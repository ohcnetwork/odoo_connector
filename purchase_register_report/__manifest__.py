# -*- coding: utf-8 -*-
{
    "name": "Care: Purchase Register Report",
    "summary": "Hospital-ready purchase register XLSX export with GST buckets",
    "description": "Exports a purchase register in GST bucket format (0/5/12/18/28).",
    "author": "SSMM Hospital",
    "license": "LGPL-3",
    "category": "Accounting",
    "version": "19.0.1.0.0",
    "depends": ["base", "account"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/purchase_register_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
