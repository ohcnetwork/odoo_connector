from odoo import models, fields, api

class CashTransfer(models.Model):
    _name = 'cash.transfer'
    _description = 'Cash Transfer'
    _rec_name = "from_user"
    _order = 'id desc'

    date = fields.Date(string='Date', readonly=True)
    from_user = fields.Many2one('res.users', string='From User', readonly=True)
    to_user = fields.Many2one('bill.counter', string='To Counter', readonly=True)
    counter = fields.Many2one('bill.counter', string='From Counter', readonly=True)
    line_ids = fields.One2many('cash.transfer.line', 'transfer_id', string='Denomination Lines')
    grand_total = fields.Float(string='Total', compute='_compute_grand_total', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ], default='draft')
    
    is_counted = fields.Boolean(default=False)

    @api.depends('line_ids.sub_total')
    def _compute_grand_total(self):
        for rec in self:
            rec.grand_total = sum(rec.line_ids.mapped('sub_total'))


class CashTransferLine(models.Model):
    _name = 'cash.transfer.line'
    _description = 'Cash Transfer Line'

    transfer_id = fields.Many2one('cash.transfer', ondelete='cascade')
    counts = fields.Integer(string='Counts', required=True)
    currency = fields.Selection(
        [('1','1'),('2','2'),('5','5'),('10','10'),('20','20'),('50','50'),('100','100'),('200','200'),('500','500')],
        required=True)
    sub_total = fields.Float(compute='_compute_sub_total', store=True)

    @api.depends('counts', 'currency')
    def _compute_sub_total(self):
        for line in self:
            line.sub_total = line.counts * int(line.currency)
