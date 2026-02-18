# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class AccountTrialBalanceReportHandler(models.AbstractModel):
    _inherit = "account.trial.balance.report.handler"

    @api.model
    def _display_single_column_for_initial_and_end_sections(self, options):
        """Override to always show separate Debit and Credit columns
        in Initial Balance and End Balance sections, instead of a
        single net Balance column.

        The standard Odoo behavior shows a single 'Balance' column when
        there is only one header level. This override forces Debit/Credit
        columns to always be displayed, matching the standard Indian
        accounting format for schedule-wise trial balance reports.
        """
        return False
