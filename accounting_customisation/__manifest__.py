# -*- coding: utf-8 -*-
{
    'name': "Accounting Customisation",
    'summary': "Tax-based sales journal selection and OCA report defaults",
    'description': """
- Auto-selects sales journal based on tax presence (Taxed/Untaxed Journal)
- Sets Miscellaneous as default in OCA Journal Ledger report
    """,
    'category': 'Accounting/Accounting',
    'version': '18.0.1.0.0',
    'depends': [
        'account',
        'account_financial_report',
    ],
    'data': [
        'views/account_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
