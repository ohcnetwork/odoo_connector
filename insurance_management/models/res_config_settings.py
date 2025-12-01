from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    insurance_tag_setting = fields.Char(
        string="Default Insurance Tag",

    )

    @api.model
    def get_values(self):
        """Get the values from settings."""
        res = super(ResConfigSettings, self).get_values()
        icp_sudo = self.env['ir.config_parameter'].sudo()
        insurance_tag_setting = icp_sudo.get_param('res.config.settings.insurance_tag_setting')
        res.update(
            insurance_tag_setting=insurance_tag_setting,

        )
        return res

    def set_values(self):
        """Set the values. The new values are stored in the configuration parameters."""
        res = super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            'res.config.settings.insurance_tag_setting', self.insurance_tag_setting)
        return res
