# -*- coding: utf-8 -*-
{
    'name': "Accounting Customisation",
    'summary': "Custom invoice tax detection and journal auto-selection",
    'description': """
This module enhances Odoo Accounting by:
- Adding booleans to detect taxed and untaxed invoices.
- Adding booleans on journals (Taxed / Untaxed Journal).
- Automatically selecting the correct journal based on invoice tax.
- Extending account.move and account.journal views.
    """,
    'category': 'Accounting/Accounting',
    'version': '1.0',
    'depends': [
        'base',
        'account',
    ],
    'data': [

        'security/ir.model.access.csv',
        'wizard/insurance_reject_wizard.xml',
        'views/insurance_company.xml',
        'views/customer_insurance_view.xml',
        'views/res_config_settings_views.xml',
        'views/account_views.xml',

    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
