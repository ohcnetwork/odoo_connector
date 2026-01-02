from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = "product.template"

    x_care_id = fields.Char(string="Care ID")
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
                # Placeholder URL pattern for products
                record.x_care_url = f"{base_url}/products/{record.x_care_id}"
            else:
                record.x_care_url = False
