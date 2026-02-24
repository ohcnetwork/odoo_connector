# -*- coding: utf-8 -*-
from odoo import models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _prepare_line_values(self, line, account, date, debit, credit):
        """Override to split journal entry lines per employee in batch mode.

        When 'Split by Employee in Batch' is enabled on the salary rule,
        this sets the employee's work contact as the partner and uses a
        unique name per employee so lines are not merged across employees.
        """
        res = super()._prepare_line_values(line, account, date, debit, credit)

        if line.salary_rule_id.split_by_employee:
            partner = self.employee_id.work_contact_id
            if partner:
                employee_name = self.employee_id.name or ''
                for line_vals in res:
                    line_vals['partner_id'] = partner.id
                    line_vals['name'] = f"{line.salary_rule_id.name} - {employee_name}"

        return res
