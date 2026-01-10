from odoo import fields, models


class CommissionPlanUser(models.Model):
    _inherit = 'sale.commission.plan.user'
    
    user_id = fields.Many2one(
        'res.users',
        string="Salesperson",
        required=True,
        domain="[]",  # Remove all restrictions - show all users including public
    )
