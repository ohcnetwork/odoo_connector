# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Allow Public User as Salesperson',
    'version': '18.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Allow selecting public/portal users as salesperson (no extra license)',
    'depends': ['sale', 'sale_commission', 'account'],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
