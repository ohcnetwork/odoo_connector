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
        'views/account_views.xml',

    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
