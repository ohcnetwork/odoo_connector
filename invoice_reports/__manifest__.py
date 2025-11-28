# -*- coding: utf-8 -*-
{
    'name': "Invoice Excel Report",
    'summary': "Generate detailed invoice reports in Excel format",
    'description': "This module allows users to generate and export invoice reports directly into Excel format",
    'category': 'Accounting',
    'version': '0.1',
    'depends': ['base','account',"l10n_in"],
    'data': [
        'security/ir.model.access.csv',
        'wizard/hsn_invoice_report_wizard.xml',
        'wizard/sales_invoice_report_wizard.xml',
        'wizard/purchase_bill_report_wizard.xml',       
        'wizard/general_ledger_report_wizard.xml',       
        'wizard/trial_balance_report_wizard.xml',       
        'wizard/partner_aging_report_wizard.xml',       
    ],
    
}
