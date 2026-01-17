# -*- coding: utf-8 -*-
{
    "name": "Care Sponsor",
    "summary": "Corporate Sponsor Management for Care of Company Invoicing",
    "description": """
        Manage corporate sponsors who pay on behalf of customers:
        - Create and manage sponsor companies with contact details
        - Assign sponsors to invoices
        - Track invoices per sponsor company
        - Automatic receivable account assignment
    """,
    "version": "19.0.1.0.0",
    "category": "Accounting",
    "author": "Care",
    "license": "LGPL-3",
    "depends": ["base", "account", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/sponsor_company_views.xml",
        "views/account_move_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}

