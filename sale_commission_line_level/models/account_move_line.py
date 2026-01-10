# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # Salesperson for commission calculation at line level
    # If set, this overrides the invoice-level invoice_user_id for commission purposes
    commission_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Commission Salesperson',
        store=True,
        readonly=False,
        help='Salesperson who earns commission on this line. '
             'If empty, falls back to the invoice salesperson.',
        copy=True,
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-populate commission_user_id from sale order line if available."""
        lines = super().create(vals_list)
        for line in lines:
            # Only auto-populate if not explicitly set and linked to a sale order
            if not line.commission_user_id and line.sale_line_ids:
                sale_line = line.sale_line_ids[:1]
                if sale_line and sale_line.order_id.user_id:
                    line.write({'commission_user_id': sale_line.order_id.user_id.id})
        return lines

    def _get_commission_user_id(self):
        """Get the effective user for commission calculation.
        
        Returns the line-level commission_user_id if set,
        otherwise falls back to the invoice-level invoice_user_id.
        """
        self.ensure_one()
        return self.commission_user_id or self.move_id.invoice_user_id
