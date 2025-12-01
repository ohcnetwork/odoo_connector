from odoo import models, fields, api
from datetime import date

class BankReconciliation(models.Model):
    _name = 'ssmm.bank.reconciliation'
    _description = 'Bank Reconciliation'

    name = fields.Char(string="Reconciliation Name", required=True)
    date_from = fields.Date(string="Date From", required=True)
    date_to = fields.Date(string="Date To", required=True)
    bank_cash_type = fields.Selection([
        ('bank', 'Bank'),
        ('cash', 'Cash'),
    ], string="Bank/Cash Type",default='bank',store=True)
    account_id = fields.Many2one('account.account',string='Bank',required=True, domain=[('account_type', '=', 'asset_cash'),('bank_cash_type', '=','bank')])
    br_line_ids = fields.One2many('reconciliation.line','reconciliation_id',string="Reconciliation Lines")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('reconciled', 'Reconciled'),
    ], string='Status', default='draft', tracking=True)
    options = fields.Selection([
        ('reconciled','Reconciled'),
        ('unreconciled','Unreconciled'),
        ('both','Both')
    ],string='Reconcile Options',tracking=True)
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )

    total_debit = fields.Monetary(
        string="Total Debit",
        currency_field='currency_id',
        compute="_compute_totals",

    )

    total_credit = fields.Monetary(
        string="Total Credit",
        currency_field='currency_id',
        compute="_compute_totals",

    )

    total_company_balance = fields.Monetary(
        string="Balance as per Company Book",
        currency_field='currency_id',
        compute="_compute_total_company_balance",

    )

    no_reconcile_amount = fields.Monetary(
        string="Amount Not Reflected in Bank",
        currency_field='currency_id',
        compute="_compute_no_reconcile_amount",

    )

    bank_reconcile_amount_total = fields.Monetary(
        string="Balance as per Bank",
        currency_field='currency_id',
        compute="_compute_bank_reconcile_amount_total",

    )

    @api.depends('br_line_ids.debit', 'br_line_ids.credit')
    def _compute_totals(self):
        for rec in self:
            rec.total_debit = sum(rec.br_line_ids.mapped('debit'))
            rec.total_credit = sum(rec.br_line_ids.mapped('credit'))



    @api.depends('date_to','account_id')
    def _compute_total_company_balance(self):
        for rec in self:
            domain = [

                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
                ('account_id', '=', self.account_id.id),
                ('move_id.state', '=', 'posted'),
            ]

            move_lines = self.env['account.move.line'].search(domain)
            rec.total_company_balance = sum(move_lines.mapped('balance')) if move_lines else 0


    @api.depends('date_to', 'account_id')
    def _compute_no_reconcile_amount(self):
        for rec in self:
            domain = [

                ('date', '<=', self.date_to),
                ('account_id', '=', self.account_id.id),
                ('move_id.state', '=', 'posted'),
                ('reconcile_date', '=', False)
            ]
            move_lines = self.env['account.move.line'].search(domain)
            rec.no_reconcile_amount = sum(move_lines.mapped('balance')) if move_lines else 0

    @api.depends('date_to', 'account_id')
    def _compute_bank_reconcile_amount_total(self):
        for rec in self:
            domain = [

                ('date', '<=', self.date_to),
                ('account_id', '=', self.account_id.id),
                ('move_id.state', '=', 'posted'),
                ('reconcile_date', '!=', False)
            ]
            move_lines = self.env['account.move.line'].search(domain)
            rec.bank_reconcile_amount_total = sum(move_lines.mapped('balance')) if move_lines else 0



    @api.onchange("options","date_from","date_to")
    def onchange_options(self):
        print("---option")
        if not (self.date_from and self.date_to and self.account_id):
            self.br_line_ids = [(5, 0, 0)]  # clear lines
            return

        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('account_id', '=', self.account_id.id),
            ('move_id.state', '=', 'posted'),
        ]

        if self.options == 'reconciled':
            domain.append(('reconcile_date', '!=', False))

        elif self.options == 'unreconciled':
            domain.append(('reconcile_date', '=', False))

        move_lines = self.env['account.move.line'].search(domain)
        print("move ;ines",move_lines)
        self.br_line_ids = [(5, 0, 0)]
        vals = []
        for line in move_lines:
            vals.append((0, 0, {
                'date': line.date,
                'move_name': line.move_id.name,
                'move_line_id':line.id,
                'partner_id': line.partner_id.id,
                'label': line.name,
                'debit': line.debit,
                'credit': line.credit,
                'reconcile_date': line.reconcile_date,
            }))

        self.br_line_ids = vals



    def action_reconcile(self):
        for rec in self:
            for br_line in rec.br_line_ids:
                br_line.move_line_id.write({'reconcile_date': br_line.reconcile_date})
            rec.state = 'reconciled'

        return True

    def action_draft(self):
        self.write({'state': 'draft'})


class ReconciliationLine(models.Model):
    _name = 'reconciliation.line'
    _description = 'Bank Reconciliation Line'

    reconciliation_id = fields.Many2one('ssmm.bank.reconciliation', string="Reconciliation")
    date = fields.Date(string="Date")
    move_name = fields.Char(string="Entry Name")
    move_line_id = fields.Many2one('account.move.line',string="Moveline")
    partner_id = fields.Many2one('res.partner',string="Partner")
    label = fields.Char(string="Label")
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )
    debit = fields.Monetary(string='Debit', currency_field='currency_id')
    credit = fields.Monetary(string='Credit', currency_field='currency_id')
    reconcile_date = fields.Date(string="Reconciliation Date")



class AccountMoveLines(models.Model):
    _inherit = 'account.move.line'

    reconcile_date = fields.Date(string="Reconcile Date")