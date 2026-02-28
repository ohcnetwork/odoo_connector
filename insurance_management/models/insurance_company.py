from odoo import models, fields

class InsuranceCompany(models.Model):
    _name = 'insurance.company'
    _description = 'Insurance Company'

    name = fields.Char(string="Insurance Company Name", required=True)
    code = fields.Char(string="Code")
    description = fields.Text(string="Description")
    account_id=fields.Many2one('account.account')