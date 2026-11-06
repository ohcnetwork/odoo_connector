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
        # Use active_test=False to include archived/terminated employees
        # who still have valid payslips for the period
        indian_employees = self.env['hr.employee'].with_context(active_test=False).search([
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

        payslip_line_values = payslips._get_line_values(['GROSS', 'PF', 'PFE'])

        for employee in indian_employees:

            payslip_ids = payslips.filtered(lambda p: p.employee_id == employee)

            if not payslip_ids:
                continue

            # 1. Gross - Pull from the latest month payslip with a cap of 25,000
            raw_gross = sum(
                payslip_line_values['GROSS'][p.id]['total'] for p in payslip_ids
            )
            gross = min(raw_gross, 25000)

            # 2. EPF Wages - Gross with a cap of 15,000
            epf_wages = min(gross, 15000)

            # 3. EPS Wages - Gross with a cap of 15,000
            eps_wages = min(gross, 15000)

            # 4. EDLI Wages - Gross with a cap of 15,000
            edli_wages = min(gross, 15000)

            # 5. EPF Contri Remitted - Pull from the latest month employee contribution
            epf_contri = sum(
                payslip_line_values['PF'][p.id]['total'] for p in payslip_ids
            )

            # Skip the employee if there are no valid PF contributions
            if epf_contri == 0:
                continue

            # 6. EPS Contri Remitted - 8.33% of EPS Wages, rounded to int
            eps_contri = round(eps_wages * 0.0833)

            # 7. EPF-EPS Diff Remitted - Employer contribution from payslip minus EPS contri
            employer_pf = abs(sum(
                payslip_line_values['PFE'][p.id]['total'] for p in payslip_ids
            ))
            epf_eps_diff = round(employer_pf - eps_contri)

            # 8. NCP Days - Total days in period minus (worked days + paid leave)
            paid_codes = ['WORK100', 'LEAVE105', 'LEAVE110', 'LEAVE120', 'LEAVE140']
            total_days = sum(
                wd.number_of_days
                for p in payslip_ids
                for wd in p.worked_days_line_ids
            )
            paid_days = sum(
                wd.number_of_days
                for p in payslip_ids
                for wd in p.worked_days_line_ids
                if wd.code in paid_codes
            )
            ncp_days = total_days - paid_days

            result.append((
                employee.l10n_in_uan or '',
                employee.name,
                gross,
                epf_wages,
                eps_wages,
                edli_wages,
                epf_contri,
                eps_contri,
                epf_eps_diff,
                ncp_days, 0,
            ))

        return result
