# -*- coding: utf-8 -*-

from odoo import models, fields, api


class JournalLedgerReportWizard(models.TransientModel):
    _inherit = 'journal.ledger.report.wizard'

    @api.model
    def _default_journal_ids(self):
        """Default to Miscellaneous (general) type journals"""
        return self.env['account.journal'].search([('type', '=', 'general')])

    journal_ids = fields.Many2many(
        default=_default_journal_ids
    )
