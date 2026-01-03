{
    'name': "Cash Denomination",
    'summary': "Cash Denomination and Transfer Management",
    'description': """
        Cash Denomination Module
        ========================
        
        This module provides:
        - Cash denomination entry for cashiers at counters
        - Cash transfer between counters
        - Approval workflow for denominations
        - Automatic journal entry creation on approval
        - Pending amount tracking
        
        Features:
        - Track payments received by cashiers
        - Record cash counts by denomination (₹1 to ₹2000)
        - Transfer cash between counters with tracking
        - Accept/reject incoming transfers
        - Manager approval workflow
        - Automatic accounting entries
    """,
    'category': 'Accounting/Accounting',
    'version': '18.0.1.0.0',
    'author': 'Your Company',
    'depends': ['base', 'account', 'website', 'mail', 'care_connector'],
    'data': [
        # Security first
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        # Data
        'data/ir_sequence.xml',
        # Views
        'views/cash_transfer_views.xml',
        'views/account_payment_views.xml',
        'views/cash_denomination_views.xml',
        'views/account_head_config_views.xml',
        # Templates
        'template/cash_denomination_template.xml',
        'template/denomination_register_template.xml',
        'template/payment_transaction_template.xml',
        'template/denomination_history_menu.xml',
        'template/pending_cash_transfer.xml',
        'template/cash_accept_template.xml',
        # Wizards
        'wizard/cash_denomination_reject_reason_wizard.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'cash_denomination/static/src/css/website_service.css',
            'cash_denomination/static/src/js/cash_denomination_events.js',
            'cash_denomination/static/src/js/cash_denomination_register.js',
            'cash_denomination/static/src/js/payment_transaction.js',
            'cash_denomination/static/src/js/pending_cash_transfer.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}
