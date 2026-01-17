# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Care: Sale Commission Line Level',
    'version': '19.0.1.1.0',
    'category': 'Sales/Commission',
    'summary': 'Allow multiple salespeople commissions per invoice at line level',
    'description': """
        Extends Odoo Enterprise Sale Commission module to support:
        - Assigning different salespeople to individual invoice lines
        - Multiple people earning commission on the same invoice
        - Commission calculation based on line-level salesperson instead of invoice-level
        - Shows invoice line amounts alongside commission in reports
        - Product information in achievement reports
    """,
    'depends': ['sale_commission', 'sale'],
    'data': [
        'views/account_move_views.xml',
        'views/achievement_report_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
