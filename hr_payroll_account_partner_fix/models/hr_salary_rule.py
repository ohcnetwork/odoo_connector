# -*- coding: utf-8 -*-
from odoo import fields, models


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    split_by_employee = fields.Boolean(
        string="Split by Employee in Batch",
        default=False,
        help="When enabled, journal entry lines for this rule will be split "
             "per employee with the employee set as the partner, even when "
             "batch payroll move lines is active. Use this for deductions like "
             "Medical Bill, LIC, etc. that need to be tracked per employee.",
    )
