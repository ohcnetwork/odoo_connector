{
    "name": "SSMM Bank Reconciliantion",
    "summary": "This module is creating bank reconciliantion records",
    "version": "0.0.1",
    "category": "Accounting",
    "installable": True,
    "depends": ["base","account"],
    "data": [
        "security/ir.model.access.csv",
        "views/bank_reconciliantion_views.xml",
        "views/account_move_views.xml",
        "wizard/bank_reconciliation_report_wizard_views.xml",
    ],
}