from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class CustomerInsurance(models.Model):
    _name = "customer.insurance"
    _description = "Customer Insurance"

    customer_id = fields.Many2one("res.partner", string="Customer", required=True)
    insurance_tag = fields.Char(
        string="Insurance Tag",
        required=True,
        readonly=True,
        default=lambda self: self.env["ir.config_parameter"]
        .sudo()
        .get_param("res.config.settings.insurance_tag_setting", default=""),
    )
    insurance_company_id = fields.Many2one(
        "insurance.company", string="Insurance Company", required=True
    )
    approved_date = fields.Date()

    invoice_line_ids = fields.One2many(
        "customer.insurance.line",
        "customer_insurance_id",
        string="Related Invoice Lines",
    )
    approved_amount = fields.Float()

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("approved", "Approved"),
            ("reject", "Rejected"),
            ("reconciled", "Reconciled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )

    total_insured_amount = fields.Float(
        string="Total Insured Amount", compute="_compute_totals", store=True
    )

    total_amount = fields.Float(
        string="Total Amount", compute="_compute_totals", store=True
    )
    journal_id = fields.Many2one("account.journal", string="Journal", required=True)
    narration = fields.Text()
    journal_ref = fields.Char()
    rejection_reason = fields.Text(string="Rejection Reason")
    journal_entry_id = fields.Many2one(
        "account.move", string="Journal Entry", readonly=True
    )
    invoice_count = fields.Integer(
        string="Invoice Count", compute="_compute_invoice_count", store=False
    )

    invoice_ids = fields.Many2many(
        "account.move", compute="_compute_invoice_ids", string="Invoices", store=False
    )

    age = fields.Char(string="Customer Age")
    doctor = fields.Char(string="Doctor")
    bill_number = fields.Char(string="Bill Number")
    ip_number = fields.Char(string="I.P.No")
    op_number = fields.Char(string="o.P.No")
    room_number = fields.Char(string="Room No")
    admission_date = fields.Datetime(string="Admission Date")
    as_on = fields.Datetime(string="As On")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        readonly=True,
    )

    def action_view_journal_entry(self):
        self.ensure_one()
        if not self.journal_entry_id:
            return False
        return {
            "name": _("Journal Entry"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.journal_entry_id.id,
            "context": "{'create': False}",
            "target": "current",
        }

    @api.depends("invoice_line_ids.move_line_id.move_id")
    def _compute_invoice_count(self):
        for rec in self:
            invoice_moves = rec.invoice_line_ids.move_line_id.move_id
            rec.invoice_count = len(invoice_moves)

    @api.depends("invoice_line_ids.move_line_id.move_id")
    def _compute_invoice_ids(self):
        for rec in self:
            invoice_moves = rec.invoice_line_ids.move_line_id.move_id
            rec.invoice_ids = invoice_moves.ids

    @api.depends("invoice_line_ids.price_subtotal", "invoice_line_ids.insurance_amount")
    def _compute_totals(self):
        for rec in self:
            rec.total_amount = sum(rec.invoice_line_ids.mapped("price_subtotal"))
            rec.total_insured_amount = sum(
                rec.invoice_line_ids.mapped("insurance_amount")
            )

    def action_view_invoices(self):
        self.ensure_one()
        return {
            "name": _("Invoices"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.invoice_ids.ids)],
            "context": "{'create': False}",
            "target": "current",
        }

    def action_confirm(self):
        for rec in self:
            if not rec.journal_ref:
                raise ValidationError(_("Journal Refference Not Added!!"))

            if not rec.approved_amount:
                raise ValidationError(_("Approved Amount Not Added!!"))

            if not rec.approved_date:
                raise ValidationError(_("Approved Date Not Added!!"))

            if not rec.invoice_line_ids:
                raise ValidationError(_("Fetch the Invoice Line Before Confirmation!!"))
            rec.state = "confirmed"

    def action_reject(self):
        """Open the wizard for entering rejection reason."""
        return {
            "name": "Enter Rejection Reason",
            "type": "ir.actions.act_window",
            "res_model": "insurance.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_customer_insurance_id": self.id,
            },
        }

    def action_approve(self):
        for rec in self:
            if not rec.insurance_company_id.account_id:
                raise UserError("Please set an account for the insurance company.")

            if not rec.customer_id.property_account_receivable_id:
                raise UserError("Customer does not have receivable account configured.")
            if not rec.approved_date:
                raise ValidationError(_("Approved Date not Added!!!"))

            if not rec.journal_id:
                raise UserError("Please configure a  Journal.")

            move_vals = {
                "ref": f"INS-{rec.journal_ref}-",
                "journal_id": rec.journal_id.id,
                "move_type": "entry",
                "date": rec.approved_date,
                "currency_id": self.env.company.currency_id.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": rec.insurance_company_id.account_id.id,
                            "name": "Insurance Company Debit",
                            "debit": rec.approved_amount,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "account_id": rec.customer_id.property_account_receivable_id.id,
                            "name": "Customer Credit (Insurance)",
                            "debit": 0.0,
                            "credit": rec.approved_amount,
                            "partner_id": rec.customer_id.id,
                        },
                    ),
                ],
            }
            move = self.env["account.move"].create(move_vals)
            move.action_post()
            rec.journal_entry_id = move.id
            rec.state = "approved"

    def action_reconcile(self):
        for rec in self:
            if not rec.journal_entry_id:
                raise UserError(_("No journal entry to reconcile."))

            receivable_account = rec.customer_id.property_account_receivable_id
            if not receivable_account:
                raise UserError(_("Customer has no receivable account configured."))

            insurance_receivable_line = rec.journal_entry_id.line_ids.filtered(
                lambda l: l.account_id == receivable_account
                and l.credit > 0
                and not l.reconciled
            )
            if not insurance_receivable_line:
                raise UserError(
                    _("No open receivable line found on insurance journal entry.")
                )

            invoice_receivable_lines = self.env["account.move.line"].search(
                [
                    ("account_id", "=", receivable_account.id),
                    ("partner_id", "=", rec.customer_id.id),
                    ("reconciled", "=", False),
                    ("move_id.move_type", "in", ["out_invoice", "out_refund"]),
                    ("move_id.state", "=", "posted"),
                    ("id", "!=", insurance_receivable_line.id),
                ]
            )

            related_invoice_lines = []
            for inv_line in rec.invoice_line_ids:
                if inv_line.move_line_id:
                    inv_receivable_line = (
                        inv_line.move_line_id.move_id.line_ids.filtered(
                            lambda l: l.account_id == receivable_account
                            and l.partner_id == rec.customer_id
                            and not l.reconciled
                        )
                    )
                    related_invoice_lines.extend(inv_receivable_line.ids)

            if related_invoice_lines:
                invoice_receivable_lines = invoice_receivable_lines.filtered(
                    lambda l: l.id in related_invoice_lines
                )

            if not invoice_receivable_lines:
                raise UserError(
                    _("No open receivable lines found on related customer invoices.")
                )

            lines_to_reconcile = insurance_receivable_line + invoice_receivable_lines
            lines_to_reconcile.reconcile()

            rec.state = "reconciled"

    def action_reset_to_draft(self):
        for rec in self:
            rec.state = "draft"

    @api.depends("customer_id", "insurance_tag")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                f"{rec.customer_id.name}- {rec.insurance_tag}"
                if rec.customer_id and rec.insurance_tag
                else ""
            )

    def action_fetch_invoice_lines(self):
        """Button action to load invoice lines based on insurance_tag."""
        for rec in self:
            rec.invoice_line_ids.unlink()

            if not rec.insurance_tag:
                continue

            invoice_lines = self.env["account.move.line"].search(
                [
                    ("insurance_tag", "=", rec.insurance_tag),
                    ("partner_id", "=", rec.customer_id.id),
                    ("display_type", "=", "product"),
                    ("move_id.move_type", "in", ["out_invoice", "out_refund"]),
                ]
            )

            if not invoice_lines:
                raise ValidationError(
                    _(
                        "Either no invoice has been generated for the selected customer, or the insurance tag has been entered incorrectly!!"
                    )
                )

            for line in invoice_lines:
                if line.price_subtotal > 0:
                    self.env["customer.insurance.line"].create(
                        {
                            "customer_insurance_id": rec.id,
                            "description": line.name,
                            "product_id": line.product_id.id,
                            "quantity": line.quantity,
                            "price_unit": line.price_unit,
                            "move_line_id": line.id,
                            "price_subtotal": line.price_subtotal,
                        }
                    )


class CustomerInsuranceLine(models.Model):
    _name = "customer.insurance.line"
    _description = "Invoice Line linked to Insurance Customer"
    _order = "id desc"

    customer_insurance_id = fields.Many2one(
        "customer.insurance", string="Customer Insurance"
    )
    move_line_id = fields.Many2one("account.move.line", string="Invoice Line")

    description = fields.Char(string="Description")
    product_id = fields.Many2one("product.product", string="Product")
    quantity = fields.Float(string="Quantity")
    price_unit = fields.Float(string="Unit Price")
    price_subtotal = fields.Float(string="Subtotal")
    insurance_amount = fields.Float(string="Insurance Amount")
    show_in_report = fields.Boolean()

    @api.onchange("quantity", "price_unit")
    def _onchange_qty_price(self):
        for line in self:
            qty = line.quantity or 0.0
            price = line.price_unit or 0.0
            line.price_subtotal = qty * price

    @api.onchange("insurance_amount")
    def _onchange_insurance_amount(self):
        for line in self:
            if line.insurance_amount and line.quantity:
                line.price_unit = line.insurance_amount / line.quantity
                line.price_subtotal = line.insurance_amount
            else:
                line.price_unit = 0.0
                line.price_subtotal = 0.0
