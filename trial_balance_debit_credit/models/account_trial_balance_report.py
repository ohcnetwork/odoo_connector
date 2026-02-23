# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class AccountTrialBalanceReportHandler(models.AbstractModel):
    _inherit = "account.trial.balance.report.handler"

    def _custom_line_postprocessor(self, report, options, lines):
        """After standard processing, replace signed balance values in
        Initial Balance and End Balance columns with absolute values
        suffixed by 'Dr' or 'Cr'.

        Standard Odoo shows these as positive/negative numbers. This
        override formats them in the Indian accounting style:
            +500  → '500.00 Dr'
            -300  → '300.00 Cr'
        """
        lines = super()._custom_line_postprocessor(report, options, lines)

        for line in lines:
            for col in line['columns']:
                col_group = options['column_groups'][col['column_group_key']]
                col_type = col_group['forced_options'].get('trial_balance_column_type')

                if col_type not in ('initial_balance', 'end_balance'):
                    continue
                if col.get('expression_label') != 'balance':
                    continue

                value = col.get('no_format')
                if value is None or col.get('is_zero'):
                    continue

                formatted = report.format_value(
                    options,
                    abs(value),
                    col.get('figure_type'),
                    format_params=col.get('format_params'),
                )
                suffix = 'Dr' if value > 0 else 'Cr'
                col['name'] = f"{formatted} {suffix}"

        return lines
