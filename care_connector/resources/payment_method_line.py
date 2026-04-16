class PaymentMethodLineUtility:
    """Utility class for fetching payment method lines from Odoo.

    Payment method lines represent individual payment methods configured on journals.
    For 'credit' journals (Care of Accounts), each payment method line represents
    a specific charity, sponsor, or fund that can pay on behalf of patients.
    """

    @classmethod
    def get_payment_method_lines(cls, user_env, journal_type='credit'):
        """Fetch inbound payment method lines for journals with the specified care code.

        Args:
            user_env: Authenticated Odoo environment
            journal_type: The x_care_journal_code value to filter journals by.
                         Default is 'credit' for Care of Accounts.

        Returns:
            List of dicts containing payment method line information

        Raises:
            ValueError: If no journal is configured for the specified type
        """
        account_journal_model = user_env['account.journal']
        payment_method_line_model = user_env['account.payment.method.line']

        # Find journals with the specified care connector code
        journals = account_journal_model.sudo().search([
            ('x_care_journal_code', '=', journal_type)
        ])

        if not journals:
            raise ValueError(
                f"No journal configured for Care Connector code '{journal_type}'. "
                f"Please set the 'Care Connector Code' field on the appropriate journal."
            )

        # Fetch inbound payment method lines for these journals
        payment_method_lines = payment_method_line_model.sudo().search([
            ('journal_id', 'in', journals.ids),
            ('payment_type', '=', 'inbound')
        ])

        result = []
        for pml in payment_method_lines:
            result.append({
                'id': pml.id,
                'name': pml.name,
                'code': pml.code if hasattr(pml, 'code') else None,
                'journal_id': pml.journal_id.id,
                'journal_name': pml.journal_id.name,
            })

        return result

    @classmethod
    def get_payment_method_line_by_id(cls, user_env, payment_method_line_id):
        """Fetch a specific payment method line by ID.

        Args:
            user_env: Authenticated Odoo environment
            payment_method_line_id: The ID of the payment method line

        Returns:
            Payment method line record or None

        Raises:
            ValueError: If payment method line not found
        """
        payment_method_line_model = user_env['account.payment.method.line']

        pml = payment_method_line_model.sudo().browse(payment_method_line_id)
        if not pml.exists():
            raise ValueError(f"Payment method line with ID {payment_method_line_id} not found")

        return pml

    @classmethod
    def validate_payment_method_line_for_journal(cls, user_env, payment_method_line_id, journal_id):
        """Validate that a payment method line belongs to the specified journal.

        Args:
            user_env: Authenticated Odoo environment
            payment_method_line_id: The ID of the payment method line
            journal_id: The ID of the journal

        Returns:
            Payment method line record if valid

        Raises:
            ValueError: If validation fails
        """
        pml = cls.get_payment_method_line_by_id(user_env, payment_method_line_id)

        if pml.journal_id.id != journal_id:
            raise ValueError(
                f"Payment method line '{pml.name}' does not belong to the selected journal. "
                f"Expected journal ID {journal_id}, got {pml.journal_id.id}"
            )

        if pml.payment_type != 'inbound':
            raise ValueError(
                f"Payment method line '{pml.name}' is not configured for inbound payments"
            )

        return pml

    @classmethod
    def get_payment_method_line_by_care_code(cls, user_env, care_payment_code):
        """Look up an inbound payment method line by its x_care_payment_code.

        This is used when a journal_input value (e.g. 'card', 'debit') maps to a
        payment method line rather than a journal. The method returns both the
        payment method line and its parent journal.

        Only inbound payment method lines are matched, since this is used
        for receiving payments from customers.

        Args:
            user_env: Authenticated Odoo environment
            care_payment_code: The x_care_payment_code value to search for

        Returns:
            Tuple of (payment_method_line record, journal record) or (None, None)

        Raises:
            ValueError: If multiple inbound payment method lines share the same care_payment_code
        """
        payment_method_line_model = user_env['account.payment.method.line']

        pml_records = payment_method_line_model.sudo().search([
            ('x_care_payment_code', '=', care_payment_code),
            ('payment_type', '=', 'inbound'),
        ])

        if not pml_records:
            return None, None

        if len(pml_records) > 1:
            names = ', '.join(
                f"'{r.name}' (id={r.id}, journal={r.journal_id.name})"
                for r in pml_records
            )
            raise ValueError(
                f"Multiple inbound payment method lines found with Care Payment Code "
                f"'{care_payment_code}': {names}. Please ensure the 'Care Payment Code' "
                f"field is unique for inbound payment method lines."
            )

        pml = pml_records[0]
        return pml, pml.journal_id

    @classmethod
    def validate_partner_allowed_payment_method(cls, partner, payment_method_line, payment_date):
        """Validate that the payment method is allowed for the partner on the given date.

        Called when the payment's journal matches the journal configured in
        Care Connector settings. The partner MUST have allowed payment method
        rules configured. The payment method must match a rule whose date
        range covers the payment date.

        Args:
            partner: res.partner record
            payment_method_line: account.payment.method.line record
            payment_date: date to validate against

        Raises:
            ValueError: If validation fails
        """
        if not partner:
            return

        rules = partner.x_allowed_payment_method_line_ids

        if not rules:
            raise ValueError(
                f"No allowed payment methods configured for partner "
                f"'{partner.name}'. Payments on this journal require "
                f"allowed payment methods to be set on the partner."
            )

        if not payment_method_line:
            raise ValueError(
                "A payment method line is required for payments on this journal."
            )

        matching_rules = rules.filtered(
            lambda r: r.payment_method_line_id.id == payment_method_line.id
        )

        if not matching_rules:
            raise ValueError(
                f"Payment method '{payment_method_line.name}' is not allowed for "
                f"partner '{partner.name}'."
            )

        if not any(rule.is_valid_on(payment_date) for rule in matching_rules):
            raise ValueError(
                f"Payment method '{payment_method_line.name}' is not valid for "
                f"partner '{partner.name}' today."
            )
