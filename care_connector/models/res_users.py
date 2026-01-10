# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    # External ID for integration with external systems (e.g., Care)
    x_care_id = fields.Char(
        string='Care ID',
        index=True,
        help='External identifier from Care system for commission tracking',
    )
