from odoo import models, fields
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    grn_number = fields.Char(string='GRN No.', readonly=True, copy=False)

    def action_post(self):
        """Assign GRN number when the vendor bill is posted (only for Care invoices)"""
        for move in self:
            # Only assign GRN for vendor bills from Care system (has x_care_id)
            if move.move_type == 'in_invoice' and move.x_care_id and not move.grn_number:
                next_number = self.env['ir.sequence'].next_by_code('grn.number.sequence')
                
                if next_number:
                    move.grn_number = next_number
                    _logger.info("Assigned GRN %s to Care invoice %s (x_care_id: %s)", 
                                move.grn_number, move.name or move.id, move.x_care_id)
                else:
                    _logger.error("GRN sequence 'grn.number.sequence' not found")
                    raise UserError("GRN sequence not configured. Please contact administrator.")

        return super().action_post()
