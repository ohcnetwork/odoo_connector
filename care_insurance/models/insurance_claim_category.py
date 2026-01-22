# -*- coding: utf-8 -*-

from odoo import models, fields, api


class InsuranceClaimCategory(models.Model):
    """Stored model for category-level insurance claim data."""

    _name = "insurance.claim.category"
    _description = "Insurance Claim Category"
    _order = "sequence, category_name"

    sequence = fields.Integer(string="Sequence", default=10)
    claim_id = fields.Many2one(
        "insurance.claim", string="Claim", required=True, ondelete="cascade"
    )
    category_id = fields.Many2one(
        "product.category",
        string="Category",
        help="Select a product category",
    )
    category_name = fields.Char(
        string="Category Name",
        compute="_compute_category_name",
        store=True,
        readonly=False,
    )
    currency_id = fields.Many2one(
        "res.currency", related="claim_id.currency_id", store=True
    )

    # Tax from first product of category
    tax_id = fields.Many2one(
        "account.tax",
        string="Tax",
        readonly=True,
        help="Tax from first invoice line of this category",
    )
    tax_rate = fields.Float(
        string="Tax %",
        compute="_compute_tax_rate",
        store=True,
        help="Tax percentage from associated tax",
    )

    # Control flags
    is_manual = fields.Boolean(
        string="Manually Added",
        default=False,
        readonly=True,
        help="True if this category was manually added (not from invoice lines)",
    )
    include_in_report = fields.Boolean(
        string="Include",
        default=True,
        help="Include this category in the report totals and voucher",
    )
    print_line_items = fields.Boolean(
        string="Print Items",
        default=False,
        help="Print individual line items under this category in the voucher",
    )

    # Original values (from invoice lines - 0 for manual categories)
    original_quantity = fields.Float(string="Orig. Qty", default=1.0, readonly=True)
    original_rate = fields.Monetary(
        string="Orig. Rate", currency_field="currency_id", readonly=True
    )
    original_amount = fields.Monetary(
        string="Orig. Amount",
        currency_field="currency_id",
        compute="_compute_original_amount",
        store=True,
    )

    # Original values with tax (computed)
    original_rate_with_tax = fields.Monetary(
        string="Orig. Rate (Incl. Tax)",
        currency_field="currency_id",
        compute="_compute_amounts_with_tax",
        store=True,
    )
    original_amount_with_tax = fields.Monetary(
        string="Orig. Amount (Incl. Tax)",
        currency_field="currency_id",
        compute="_compute_amounts_with_tax",
        store=True,
    )

    # Insurance values (editable, but readonly when print_line_items=True)
    insurance_quantity = fields.Float(string="Ins. Qty", default=1.0)
    insurance_rate = fields.Monetary(string="Ins. Rate", currency_field="currency_id")
    insurance_amount = fields.Monetary(
        string="Ins. Amount",
        currency_field="currency_id",
        compute="_compute_insurance_amount",
        store=True,
        readonly=False,
    )

    # Tax-inclusive computed fields
    insurance_rate_with_tax = fields.Monetary(
        string="Rate (Incl. Tax)",
        currency_field="currency_id",
        compute="_compute_amounts_with_tax",
        store=True,
        help="Insurance rate including tax",
    )
    insurance_amount_with_tax = fields.Monetary(
        string="Amount (Incl. Tax)",
        currency_field="currency_id",
        compute="_compute_amounts_with_tax",
        store=True,
        help="Insurance amount including tax",
    )

    @api.depends("category_id")
    def _compute_category_name(self):
        for rec in self:
            if rec.category_id:
                rec.category_name = rec.category_id.name
            elif not rec.category_name:
                rec.category_name = ""

    @api.depends("tax_id")
    def _compute_tax_rate(self):
        for rec in self:
            rec.tax_rate = rec.tax_id.amount if rec.tax_id else 0.0

    @api.depends("original_quantity", "original_rate")
    def _compute_original_amount(self):
        for rec in self:
            rec.original_amount = rec.original_quantity * rec.original_rate

    @api.depends("insurance_quantity", "insurance_rate")
    def _compute_insurance_amount(self):
        for rec in self:
            rec.insurance_amount = rec.insurance_quantity * rec.insurance_rate

    @api.depends(
        "original_rate",
        "original_amount",
        "insurance_rate",
        "insurance_amount",
        "tax_rate",
    )
    def _compute_amounts_with_tax(self):
        for rec in self:
            multiplier = 1 + (rec.tax_rate / 100)
            # Original values with tax
            rec.original_rate_with_tax = rec.original_rate * multiplier
            rec.original_amount_with_tax = rec.original_amount * multiplier
            # Insurance values with tax
            rec.insurance_rate_with_tax = rec.insurance_rate * multiplier
            rec.insurance_amount_with_tax = rec.insurance_amount * multiplier

    @api.onchange("insurance_quantity", "insurance_rate")
    def _onchange_insurance_fields(self):
        if not self.print_line_items:
            self.insurance_amount = self.insurance_quantity * self.insurance_rate

    @api.onchange("insurance_amount")
    def _onchange_insurance_amount(self):
        """If amount is manually edited, update rate (keep qty)."""
        if not self.print_line_items:
            if self.insurance_quantity and self.insurance_quantity != 0:
                self.insurance_rate = self.insurance_amount / self.insurance_quantity

    @api.onchange("print_line_items")
    def _onchange_print_line_items(self):
        """When print_line_items is checked, copy original values to insurance."""
        if self.print_line_items and not self.is_manual:
            self.insurance_quantity = self.original_quantity
            self.insurance_rate = self.original_rate
            self.insurance_amount = self.original_amount

    @api.model_create_multi
    def create(self, vals_list):
        """Mark manually created categories."""
        for vals in vals_list:
            # If created without original values, it's manual
            if "original_rate" not in vals or vals.get("original_rate", 0) == 0:
                vals["is_manual"] = True
                vals["print_line_items"] = False
        return super().create(vals_list)
