# -*- coding: utf-8 -*-
{
    'name': "Care: Vendor TDS Auto Apply",
    'summary': "If a vendor's total bills in a financial year exceed ₹50 lakhs, TDS applies to the excess amount",
    'description': "This module is automatically adding TDS to the vendor bill",
    'category': 'Accounting',
    'version': '19.0.1.0.0',
    'depends': ['base','account', 'l10n_in_withholding','report_xlsx'],
    'data': [
        'security/ir.model.access.csv',
        'report/report_action.xml',
        'wizard/tds_vendor_report_wizard.xml',
        'views/tds_records_view.xml',
        'views/account_move_views.xml',
    ],
}