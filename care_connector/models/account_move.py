import os
from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = "account.move"

    x_care_id = fields.Char(string="Care ID")
    x_identifier = fields.Char(string="Identifier in Care")
    x_created_by = fields.Char(string="Created By in Care")

    care_url = fields.Char(string="CARE Link", compute="_compute_care_url", store=False)

    @api.depends("x_care_id")
    def _compute_care_url(self):
        care_domain = os.getenv("CARE_DOMAIN")
        facility_id = os.getenv("CARE_FACILITY_ID")
        for rec in self:
            if rec.x_care_id and care_domain and facility_id:
                rec.care_url = (
                    f"{care_domain}/facility/{facility_id}/"
                    f"billing/invoices/{rec.x_care_id}"
                )
            else:
                rec.care_url = False


class AccountMoveLines(models.Model):
    _inherit = "account.move.line"

    x_care_id = fields.Char(string="Care Charge Item ID")
    received_qty = fields.Float(string="Quantity", store=True)
    free_qty = fields.Float(string="Free Quantity")

    @api.onchange("received_qty", "free_qty")
    def _onchange_received_qty(self):
        if self.move_id.move_type == "in_invoice":
            self.quantity = self.received_qty - self.free_qty
            if self.free_qty > self.received_qty:
                self.free_qty = 0
                self.quantity = self.received_qty
        else:
            self.quantity = self.received_qty
            self.free_qty = 0
