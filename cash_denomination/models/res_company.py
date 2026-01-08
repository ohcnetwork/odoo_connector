from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    counter_cash_journal_id = fields.Many2one(
        'account.journal',
        string='Counter Cash Journal',
        domain=[('type', '=', 'cash')],
        help='Cash journal for counter collections. Its default account is the Counter Cash Account.'
    )
    main_cash_journal_id = fields.Many2one(
        'account.journal',
        string='Main Cash Journal',
        domain=[('type', '=', 'cash')],
        help='Cash journal for main cash operations. Its default account is the Main Cash Account.'
    )
