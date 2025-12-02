from odoo import models, fields

class TDSModel(models.Model):
    _name = 'tds'
    _description = 'TDS Records'

    name = fields.Char(string="TDS Name", required=True)
    limit = fields.Float(string="TDS Limit", required=True)
    tds_tax = fields.Many2one(comodel_name='account.tax',string="TDS Tax",required=True,)