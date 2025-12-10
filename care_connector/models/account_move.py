from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    x_care_id = fields.Char(string='Care ID')


class AccountMoveLines(models.Model):
    _inherit = 'account.move.line'

    x_care_id = fields.Char(string='Care Ml ID')
    received_qty = fields.Float(string='Quantity', store=True)
    free_qty = fields.Float(string='Free Quantity')

    @api.onchange('received_qty','free_qty')
    def _onchange_received_qty(self):
        if self.move_id.move_type == 'in_invoice':
            self.quantity = self.received_qty - self.free_qty
            if self.free_qty > self.received_qty:
                self.free_qty = 0
                self.quantity = self.received_qty
        else:
            self.quantity = self.received_qty
            self.free_qty = 0