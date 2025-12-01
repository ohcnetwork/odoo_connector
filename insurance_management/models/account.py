# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError, AccessError, RedirectWarning


class AccountMoveInherit(models.Model):
    _inherit='account.move'

    is_insurance = fields.Boolean(string="Is Insurance", compute="_compute_insurance_flag")
    insurance_tag=fields.Char(store=True)
    insurance_id=fields.Many2one('customer.insurance',store=True)


    @api.depends('insurance_tag')
    def _compute_insurance_flag(self):
        settings = self.env['res.config.settings'].sudo().get_values()
        setting_tag = settings.get('insurance_tag_setting')

        for move in self:
            move.is_insurance = (move.insurance_tag and move.insurance_tag == setting_tag)

class AccountMoveLineInherit(models.Model):
    _inherit='account.move.line'


    insurance_tag = fields.Char(store=True,related='move_id.insurance_tag')

