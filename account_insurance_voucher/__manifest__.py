# -*- coding: utf-8 -*-
{
    'name': "Account Insurance Voucher",

    'summary': "Generate The Account Insurance Voucher for each invoices",

    'description': """ """,

    'category': 'Account',
    'version': '18.1',

    'depends': ['base','account','insurance_management'],

    'data': [
        'report/account_insurance_voucher_template.xml',
        'views/inherit_account_move_views.xml',
    ],
}

