# -*- coding: utf-8 -*-
{
    'name': "Insurance Management",
    'summary': "Customer Insurance Management",
    'description': """
    """,
    'category': 'Accounting',
    'version': '1.0',
    'depends': [
        'base','account',],
    'data': [

        'security/ir.model.access.csv',
        'wizard/insurance_reject_wizard.xml',
        'views/insurance_company.xml',
        'views/customer_insurance_view.xml',
        'views/res_config_settings_views.xml',
        'views/account_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
