from odoo import models, fields, api
from odoo.exceptions import UserError


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
    journal_entry_id = fields.Many2one('account.move', string="Journal Entry", readonly=True)


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


    def action_approve(self):
        """
        Approve Cash Denomination and create Journal Entry
        """
        for rec in self:
            journal_model = self.env['account.journal']
            account_move_model = self.env['account.move']
            config = self.env['account.head.config'].search([], limit=1)
            if not config:
                raise UserError("Please configure the Cash Denomination Accounts.")

            debit_account = config.debit_account_id.id
            credit_account = config.credit_account_id.id

            if not debit_account or not credit_account:
                raise UserError("Debit and Credit accounts must be set in Cash Denomination Configuration.")

            amount = rec.grand_total

            if amount <= 0:
                raise UserError("Grand total must be greater than zero to create a Journal Entry.")

            journal_model = self.env['account.journal']
            journal = journal_model.search([('type', '=', 'general')], limit=1)

            if not journal:
               return {'error': 'Miscellaneous Journal not found'}

            move_vals = {
                'date': rec.date,
                'ref': f"Cash Denomination - {rec.user.name}",
                'journal_id': journal.id,   
                'line_ids': [
                    (0, 0, {
                        'account_id': debit_account,
                        'name': f"Cash Denomination by {rec.user.name}",
                        'debit': amount,
                        'credit': 0,
                    }),
                    (0, 0, {
                        'account_id': credit_account,
                        'name': f"Cash Denomination by {rec.user.name}",
                        'debit': 0,
                        'credit': amount,
                    }),
                ]
            }

            move = account_move_model.create(move_vals)
            move.action_post() 
            rec.journal_entry_id = move.id
            self.write({'state': 'approved'})


    def action_reject(self):
        for rec in self:
            account_move_model = self.env['account.move']
            config = self.env['account.head.config'].search([], limit=1)

            if not config:
                raise UserError("Please configure the Cash Denomination Accounts.")

            debit_account = config.debit_account_id.id
            credit_account = config.credit_account_id.id

            if not debit_account or not credit_account:
                raise UserError("Debit and Credit accounts must be set in Cash Denomination Configuration.")

            amount = rec.grand_total

            if amount <= 0:
                raise UserError("Grand total must be greater than zero to create a Journal Entry.")

            journal_model = self.env['account.journal']
            journal = journal_model.search([('type', '=', 'general')], limit=1)

            if not journal:
                return {'error': 'Miscellaneous Journal not found'}

            move_vals = {
                'date': rec.date,
                'ref': f"Cash Denomination - {rec.user.name}",
                'journal_id': journal.id,
                'line_ids': [
                    (0, 0, {
                        'account_id': debit_account,
                        'name': f"Cash Denomination by {rec.user.name}",
                        'debit': amount,
                        'credit': 0,
                    }),
                    (0, 0, {
                        'account_id': credit_account,
                        'name': f"Cash Denomination by {rec.user.name}",
                        'debit': 0,
                        'credit': amount,
                    }),
                ]
            }

            move = account_move_model.create(move_vals)
            rec.journal_entry_id = move.id
        self.write({'state': 'rejected'})
    
    def open_journal_entry(self):
        self.ensure_one()
        if not self.journal_entry_id:
            raise UserError("No Journal Entry linked to this record.")

        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entry',
            'res_model': 'account.move',
            'res_id': self.journal_entry_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_cash_transfers(self):
        self.ensure_one()

        transfers_model = self.env['cash.transfer']
        transfers = transfers_model.search([
            ('date', '=', self.date),
            ('from_user', '=', self.user.id),
            ('counter', '=', self.counter),
        ])

        if not transfers:
            raise UserError("No Cash Transfer records found for this denomination.")

        return {
            'type': 'ir.actions.act_window',
            'name': 'Cash Transfers',
            'res_model': 'cash.transfer',
            'view_mode': 'list,form',
            'domain': [
                ('date', '=', self.date),
                ('from_user', '=', self.user.id),
                ('counter', '=', self.counter),
            ],
            'target': 'current',
        }


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

