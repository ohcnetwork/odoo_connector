# Part of Odoo. See LICENSE file for full copyright and licensing details.

import calendar

from odoo import models


class L10nInHrPayrollEpfReport(models.Model):
    _inherit = 'l10n.in.hr.payroll.epf.report'

    def _get_employee_pf_data(self):
        """
        Override to fix the employee search domain.
        
        The original search used ('version_id.l10n_in_provident_fund', '=', True)
        which doesn't work correctly because:
        1. version_id on hr.employee is a computed non-stored field
        2. l10n_in_provident_fund on hr.version is a non-stored related field
        
        The fix uses:
        - company_id.l10n_in_provident_fund: direct path to company's stored field
        - l10n_in_pf_employee_amount: inherited stored field indicating PF is configured
        """
        self.ensure_one()
        # Get the relevant records based on the year and month
        indian_employees = self.env['hr.employee'].search([
            ('company_id', '=', self.company_id.id),
            ('company_id.l10n_in_provident_fund', '=', True),
            ('l10n_in_pf_employee_amount', '>', 0),
        ]).filtered(lambda e: e.company_country_code == 'IN')

        result = []
        end_date = calendar.monthrange(self.year, int(self.month))[1]

        payslips = self.env['hr.payslip'].search([
            ('employee_id', 'in', indian_employees.ids),
            ('date_from', '>=', f'{self.year}-{int(self.month):02d}-01'),
            ('date_to', '<=', f'{self.year}-{int(self.month):02d}-{end_date:02d}'),
            ('state', 'in', ('validated', 'paid'))
        ])

        if not payslips:
            return []

        payslip_line_values = payslips._get_line_values(['GROSS', 'BASIC', 'PF'])

        for employee in indian_employees:

            wage = 0
            epf = 0
            eps = 0
            epf_contri = 0

            payslip_ids = payslips.filtered(lambda p: p.employee_id == employee)

            if not payslip_ids:
                continue

            for payslip in payslip_ids:
                pf_value = payslip_line_values['PF'][payslip.id]['total']
                if pf_value == 0:
                    continue

                epf_contri -= pf_value
                wage += payslip_line_values['GROSS'][payslip.id]['total']
                epf += payslip_line_values['BASIC'][payslip.id]['total']

            # Skip the employee if there are no valid PF contributions
            if epf_contri == 0:
                continue

            # Calculate contributions and differences
            eps = min(payslip_ids[0]._rule_parameter('l10n_in_pf_amount'), epf)
            eps_contri = round(eps * payslip_ids[0]._rule_parameter('l10n_in_eps_contri_percent'), 2)
            diff = round(epf_contri - eps_contri, 2)

            result.append((
                employee.l10n_in_uan or '',
                employee.name,
                wage,
                epf,
                eps,
                eps,
                epf_contri,
                eps_contri,
                diff,
                0, 0,
            ))

        return result
