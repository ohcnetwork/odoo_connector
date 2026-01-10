{
    "name": "Care: Account Discounts",
    "summary": "Track discount groups on invoices using native Odoo discounts",
    "version": "19.0.1.0.0",
    "category": "Accounting",
    "license": "LGPL-3",
    "author": "Custom",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "views/discount_group_views.xml",
        "views/account_move_views.xml",
    ],
    "installable": True,
}
