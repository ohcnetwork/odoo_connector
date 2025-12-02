# -*- coding: utf-8 -*-
{
    'name': "Product Category Tax Configuration",

    'summary': "Product Category Tax Configuration",

    'description': """
Custom module extending product categories with configurable tax rules,
and adding custom business logic for accounting and stock-related operations.
    """,

    'category': 'Tools',
    'version': '1.0',

    'depends': [
        'base',
        'product',
        'account',
        'stock',
        'sale',
    ],

    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
    ],

    'demo': [
        'demo/demo.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}
