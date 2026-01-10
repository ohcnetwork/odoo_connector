# -*- coding: utf-8 -*-
{
    'name': "Care: Payment Voucher",

    'summary': "Generate The Payment Voucher for each Payments",

    'description': """ """,

    'category': 'Account',
    'version': '19.0.1.0.0',

    'depends': ['base','account'],

    'data': [
        'report/payment_voucher_template.xml',
        'views/inherit_account_payment_views.xml',
    ],
}

