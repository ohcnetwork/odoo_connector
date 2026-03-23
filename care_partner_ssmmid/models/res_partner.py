from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.depends('name', 'ref')
    def _compute_display_name(self):
        for partner in self:
            if partner.ref:
                partner.display_name = f"{partner.name} ({partner.ref})"
            else:
                partner.display_name = partner.name
