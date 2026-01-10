# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Override user_id to remove the restrictive domain that blocks public users
    user_id = fields.Many2one(
        comodel_name='res.users',
        string="Salesperson",
        domain="[('company_ids', '=', company_id)]",  # Removed share=False and group restrictions
    )

    @api.depends('partner_id')
    def _compute_user_id(self):
        """Don't auto-assign current user."""
        for order in self:
            if order.partner_id and not (order._origin.id and order.user_id):
                order.user_id = (
                    order.partner_id.user_id
                    or order.partner_id.commercial_partner_id.user_id
                    or False
                )
