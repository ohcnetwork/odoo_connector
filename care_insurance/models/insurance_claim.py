# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from collections import defaultdict


class InsuranceClaim(models.Model):
    _name = "insurance.claim"
    _description = "Insurance Claim"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Claim Reference",
        required=True,
        readonly=True,
        default="New",
        copy=False,
        tracking=True,
    )
    customer_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        tracking=True,
    )
    customer_care_id = fields.Char(
        string="Identifier in Care",
        readonly=True,
        help="Populated from invoice x_care_id when fetching lines",
    )
    # Address from customer
    customer_street = fields.Char(
        string="Street",
        related="customer_id.street",
        readonly=True,
    )
    customer_street2 = fields.Char(
        string="Street 2",
        related="customer_id.street2",
        readonly=True,
    )
    customer_city = fields.Char(
        string="City",
        related="customer_id.city",
        readonly=True,
    )
    customer_zip = fields.Char(
        string="ZIP",
        related="customer_id.zip",
        readonly=True,
    )
    customer_state_id = fields.Many2one(
        related="customer_id.state_id",
        readonly=True,
    )
    customer_country_id = fields.Many2one(
        related="customer_id.country_id",
        readonly=True,
    )
    insurance_company_id = fields.Many2one(
        "insurance.company",
        string="Insurance Company",
        required=True,
        tracking=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Journal",
        required=True,
        tracking=True,
        default=lambda self: self._get_default_journal(),
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("reconciled", "Reconciled"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )

    # Approval fields
    approved_date = fields.Date(
        string="Approved Date",
        tracking=True,
    )
    approved_amount = fields.Monetary(
        string="Approved Amount",
        currency_field="currency_id",
        tracking=True,
    )
    journal_ref = fields.Char(
        string="Journal Reference",
        tracking=True,
    )
    rejection_reason = fields.Text(
        string="Rejection Reason",
        readonly=True,
    )

    # Hospital specific fields
    age = fields.Integer(
        string="Customer Age",
    )
    birthdate = fields.Date(
        string="Date of Birth",
        related="customer_id.x_birthdate",
        readonly=True,
        store=True,
    )
    gender = fields.Selection(
        related="customer_id.x_gender",
        string="Gender",
        readonly=True,
        store=True,
    )
    doctor = fields.Char(string="Doctor")
    claim_number = fields.Char(string="Claim Number")
    room_number = fields.Char(string="Room No")
    no_of_days = fields.Integer(
        string="No. of Days",
        compute="_compute_no_of_days",
        store=True,
        readonly=False,
        help="Number of days (discharge - admission). Editable.",
    )
    admission_date = fields.Datetime(string="Admission Date")
    discharge_date = fields.Datetime(string="Discharge Date")
    narration = fields.Text(string="Notes")

    # Invoice info (populated when fetching lines)
    account = fields.Char(
        string="Account",
        readonly=True,
        help="Account identifier from invoice x_account field",
    )
    ip_bill_no = fields.Char(
        string="IP Bill Number",
        readonly=True,
        help="IP Bill Number from invoice",
    )
    bill_generated_on = fields.Datetime(
        string="Bill Generated On",
        help="Invoice creation date from Odoo",
    )

    # Category lines (stored, editable)
    category_ids = fields.One2many(
        "insurance.claim.category",
        "claim_id",
        string="Category Summary",
    )

    # Track which invoice lines are included in this claim (for filtering)
    claimed_move_line_ids = fields.Many2many(
        "account.move.line",
        "insurance_claim_move_line_rel",
        "claim_id",
        "move_line_id",
        string="Claimed Invoice Lines",
        copy=False,
    )

    # Computed totals (all amounts are tax inclusive)
    total_original_amount = fields.Monetary(
        string="Total Original",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
        help="Total original amount (tax inclusive)",
    )
    total_insurance_amount = fields.Monetary(
        string="Total Insurance",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
        help="Total insurance amount (tax inclusive)",
    )

    # Related records
    journal_entry_id = fields.Many2one(
        "account.move",
        string="Journal Entry",
        readonly=True,
        copy=False,
    )

    # Company and currency
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Default Methods
    # -------------------------------------------------------------------------

    @api.model
    def _get_default_journal(self):
        """Get default journal from settings."""
        journal_id = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("care_insurance.default_journal_id", default=False)
        )
        if journal_id:
            return self.env["account.journal"].browse(int(journal_id)).exists()
        return False

    # -------------------------------------------------------------------------
    # Compute Methods
    # -------------------------------------------------------------------------

    @api.depends(
        "category_ids.original_amount",
        "category_ids.insurance_amount",
        "category_ids.include_in_report",
    )
    def _compute_totals(self):
        for claim in self:
            included_categories = claim.category_ids.filtered(
                lambda c: c.include_in_report
            )
            claim.total_original_amount = sum(
                included_categories.mapped("original_amount")
            )
            claim.total_insurance_amount = sum(
                included_categories.mapped("insurance_amount")
            )

    @api.depends("admission_date", "discharge_date")
    def _compute_no_of_days(self):
        for claim in self:
            if claim.admission_date and claim.discharge_date:
                delta = claim.discharge_date - claim.admission_date
                claim.no_of_days = delta.days
            else:
                claim.no_of_days = 0

    @api.onchange("customer_id")
    def _onchange_customer_id(self):
        if self.customer_id:
            self.age = self.customer_id.x_age

    # -------------------------------------------------------------------------
    # CRUD Methods
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("insurance.claim") or "New"
                )
        return super().create(vals_list)

    def unlink(self):
        for claim in self:
            if claim.state not in ("draft", "rejected"):
                raise UserError(
                    _(
                        "You cannot delete a claim that is not in Draft or Rejected state."
                    )
                )
            if claim.journal_entry_id:
                raise UserError(
                    _(
                        "You cannot delete a claim that has a journal entry. "
                        "Please cancel the journal entry first."
                    )
                )
        return super().unlink()

    # -------------------------------------------------------------------------
    # Action Methods
    # -------------------------------------------------------------------------

    def action_fetch_invoice_lines(self):
        """Fetch invoice lines and group by product category."""
        self.ensure_one()

        if self.state != "draft":
            raise UserError(_("You can only fetch lines in Draft state."))

        # Get the insurance tag from settings
        insurance_tag = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("res.config.settings.insurance_tag_setting", default="")
        )

        if not insurance_tag:
            raise UserError(
                _(
                    "Insurance tag is not configured. "
                    "Please configure it in Accounting Settings."
                )
            )

        # Clear existing categories and claimed lines
        self.category_ids.unlink()
        self.claimed_move_line_ids = [(5, 0, 0)]

        # Get invoice lines already claimed in OTHER claims (not draft/rejected)
        other_claims = self.search(
            [
                ("id", "!=", self.id),
                ("state", "not in", ["draft", "rejected"]),
            ]
        )
        already_claimed_line_ids = other_claims.mapped("claimed_move_line_ids").ids

        # Search for matching invoice lines (excluding already claimed)
        domain = [
            ("insurance_tag", "=", insurance_tag),
            ("partner_id", "=", self.customer_id.id),
            ("display_type", "=", "product"),
            ("move_id.move_type", "in", ["out_invoice", "out_refund"]),
            ("move_id.state", "=", "posted"),
            ("move_id.payment_state", "=", "not_paid"),
        ]
        if already_claimed_line_ids:
            domain.append(("id", "not in", already_claimed_line_ids))

        invoice_lines = self.env["account.move.line"].search(domain)

        if not invoice_lines:
            raise UserError(
                _(
                    "No invoice lines found for this customer with the insurance tag. "
                    "Either no invoices exist, or all lines are already claimed."
                )
            )

        def get_root_category(category):
            """Get the root (top-level) parent category."""
            if not category:
                return None
            while category.parent_id:
                category = category.parent_id
            return category

        # Group by root/parent category
        category_totals = defaultdict(
            lambda: {
                "amount": 0.0,
                "amount_with_tax": 0.0,  # Sum of tax-inclusive amounts per line
                "category_id": None,
                "category_name": "Uncategorized",
                "line_ids": [],
            }
        )

        for line in invoice_lines:
            # Apply sign based on move type: negative for credit notes, positive for invoices
            sign = -1 if line.move_id.move_type == "out_refund" else 1
            signed_amount = line.price_subtotal * sign

            # Calculate tax-inclusive amount for this line using its actual tax
            line_tax_rate = line.tax_ids[0].amount if line.tax_ids else 0.0
            tax_multiplier = 1 + (line_tax_rate / 100)
            signed_amount_with_tax = signed_amount * tax_multiplier

            # Get the root category for grouping
            category = line.product_id.categ_id if line.product_id else None
            root_category = get_root_category(category)

            if root_category:
                key = root_category.id
                category_totals[key]["category_id"] = root_category.id
                category_totals[key]["category_name"] = root_category.name
            else:
                key = 0  # Uncategorized

            category_totals[key]["amount"] += signed_amount
            category_totals[key]["amount_with_tax"] += signed_amount_with_tax
            category_totals[key]["line_ids"].append(line.id)

        if not category_totals:
            raise UserError(_("No valid invoice lines found."))

        # Collect all line IDs for tracking
        all_line_ids = []

        # Create category records with incrementing sequence
        category_records = []
        sequence = 10
        for key, data in category_totals.items():
            # Use tax-inclusive amount as rate (qty=1)
            tax_inclusive_rate = data["amount_with_tax"]

            category_records.append(
                {
                    "claim_id": self.id,
                    "sequence": sequence,
                    "category_id": data["category_id"],
                    "category_name": data["category_name"],
                    # Original: Qty=1, Rate=tax inclusive total
                    "original_quantity": 1.0,
                    "original_rate": tax_inclusive_rate,
                    # Insurance: same as original initially
                    "insurance_quantity": 1.0,
                    "insurance_rate": tax_inclusive_rate,
                }
            )
            all_line_ids.extend(data["line_ids"])
            sequence += 10  # Increment by 10 for each category

        if category_records:
            self.env["insurance.claim.category"].create(category_records)

        # Store the claimed line IDs for future filtering
        if all_line_ids:
            self.claimed_move_line_ids = [(6, 0, all_line_ids)]

        # Populate fields from invoices
        invoices = self.claimed_move_line_ids.mapped("move_id")
        if invoices:
            first_invoice = invoices[0]
            update_vals = {}

            # Identifier in Care from invoice's x_identifier
            if first_invoice.x_identifier:
                update_vals["customer_care_id"] = first_invoice.x_identifier

            # Account from invoice's x_account
            if first_invoice.x_account:
                update_vals["account"] = first_invoice.x_account

            # IP Bill Number from invoice
            if first_invoice.ip_bill_no:
                update_vals["ip_bill_no"] = first_invoice.ip_bill_no

            # Bill Generated On from invoice's create_date
            create_dates = invoices.mapped("create_date")
            if create_dates:
                update_vals["bill_generated_on"] = min(create_dates)

            # Doctor, room, admission, discharge from first invoice if not set
            if not self.doctor and first_invoice.doctor:
                update_vals["doctor"] = first_invoice.doctor
            if not self.room_number and first_invoice.room_number:
                update_vals["room_number"] = first_invoice.room_number
            if not self.admission_date and first_invoice.admission_date:
                update_vals["admission_date"] = first_invoice.admission_date
            if not self.discharge_date and first_invoice.discharge_date:
                update_vals["discharge_date"] = first_invoice.discharge_date

            if update_vals:
                self.write(update_vals)

        return True

    def action_confirm(self):
        """Confirm the insurance claim."""
        for claim in self:
            if claim.state != "draft":
                raise UserError(_("Only draft claims can be confirmed."))

            if not claim.category_ids:
                raise UserError(
                    _("Please fetch invoice lines before confirming the claim.")
                )

            claim.state = "confirmed"

    def action_approve(self):
        """Approve the claim and create journal entry."""
        for claim in self:
            if claim.state != "confirmed":
                raise UserError(_("Only confirmed claims can be approved."))

            if not claim.approved_amount:
                raise UserError(_("Please enter the Approved Amount."))

            if not claim.approved_date:
                raise UserError(_("Please enter the Approved Date."))

            if not claim.insurance_company_id.account_id:
                raise UserError(
                    _(
                        "Please configure a receivable account for the insurance company '%s'."
                    )
                    % claim.insurance_company_id.name
                )

            if not claim.customer_id.property_account_receivable_id:
                raise UserError(
                    _("Customer '%s' does not have a receivable account configured.")
                    % claim.customer_id.name
                )

            if not claim.journal_id:
                raise UserError(_("Please select a Journal."))

            # Create journal entry
            move_vals = {
                "ref": f"INS/{claim.name}/{claim.journal_ref}",
                "journal_id": claim.journal_id.id,
                "move_type": "entry",
                "date": claim.approved_date,
                "company_id": claim.company_id.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": claim.insurance_company_id.account_id.id,
                            "name": _("Insurance Company Receivable - %s")
                            % claim.insurance_company_id.name,
                            "debit": claim.approved_amount,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "account_id": claim.customer_id.property_account_receivable_id.id,
                            "name": _("Customer Credit (Insurance) - %s")
                            % claim.customer_id.name,
                            "debit": 0.0,
                            "credit": claim.approved_amount,
                            "partner_id": claim.customer_id.id,
                        },
                    ),
                ],
            }

            move = self.env["account.move"].create(move_vals)
            move.action_post()

            claim.write(
                {
                    "journal_entry_id": move.id,
                    "state": "approved",
                }
            )

    def action_reject(self):
        """Open wizard to enter rejection reason."""
        self.ensure_one()
        if self.state != "confirmed":
            raise UserError(_("Only confirmed claims can be rejected."))

        return {
            "name": _("Reject Insurance Claim"),
            "type": "ir.actions.act_window",
            "res_model": "insurance.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_claim_id": self.id},
        }

    def action_reconcile(self):
        """Reconcile the insurance journal entry with customer invoices."""
        for claim in self:
            if claim.state != "approved":
                raise UserError(_("Only approved claims can be reconciled."))

            if not claim.journal_entry_id:
                raise UserError(_("No journal entry found to reconcile."))

            receivable_account = claim.customer_id.property_account_receivable_id
            if not receivable_account:
                raise UserError(
                    _("Customer '%s' has no receivable account configured.")
                    % claim.customer_id.name
                )

            # Get the credit line from insurance journal entry (customer receivable credit)
            insurance_credit_line = claim.journal_entry_id.line_ids.filtered(
                lambda l: l.account_id == receivable_account
                and l.credit > 0
                and not l.reconciled
            )

            if not insurance_credit_line:
                raise UserError(
                    _("No open receivable line found on the insurance journal entry.")
                )

            # Get receivable lines from related invoices using claimed_move_line_ids
            related_invoice_ids = claim.claimed_move_line_ids.mapped("move_id").ids
            if not related_invoice_ids:
                raise UserError(_("No related invoices found for this claim."))

            invoice_debit_lines = self.env["account.move.line"].search(
                [
                    ("account_id", "=", receivable_account.id),
                    ("partner_id", "=", claim.customer_id.id),
                    ("reconciled", "=", False),
                    ("move_id", "in", related_invoice_ids),
                    ("debit", ">", 0),
                ]
            )

            if not invoice_debit_lines:
                raise UserError(
                    _(
                        "No open receivable lines found on the related customer invoices. "
                        "The invoices may already be paid."
                    )
                )

            # Reconcile the lines
            lines_to_reconcile = insurance_credit_line | invoice_debit_lines
            lines_to_reconcile.reconcile()

            claim.state = "reconciled"

    def action_undo_reconcile(self):
        """Undo reconciliation and revert claim to approved state."""
        for claim in self:
            if claim.state != "reconciled":
                raise UserError(_("Only reconciled claims can be unreconciled."))

            if not claim.journal_entry_id:
                raise UserError(_("No journal entry found."))

            receivable_account = claim.customer_id.property_account_receivable_id
            if not receivable_account:
                raise UserError(
                    _("Customer '%s' has no receivable account configured.")
                    % claim.customer_id.name
                )

            # Find reconciled lines on the insurance journal entry
            reconciled_lines = claim.journal_entry_id.line_ids.filtered(
                lambda l: l.account_id == receivable_account and l.reconciled
            )

            if reconciled_lines:
                reconciled_lines.remove_move_reconcile()

            claim.state = "approved"

    def action_undo_approval(self):
        """Undo approval: delete the posted journal entry and revert to confirmed.

        This is intended for cases where the approval was made in error and the
        journal entry should be removed entirely (not reversed).
        """
        for claim in self:
            if claim.state != "approved":
                raise UserError(_("Only approved claims can be unapproved."))

            move = claim.journal_entry_id
            if move:
                # Block deletion if any line has been reconciled (safety net;
                # reconciled claims should use Undo Reconcile first).
                if any(line.reconciled for line in move.line_ids):
                    raise UserError(
                        _(
                            "Cannot delete the journal entry because some of its "
                            "lines are reconciled. Please undo the reconciliation first."
                        )
                    )

                move_name = move.name
                # Set to draft (account.move.unlink only allows draft/cancel moves)
                if move.state == "posted":
                    move.button_draft()
                move.with_context(force_delete=True).unlink()

                claim.message_post(
                    body=_(
                        "Approval undone by %(user)s. Journal entry %(move)s was deleted."
                    )
                    % {
                        "user": self.env.user.name,
                        "move": move_name,
                    }
                )
            else:
                claim.message_post(
                    body=_("Approval undone by %(user)s.")
                    % {"user": self.env.user.name}
                )

            claim.write(
                {
                    "journal_entry_id": False,
                    "state": "confirmed",
                }
            )

    def action_reset_to_draft(self):
        """Reset confirmed or rejected claim to draft."""
        for claim in self:
            if claim.state not in ("confirmed", "rejected"):
                raise UserError(
                    _("Only confirmed or rejected claims can be reset to draft.")
                )

            claim.write(
                {
                    "state": "draft",
                    "rejection_reason": False,
                }
            )

    def action_view_journal_entry(self):
        """Open the journal entry."""
        self.ensure_one()
        if not self.journal_entry_id:
            return False

        return {
            "name": _("Journal Entry"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.journal_entry_id.id,
            "context": {"create": False},
        }

    def action_print_voucher(self):
        """Print the insurance voucher report."""
        self.ensure_one()

        if not self.category_ids:
            raise UserError(_("Cannot print voucher: No category data in this claim."))

        return self.env.ref(
            "care_insurance.action_report_insurance_voucher"
        ).report_action(self)
