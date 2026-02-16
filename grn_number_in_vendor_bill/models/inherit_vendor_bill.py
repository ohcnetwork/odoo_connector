from odoo import models, fields
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    grn_number = fields.Char(string='GRN No.', readonly=True, copy=False)
    grn_sequence_id = fields.Many2one(
        'ir.sequence',
        string='GRN Sequence',
        copy=False,
        domain=[('code', 'like', 'grn.%')],
        help="Select the GRN sequence to use when posting this vendor bill. "
             "Create sequences from Settings > Technical > Sequences with a code starting with 'grn.'",
    )

    def action_post(self):
        """Assign GRN number when the vendor bill is posted (only for Care invoices)"""
        for move in self:
            # Only assign GRN for vendor bills from Care system (has x_care_id)
            if move.move_type == 'in_invoice' and move.x_care_id and not move.grn_number:
                if not move.grn_sequence_id:
                    raise UserError("Please select a GRN Sequence before posting this vendor bill.")

                # Use invoice date for sequence date range
                sequence_date = move.invoice_date or fields.Date.today()

                next_number = move.grn_sequence_id.with_context(
                    ir_sequence_date=sequence_date
                ).next_by_id()

                if next_number:
                    move.grn_number = next_number
                    _logger.info("Assigned GRN %s (sequence=%s) to invoice %s",
                                 move.grn_number, move.grn_sequence_id.name, move.name or move.id)
                else:
                    raise UserError("Failed to generate GRN number from sequence '%s'. "
                                    "Please contact administrator." % move.grn_sequence_id.name)

        return super().action_post()
