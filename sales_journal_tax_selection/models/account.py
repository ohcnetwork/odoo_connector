from odoo import models, fields, api


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    is_taxed_journal = fields.Boolean(
        string="Taxed Journal",
        help="Auto-select this journal for sales invoices with taxes.",
    )
    is_untaxed_journal = fields.Boolean(
        string="Untaxed Journal",
        help="Auto-select this journal for sales invoices without taxes.",
    )


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_taxed = fields.Boolean(compute="_compute_is_taxed", store=True)

    @api.depends('invoice_line_ids.tax_ids')
    def _compute_is_taxed(self):
        for move in self:
            move.is_taxed = any(line.tax_ids for line in move.invoice_line_ids)

    def _search_default_journal(self):
        """Override to select taxed/untaxed journal for sales invoices."""
        journal = super()._search_default_journal()
        
        # Only apply for sales invoices
        if self.move_type not in ('out_invoice', 'out_refund'):
            return journal

        # Find tax-specific journal
        domain = [
            ('company_id', '=', (self.company_id or self.env.company).id),
            ('type', '=', 'sale'),
        ]
        
        if self.is_taxed:
            tax_journal = self.env['account.journal'].search(
                domain + [('is_taxed_journal', '=', True)], limit=1
            )
        else:
            tax_journal = self.env['account.journal'].search(
                domain + [('is_untaxed_journal', '=', True)], limit=1
            )

        return tax_journal or journal
