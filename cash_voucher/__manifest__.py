# -*- coding: utf-8 -*-
{
    'name': "Care: Cash Voucher",

    'summary': "Generate printable Cash Vouchers for cash payments and receipts",

    'description': """
        This module provides a printable Cash Voucher format for:
        - Cash Receipts (inbound payments)
        - Cash Payments (outbound payments)
        
        Features:
        - Professional voucher layout with company details
        - Amount in words
        - Dr/Cr notation
        - Signature sections for authorization
        - Reconciled invoice/bill references
    """,

    'author': "Care",
    'category': 'Accounting',
    'version': '19.0.1.0.0',

    'depends': ['base', 'account'],

    'data': [
        'report/cash_voucher_report.xml',
        'report/cash_voucher_template.xml',
        'report/cash_voucher_move_template.xml',
        'views/account_payment_views.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}
