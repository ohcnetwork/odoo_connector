# -*- coding: utf-8 -*-
{
    'name': "Partner Ledger Excel Report",
    'summary': "Generate detailed partner ledger reports in Excel format",
    'description': "This module allows users to generate and export Partner Ledger reports directly into Excel format",
    'category': 'Accounting',
    'version': '0.1',
    'depends': ['base','account','base_accounting_kit','invoice_reports'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/partner_ledger_report_wizard.xml',
        
    ],
    
}