from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_disc_item = fields.Boolean(string="Discount Item")
    discount_group = fields.Many2one('account.discount.groups', string="Discount Group", ondelete='cascade')
    disc_amount = fields.Float(string="Discount Amount")
    disc_percent = fields.Float(string="Discount Percentage")