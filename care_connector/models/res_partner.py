from odoo import fields, models, api


class ResPartner(models.Model):
    """Inheriting res.partner"""

    _inherit = "res.partner"

    x_care_id = fields.Char(string="Care Partner ID")
    x_care_id_type = fields.Selection(
        [("user", "User"), ("vendor", "Vendor")],
        string="Care ID Type",
        help="Indicates whether this Care ID belongs to a User or Vendor",
    )
    x_care_url = fields.Char(
        string="Care URL",
        compute="_compute_care_url",
        store=False,
    )

    @api.depends('x_care_id', 'x_care_id_type')
    def _compute_care_url(self):
        """Compute the Care URL based on care_id and care_id_type."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('care.base_url', default='')
        for record in self:
            if record.x_care_id and base_url:
                # URL pattern for users and vendors - placeholder paths
                if record.x_care_id_type == 'user':
                    record.x_care_url = f"{base_url}/users/{record.x_care_id}"
                elif record.x_care_id_type == 'vendor':
                    record.x_care_url = f"{base_url}/vendors/{record.x_care_id}"
                else:
                    # Default to user if type is not set
                    record.x_care_url = f"{base_url}/users/{record.x_care_id}"
            else:
                record.x_care_url = False

