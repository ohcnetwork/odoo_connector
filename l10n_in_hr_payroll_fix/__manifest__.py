# -*- coding: utf-8 -*-
{
    'name': "Care: India Payroll EPF Fix",
    'summary': "Fixes EPF report generation in India payroll",
    'description': """
        This module fixes the EPF (Employee Provident Fund) report generation issue
        in the India payroll extension where the employee search was using a non-stored
        computed field path that didn't work correctly.
        
        The fix changes the search domain to use:
        - Direct company path for provident fund setting
        - Stored employee PF amount field for filtering
    """,
    'category': 'Human Resources/Payroll',
    'version': '19.0.1.0.0',
    'depends': ['l10n_in_hr_payroll'],
    'data': [],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
