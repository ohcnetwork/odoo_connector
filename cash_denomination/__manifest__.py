{
    'name': "Care: Cash Session",
    'summary': "Cash Session Management",
    'description': """
        Cash Session Management System
        ==============================
        Track cash sessions, transfers, and variances.
        
        Features:
        - Cash session tracking (open/close)
        - Cash transfers between sessions
        - Variance tracking and resolution
        - Integration with Care system
    """,
    'category': 'Accounting',
    'version': '19.0.1.0.0',
    'depends': ['base', 'account', 'accountant', 'care_connector'],
    'data': [
        'security/ir.model.access.csv',
        'views/cash_transfer_views.xml',
        'views/cash_session_views.xml',
        'views/res_company_views.xml',
        'views/account_payment_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
