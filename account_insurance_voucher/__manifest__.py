# -*- coding: utf-8 -*-
{
    'name': "Care: Account Insurance Voucher",

    'summary': "Generate The Account Insurance Voucher for each invoices",

    'description': """ """,

    'category': 'Account',
    'version': '19.0.1.0.0',

    'depends': ['base','account','insurance_management'],

    'data': [
        'report/account_insurance_voucher_template.xml',
        'views/inherit_account_move_views.xml',
    ],
}

