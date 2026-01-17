# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SponsorCompany(models.Model):
    _name = "sponsor.company"
    _description = "Sponsor Company"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    _sql_constraints = [
        (
            "code_unique",
            "UNIQUE(code, company_id)",
            "Sponsor code must be unique per company!",
        ),
    ]

    # Basic Information
    name = fields.Char(
        string="Company Name",
        required=True,
        tracking=True,
    )
    code = fields.Char(
        string="Code",
        tracking=True,
        help="Short code for the sponsor company",
    )

    # Contact Information
    phone = fields.Char(string="Phone")
    mobile = fields.Char(string="Mobile")
    email = fields.Char(string="Email")
    website = fields.Char(string="Website")

    # Address
    street = fields.Char(string="Street")
    street2 = fields.Char(string="Street 2")
    city = fields.Char(string="City")
    state_id = fields.Many2one(
        "res.country.state",
        string="State",
        domain="[('country_id', '=', country_id)]",
    )
    zip = fields.Char(string="ZIP")
    country_id = fields.Many2one("res.country", string="Country")

    # Contact Person
    contact_name = fields.Char(string="Contact Person")
    contact_phone = fields.Char(string="Contact Phone")
    contact_email = fields.Char(string="Contact Email")
    contact_designation = fields.Char(string="Contact Designation")

    # Accounting
    account_id = fields.Many2one(
        "account.account",
        string="Receivable Account",
        domain="[('account_type', '=', 'asset_receivable')]",
        required=True,
        tracking=True,
        help="Account used for sponsor receivables when invoices are assigned",
    )

    # Status
    active = fields.Boolean(default=True)
    notes = fields.Text(string="Internal Notes")

    # Company
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    # Computed Fields
    invoice_count = fields.Integer(
        string="Invoice Count",
        compute="_compute_invoice_count",
    )
    invoice_ids = fields.One2many(
        "account.move",
        "sponsor_company_id",
        string="Invoices",
        domain=[("move_type", "in", ["out_invoice", "out_refund"])],
    )
    total_invoiced = fields.Monetary(
        string="Total Invoiced",
        compute="_compute_totals",
        currency_field="currency_id",
    )
    total_outstanding = fields.Monetary(
        string="Outstanding Amount",
        compute="_compute_totals",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )

    @api.depends("invoice_ids")
    def _compute_invoice_count(self):
        for sponsor in self:
            sponsor.invoice_count = len(
                sponsor.invoice_ids.filtered(lambda m: m.state == "posted")
            )

    @api.depends(
        "invoice_ids.amount_total", "invoice_ids.amount_residual", "invoice_ids.state"
    )
    def _compute_totals(self):
        for sponsor in self:
            posted_invoices = sponsor.invoice_ids.filtered(
                lambda m: m.state == "posted" and m.move_type == "out_invoice"
            )
            posted_refunds = sponsor.invoice_ids.filtered(
                lambda m: m.state == "posted" and m.move_type == "out_refund"
            )
            sponsor.total_invoiced = sum(posted_invoices.mapped("amount_total")) - sum(
                posted_refunds.mapped("amount_total")
            )
            sponsor.total_outstanding = sum(
                posted_invoices.mapped("amount_residual")
            ) - sum(posted_refunds.mapped("amount_residual"))

    def action_view_invoices(self):
        """Open list of invoices for this sponsor."""
        self.ensure_one()
        return {
            "name": _("Sponsored Invoices"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [
                ("sponsor_company_id", "=", self.id),
                ("move_type", "in", ["out_invoice", "out_refund"]),
            ],
            "context": {
                "default_sponsor_company_id": self.id,
                "default_move_type": "out_invoice",
                "create": False,
            },
        }

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        """Allow searching by code as well as name."""
        args = args or []
        if name:
            domain = ["|", ("name", operator, name), ("code", operator, name)]
            return self.search(domain + args, limit=limit).name_get()
        return super().name_search(name, args, operator, limit)
