{
    "name": "Care Connector",
    "summary": "Integration with OHC software",
    "version": "0.0.1",
    "category": "Uncategorized",
    "installable": True,
    "depends": ["base", "stock", "web", "contacts", "account","hr"],
    "external_dependencies": {
        "python": ["pydantic", "email-validator"],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/account_move_views.xml",
        "views/account_payment_views.xml",
        "views/product_template_views.xml",
        "views/res_partner_views.xml",
        "views/product_category_views.xml",
        "views/bill_counter_views.xml",
        "views/hr_employee_views.xml",
    ],
}
