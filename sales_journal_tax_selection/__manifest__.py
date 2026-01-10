{
    'name': "Care: Sales Journal Tax Auto-Selection",
    'summary': "Auto-select sales journal based on invoice tax presence",
    'description': """
Automatically selects the appropriate sales journal based on whether 
the invoice contains taxes:

- Mark a journal as "Taxed Journal" for invoices with taxes
- Mark a journal as "Untaxed Journal" for invoices without taxes

Compatible with Odoo Enterprise.
    """,
    'category': 'Accounting/Accounting',
    'version': '19.0.1.0.0',
    'depends': [
        'account',
    ],
    'data': [
        'views/account_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
