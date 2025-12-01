{
    'name': "cash_denomination",
    'summary': "Cash Denomination",
    'description': "Cash Denomination",
    'category': 'Website',
    'version': '0.1',
    'depends': ['base','account','website','care_connector'],
    'data': [
        'security/ir.model.access.csv',
        #
        # 'views/cash_transfer_views.xml',
        'views/cash_transfer_views.xml',
        # 'views/petty_cash.xml',
        'template/cash_denomination_template.xml',
        # 'views/portal_cash_denomination_templates.xml',
        'views/account_payment_views.xml', 
        'views/cash_denomination_views.xml',
        'views/account_head_config_views.xml',
    ],
    'assets': {
            'web.assets_frontend': [
                'cash_denomination/static/src/js/cash_denomination_events.js',
                # 'cash_denomination/static/src/js/cash_denomintaion_search.js',
                # 'cash_denomination/static/src/xml/cash_denomintaion_search.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}