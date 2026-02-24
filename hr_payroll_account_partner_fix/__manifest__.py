# -*- coding: utf-8 -*-
{
    'name': "Care: Payslip Journal Entry Partner Fix",
    'summary': "Splits payslip journal entry lines per employee for selected salary rules",
    'description': """
        Adds a 'Split by Employee in Batch' checkbox on salary rules. When enabled,
        journal entry lines for that rule will be created separately per employee
        (with the employee as partner) even when 'Batch Payroll Move Lines' is
        active at the company level.

        This is useful for deductions like Medical Bill, LIC, Hostel Rent, etc.
        that need to be tracked per employee in the journal entry.

        This is independent of the existing 'Set employee on account line' flag,
        which Odoo uses internally for payment registration on the NET salary rule.
    """,
    'category': 'Human Resources/Payroll',
    'version': '19.0.1.0.0',
    'depends': ['hr_payroll_account'],
    'data': [
        'views/hr_salary_rule_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
