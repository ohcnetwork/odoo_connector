# -*- coding: utf-8 -*-
{
    'name': "vendor_bill_auto_number",
    'summary': "Vendor Bill Auto Number System",
    'description': "Generating auto number while creation of the each vendor bill",
    'category': 'Accounting',
    'version': '0.1',
    'depends': ['base','account'],
    'data': [
        'security/ir.model.access.csv', 
        'views/inherit_vendor_bill_views.xml',
        'views/inherit_res_settings_view.xml',
        
    ],
}