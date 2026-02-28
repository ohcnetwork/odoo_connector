from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = "product.template"

    x_care_id = fields.Char(string="Care ID")