# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError, AccessError, RedirectWarning


class AccountMoveInherit(models.Model):
    _inherit='account.move'



    taxed_invoice = fields.Boolean(compute="_compute_tax_flags", store=True)
    untaxed_invoice = fields.Boolean(compute="_compute_tax_flags", store=True)
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        compute='_compute_journal_id', readonly=False,
        required=True,
        check_company=True,
        domain="[('id', 'in', suitable_journal_ids)]",
    )

    @api.depends('move_type', 'origin_payment_id', 'statement_line_id','taxed_invoice','untaxed_invoice','invoice_line_ids')
    def _compute_journal_id(self):
        for move in self:
            move.journal_id = move._search_default_journal()


    def _search_default_journal(self):
        if self.statement_line_ids.statement_id.journal_id:
            return self.statement_line_ids.statement_id.journal_id[:1]
        journal_types = self._get_valid_journal_types()
        company = self.company_id or self.env.company
        domain = [
            *self.env['account.journal']._check_company_domain(company),
            ('type', 'in', journal_types),
        ]
        if 'sale' in journal_types:
            if self.untaxed_invoice:
                domain += [('is_untaxed_journal', '=', True)]

            else:
                domain += [('is_taxed_journal', '=', True)]
        journal = None
        # the currency is not a hard dependence, it triggers via manual add_to_compute
        # avoid computing the currency before all it's dependences are set (like the journal...)
        if self.env.cache.contains(self, self._fields['currency_id']):
            currency_id = self.currency_id.id or self._context.get('default_currency_id')
            if currency_id and currency_id != company.currency_id.id:

                currency_domain = domain + [('currency_id', '=', currency_id)]



                journal = self.env['account.journal'].search(currency_domain, limit=1)

        if not journal:
            journal = self.env['account.journal'].search(domain, limit=1)
        if not journal:
            error_msg = self.env['account.journal']._build_no_journal_error_msg(company.display_name, journal_types)
            raise UserError(error_msg)
        return journal



    @api.depends('line_ids.tax_ids')
    def _compute_tax_flags(self):
        for move in self:

            has_tax = any(
                any(tax.amount > 0 for tax in line.tax_ids)
                for line in move.line_ids
            )

            move.taxed_invoice = has_tax
            move.untaxed_invoice = not has_tax



class AccountJournalInherit(models.Model):
    _inherit = 'account.journal'

    is_taxed_journal = fields.Boolean(string="Taxed Journal",tracking=True)
    is_untaxed_journal = fields.Boolean(string="Untaxed Journal",tracking=True)




