from odoo import models, api, fields, _
from datetime import date


class AccountMove(models.Model):
    _inherit = "account.move"

    vendor_tds = fields.Float("TDS")


    def action_post(self):
        res = super(AccountMove, self).action_post()
        for move in self:
            if move.move_type == 'in_invoice':
                account_move_tds = None
                partner = move.partner_id
                today = date.today()
                start_date = date(today.year, 4, 1)
                end_date = date(today.year + 1, 3, 31)

                domain = [
                    ('move_type', '=', 'in_invoice'),
                    ('state', '=', 'posted'),
                    ('invoice_date', '>=', start_date),
                    ('invoice_date', '<=', end_date),
                    ('id', '!=', move.id),
                ]
                if partner.vat:
                    domain.append(('partner_id.vat', '=', partner.vat))
                else:
                    domain.append(('partner_id', '=', partner.id))
                previous_bills = self.search(domain)
                previous_bills_total = sum(previous_bills.mapped('amount_total'))
                total_billed_amount = previous_bills_total + move.amount_total
                tds_model = self.env['tds']
                tds = tds_model.search([('limit', '=', 5000000)], limit=1)

                if tds and total_billed_amount > tds.limit:
                    if previous_bills_total > tds.limit:
                        base_amount = move.amount_total
                    else:
                        base_amount = total_billed_amount - tds.limit

                    tds_tax = tds.tds_tax
                    lines = [(tds_tax, base_amount)]
                    account_move_tds = move._create_tds_entry(lines)
                if account_move_tds:
                    tds_lines = account_move_tds.line_ids.filtered(lambda l: l.l10n_in_withhold_tax_amount)
                    total_tds_amount = sum(tds_lines.mapped('l10n_in_withhold_tax_amount'))
                    move.vendor_tds = total_tds_amount

        return res

    def _create_tds_entry(self, lines):
        for move in self:
            tds_wizard = self.env['l10n_in.withhold.wizard'].with_context(
                active_model='account.move', active_ids=move.ids
            ).create({
                'journal_id': self.env['account.journal'].search([
                    ('company_id', '=', self.env.company.id),
                    ('type', '=', 'general')
                ], limit=1).id,
                'date': move.invoice_date,
            })

            for tax, amount in lines:
                self.env['l10n_in.withhold.wizard.line'].create({
                    'withhold_id': tds_wizard.id,
                    'tax_id': tax.id,
                    'base': amount,
                })

            account_move_tds = tds_wizard.action_create_and_post_withhold()
            return account_move_tds