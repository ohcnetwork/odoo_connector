# -*- coding: utf-8 -*-
{
    "name": "Care Insurance",
    "summary": "Hospital Insurance Claim Management",
    "description": """
        Manage hospital insurance claims with proper workflow:
        - Create insurance claims linked to customer invoices
        - Track claim approval and reconciliation
        - Generate insurance voucher reports
    """,
    "version": "19.0.1.0.0",
    "category": "Accounting",
    "author": "Care",
    "license": "LGPL-3",
    "depends": ["base", "account", "mail", "care_connector"],
    "data": [
        # Security
        "security/insurance_security.xml",
        "security/ir.model.access.csv",
        # Data
        "data/ir_sequence_data.xml",
        # Wizard
        "wizard/insurance_reject_wizard_views.xml",
        # Views (claim first - it defines root menu)
        "views/insurance_claim_views.xml",
        "views/insurance_company_views.xml",
        "views/account_move_views.xml",
        "views/res_config_settings_views.xml",
        # Reports
        "report/insurance_voucher_report.xml",
        "report/insurance_voucher_template.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}

