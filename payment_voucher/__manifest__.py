# -*- coding: utf-8 -*-
{
    'name': "Payment Voucher",

    'summary': "Generate The Payment Voucher for each Payments",

    'description': """ """,

    'category': 'Account',
    'version': '18.1',

    'depends': ['base','account'],

    'data': [
        'report/payment_voucher_template.xml',
        'views/inherit_account_payment_views.xml',
    ],
}

