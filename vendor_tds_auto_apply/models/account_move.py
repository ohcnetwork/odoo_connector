from odoo import models, api, fields, _
from datetime import date

TDS_LIMIT = 5000000  # ₹50 lakhs


class AccountMove(models.Model):
    _inherit = "account.move"

    vendor_tds = fields.Float("TDS")

    def _get_financial_year_dates(self, ref_date=None):
        """
        Get the Indian financial year start and end dates.
        Indian FY runs from April 1 to March 31.
        """
        if ref_date is None:
            ref_date = date.today()
        
        if ref_date.month < 4:  # Before April - FY started previous year
            start_date = date(ref_date.year - 1, 4, 1)
            end_date = date(ref_date.year, 3, 31)
        else:  # April onwards - FY started this year
            start_date = date(ref_date.year, 4, 1)
            end_date = date(ref_date.year + 1, 3, 31)
        
        return start_date, end_date

    def action_post(self):
        res = super(AccountMove, self).action_post()
        for move in self:
            if move.move_type == 'in_invoice':
                account_move_tds = None
                partner = move.partner_id
                
                # Get financial year based on invoice date
                ref_date = move.invoice_date or date.today()
                start_date, end_date = self._get_financial_year_dates(ref_date)

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
                
                # Find applicable TDS rule - search for rules where limit is exceeded
                tds_model = self.env['tds']
                tds = tds_model.search([('limit', '<=', total_billed_amount)], order='limit desc', limit=1)

                if tds and tds.tds_tax and total_billed_amount > tds.limit:
                    if previous_bills_total > tds.limit:
                        # Previous bills already exceeded limit, TDS on full current bill
                        base_amount = move.amount_total
                    else:
                        # TDS only on the excess amount above the limit
                        base_amount = total_billed_amount - tds.limit

                    lines = [(tds.tds_tax, base_amount)]
                    account_move_tds = move._create_tds_entry(lines)
                    
                if account_move_tds:
                    tds_lines = account_move_tds.line_ids.filtered(lambda l: l.l10n_in_withhold_tax_amount)
                    total_tds_amount = sum(tds_lines.mapped('l10n_in_withhold_tax_amount'))
                    move.vendor_tds = total_tds_amount

        return res

    def _create_tds_entry(self, lines):
        """Create TDS withholding entry for the current move."""
        self.ensure_one()
        
        tds_wizard = self.env['l10n_in.withhold.wizard'].with_context(
            active_model='account.move', active_ids=self.ids
        ).create({
            'journal_id': self.env['account.journal'].search([
                ('company_id', '=', self.env.company.id),
                ('type', '=', 'general')
            ], limit=1).id,
            'date': self.invoice_date,
        })

        for tax, amount in lines:
            self.env['l10n_in.withhold.wizard.line'].create({
                'withhold_id': tds_wizard.id,
                'tax_id': tax.id,
                'base': amount,
            })

        return tds_wizard.action_create_and_post_withhold()