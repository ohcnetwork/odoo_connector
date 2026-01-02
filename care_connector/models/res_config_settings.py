from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    care_base_url = fields.Char(
        string="Care Base URL",
        help="Base URL for Care system (e.g., https://care.example.com)",
    )

    @api.model
    def get_values(self):
        """Get the values from settings."""
        res = super(ResConfigSettings, self).get_values()
        icp_sudo = self.env['ir.config_parameter'].sudo()
        care_base_url = icp_sudo.get_param('care.base_url', default='')
        res.update(
            care_base_url=care_base_url,
        )
        return res

    def set_values(self):
        """Set the values. The new values are stored in the configuration parameters."""
        res = super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            'care.base_url', self.care_base_url or '')
        return res
