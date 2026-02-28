import os
from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = "hr.employee"

    x_care_id = fields.Char(string="Care ID")