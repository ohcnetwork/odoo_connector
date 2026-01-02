from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    x_care_id = fields.Char(string='Care ID')
    ssmm_id = fields.Char(string='SSMM ID')
    created_by = fields.Char(string='Created By')
    x_care_url = fields.Char(
        string="Care URL",
        compute="_compute_care_url",
        store=False,
    )

    @api.depends('x_care_id')
    def _compute_care_url(self):
        """Compute the Care URL based on care_id."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('care.base_url', default='')
        for record in self:
            if record.x_care_id and base_url:
                # Placeholder URL pattern for invoices
                record.x_care_url = f"{base_url}/invoices/{record.x_care_id}"
            else:
                record.x_care_url = False


class AccountMoveLines(models.Model):
    _inherit = 'account.move.line'

    x_care_id = fields.Char(string='Care Ml ID')
    received_qty = fields.Float(string='Quantity', store=True)
    free_qty = fields.Float(string='Free Quantity')
    x_care_url = fields.Char(
        string="Care URL",
        compute="_compute_care_url",
        store=False,
    )

    @api.depends('x_care_id')
    def _compute_care_url(self):
        """Compute the Care URL based on care_id."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('care.base_url', default='')
        for record in self:
            if record.x_care_id and base_url:
                # Placeholder URL pattern for invoice lines
                record.x_care_url = f"{base_url}/invoice-lines/{record.x_care_id}"
            else:
                record.x_care_url = False

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