# -*- coding: utf-8 -*-
{
    "name": "Care: GST Register Suite",
    "summary": "Single addon for purchase, sales, purchase return and sales return GST registers",
    "description": "One plugin containing all four GST register reports with dynamic GST slabs.",
    "author": "SSMM Hospital",
    "license": "LGPL-3",
    "category": "Accounting",
    "version": "19.0.1.0.0",
    "depends": ["base", "account"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/purchase_register_wizard_views.xml",
        "wizard/sales_register_wizard_views.xml",
        "wizard/purchase_return_register_wizard_views.xml",
        "wizard/sales_return_register_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
