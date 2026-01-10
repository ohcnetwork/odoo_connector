{
    "name": "Account Discounts",
    "summary": "Track discount groups on invoices using native Odoo discounts",
    "version": "18.0.2.0.0",
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
