from odoo import models, fields, api

class CashDenomination(models.Model):
    _name = 'cash.denomination'  
    _description = 'Cash Denomination' 
    _rec_name = "user"
    _order = 'id desc'

    date = fields.Date(string='Date', readonly=True)
    user = fields.Many2one('res.users',string='Person',readonly=True)
    counter = fields.Char(string='Counter',readonly=True)
    line_ids = fields.One2many('cash.denomination.line', 'denomination_id', string='Denomination Lines',readonly=True)
    grand_total = fields.Float(string='Total', compute='_comput_grand_total', store=True)
    transfer_line_ids = fields.One2many('cash.denomination.transfer.line', 'denomination_id', string='Cash Transfer Lines', readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)

    transfer_total = fields.Float(string='Transfer Total', compute='_compute_transfer_total')
    remark = fields.Text(string="Remark")
    
    @api.depends('transfer_line_ids.sub_total')
    def _compute_transfer_total(self):
        for rec in self:
            rec.transfer_total = sum(rec.transfer_line_ids.mapped('sub_total'))

    @api.depends('line_ids.sub_total')
    def _comput_grand_total(self):
        for record in self:
            self.grand_total=sum(record.line_ids.mapped('sub_total'))

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_reject(self):
        self.write({'state': 'rejected'})


class CashDenominationLine(models.Model):
    _name = 'cash.denomination.line'
    _description = 'Cash Denomination Line'

    denomination_id = fields.Many2one('cash.denomination', string='Cash Denomination', ondelete='cascade')
    counts = fields.Integer(string='Counts', required=True,readonly=True)
    currency = fields.Selection(
        [('1','1'),('2','2'),('5','5'),('10','10'),('20','20'),('50','50'),('100','100'),('200','200'),('500','500')],
        string='Currency', required=True,readonly=True)
    sub_total = fields.Float(string='Sub Total', compute='_compute_sub_total', store=True,readonly=True)

    
    @api.depends('counts', 'currency')
    def _compute_sub_total(self):
        for line in self:
            line.sub_total = line.counts * int(line.currency)



class CashDenominationTransferLine(models.Model):
    _name = 'cash.denomination.transfer.line'
    _description = 'Cash Denomination Transfer Line'

    denomination_id = fields.Many2one('cash.denomination', string='Cash Denomination', ondelete='cascade')

    to_counter = fields.Many2one('bill.counter', string='To Counter', readonly=True)
    counts = fields.Integer(string='Counts', readonly=True)
    currency = fields.Selection(
        [('1','1'),('2','2'),('5','5'),('10','10'),('20','20'),('50','50'),('100','100'),('200','200'),('500','500')],
        string='Currency', readonly=True
    )
    sub_total = fields.Float(string='Total', compute='_compute_total', store=True, readonly=True)

    @api.depends('counts', 'currency')
    def _compute_total(self):
        for rec in self:
            rec.sub_total = rec.counts * int(rec.currency)

