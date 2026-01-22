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
