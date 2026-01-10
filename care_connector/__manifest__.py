{
    "name": "Open Helathcare Network Care Connector",
    "summary": "Integration with Care software to manage invoices and payments",
    "version": "0.0.1",
    "category": "Healthcare",
    "installable": True,
    "depends": ["base", "stock", "contacts", "account"],
    "external_dependencies": {
        "python": ["pydantic", "email-validator"],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/account_move_views.xml",
        "views/account_payment_views.xml",
        "views/account_journal_views.xml",
        "views/product_template_views.xml",
        "views/res_partner_views.xml",
        "views/product_category_views.xml",
        "views/bill_counter_views.xml",
    ],
}
