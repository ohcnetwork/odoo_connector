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
    age = fields.Char(string="Customer Age")
    doctor = fields.Char(string="Doctor")
    bill_number = fields.Char(string="Bill Number")
    ip_number = fields.Char(string="I.P. No")
    op_number = fields.Char(string="O.P. No")
    room_number = fields.Char(string="Room No")
    admission_date = fields.Datetime(string="Admission Date")
    as_on = fields.Datetime(string="As On")
    narration = fields.Text(string="Notes")

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

    # Computed fields
    total_original_amount = fields.Monetary(
        string="Total Original Amount",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    total_insurance_amount = fields.Monetary(
        string="Total Insurance Amount",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
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

    @api.depends("category_ids.original_amount", "category_ids.insurance_amount")
    def _compute_totals(self):
        for claim in self:
            claim.total_original_amount = sum(
                claim.category_ids.mapped("original_amount")
            )
            claim.total_insurance_amount = sum(
                claim.category_ids.mapped("insurance_amount")
            )

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
            ("move_id.insurance_company_id", "=", self.insurance_company_id.id),
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

        # Group by product category
        category_totals = defaultdict(
            lambda: {
                "amount": 0.0,
                "category_id": None,
                "category_name": "Uncategorized",
                "line_ids": [],
            }
        )

        for line in invoice_lines:
            if line.price_subtotal > 0:
                category = line.product_id.categ_id if line.product_id else None
                if category:
                    key = category.id
                    category_totals[key]["category_id"] = category.id
                    category_totals[key]["category_name"] = category.name
                else:
                    key = 0  # Uncategorized

                category_totals[key]["amount"] += line.price_subtotal
                category_totals[key]["line_ids"].append(line.id)

        if not category_totals:
            raise UserError(_("No valid invoice lines found with positive amounts."))

        # Collect all line IDs for tracking
        all_line_ids = []

        # Create category records
        category_records = []
        for key, data in category_totals.items():
            total_amount = data["amount"]
            category_records.append(
                {
                    "claim_id": self.id,
                    "category_id": data["category_id"],
                    "category_name": data["category_name"],
                    # Original: Qty=1, Rate=total
                    "original_quantity": 1.0,
                    "original_rate": total_amount,
                    # Insurance: same as original initially
                    "insurance_quantity": 1.0,
                    "insurance_rate": total_amount,
                }
            )
            all_line_ids.extend(data["line_ids"])

        if category_records:
            self.env["insurance.claim.category"].create(category_records)

        # Store the claimed line IDs for future filtering
        if all_line_ids:
            self.claimed_move_line_ids = [(6, 0, all_line_ids)]

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

    def action_reset_to_draft(self):
        """Reset rejected claim to draft."""
        for claim in self:
            if claim.state != "rejected":
                raise UserError(_("Only rejected claims can be reset to draft."))

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
