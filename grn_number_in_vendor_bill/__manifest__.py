# -*- coding: utf-8 -*-
{
    'name': "GRN Number in Vendor Bill",
    'summary': "Auto-generate GRN numbers for Care vendor bills",
    'description': """
        Automatically generates sequential GRN numbers when posting vendor bills 
        that originate from the Care system (have x_care_id).
        
        GRN numbers are unique and consecutive within each financial year.
        Format: GRN/YYYY/0001, GRN/YYYY/0002, etc.
        
        Note: Only vendor bills with x_care_id will receive GRN numbers.
    """,
    'author': "Your Company",
    'category': 'Accounting',
    'version': '18.0.2.0.0',
    'license': 'LGPL-3',
    'depends': ['account', 'care_connector'],
    'data': [
        'data/ir_sequence_data.xml',
        'views/inherit_vendor_bill_views.xml',
    ],
}
