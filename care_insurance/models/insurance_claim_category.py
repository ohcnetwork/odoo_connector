# -*- coding: utf-8 -*-

from odoo import models, fields, api


class InsuranceClaimCategory(models.Model):
    """Stored model for category-level insurance claim data."""
    _name = "insurance.claim.category"
    _description = "Insurance Claim Category"
    _order = "category_name"

    claim_id = fields.Many2one(
        "insurance.claim", string="Claim", required=True, ondelete="cascade"
    )
    category_id = fields.Many2one("product.category", string="Category ID")
    category_name = fields.Char(string="Category", required=True)
    currency_id = fields.Many2one(
        "res.currency", related="claim_id.currency_id", store=True
    )
    
    # Original values (from invoice - readonly after fetch)
    # Qty is always 1, Rate is sum of all item amounts in category
    original_quantity = fields.Float(
        string="Orig. Qty", default=1.0, readonly=True
    )
    original_rate = fields.Monetary(
        string="Orig. Rate", currency_field="currency_id", readonly=True
    )
    original_amount = fields.Monetary(
        string="Orig. Amount", currency_field="currency_id", 
        compute="_compute_original_amount", store=True
    )
    
    # Insurance values (editable)
    insurance_quantity = fields.Float(
        string="Ins. Qty", default=1.0
    )
    insurance_rate = fields.Monetary(
        string="Ins. Rate", currency_field="currency_id"
    )
    insurance_amount = fields.Monetary(
        string="Ins. Amount", currency_field="currency_id",
        compute="_compute_insurance_amount", store=True, readonly=False
    )

    @api.depends("original_quantity", "original_rate")
    def _compute_original_amount(self):
        for rec in self:
            rec.original_amount = rec.original_quantity * rec.original_rate

    @api.depends("insurance_quantity", "insurance_rate")
    def _compute_insurance_amount(self):
        for rec in self:
            rec.insurance_amount = rec.insurance_quantity * rec.insurance_rate

    @api.onchange("insurance_quantity", "insurance_rate")
    def _onchange_insurance_fields(self):
        self.insurance_amount = self.insurance_quantity * self.insurance_rate

    @api.onchange("insurance_amount")
    def _onchange_insurance_amount(self):
        """If amount is manually edited, update rate (keep qty=1)."""
        if self.insurance_quantity and self.insurance_quantity != 0:
            self.insurance_rate = self.insurance_amount / self.insurance_quantity
