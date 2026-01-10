# -*- coding: utf-8 -*-
{
    'name': "Care: Partner Drug License",
    'summary': "Add Drug License Number field to partners",
    'description': """
        Adds a Drug License Number field to the partner (contact) form.
        Useful for pharmaceutical and healthcare businesses.
    """,
    'author': "Your Company",
    'category': 'Sales',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'views/res_partner_views.xml',
    ],
}
