from odoo import models, fields

class BillCounter(models.Model):
    _name = 'bill.counter'
    _description = 'Bill Counter'
    _rec_name = "bill_counter"
    _order = 'id desc'

    name = fields.Many2many('res.users',string='Cashier')
    bill_counter = fields.Char(string='Bill Counter',required=True)
    x_care_id = fields.Char(string='Care ID')