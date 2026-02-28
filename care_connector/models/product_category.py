from odoo import models, fields

class ProductCategory(models.Model):
    _inherit = "product.category"

    x_care_id = fields.Char(string="Care ID")