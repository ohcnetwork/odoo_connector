{
    "name": "Account Discounts",
    "summary": "This module defines and manages predefined discounts used in bills",
    "version": "0.0.1",
    "category": "Accounting",
    "installable": True,
    "depends": ["base","account","web","insurance_management"],
    "data": [
        "security/ir.model.access.csv",
        "views/account_move_views.xml",
        "views/discount_groups_views.xml",
        "views/product_template_views.xml",
        "wizard/discount_category_report_wizard.xml",
    ],
}