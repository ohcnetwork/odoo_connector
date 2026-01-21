from odoo import models, fields


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    x_care_journal_code = fields.Selection(
        selection=[
            ('cash', 'Cash'),
            ('bank', 'Bank'),
            ('card', 'Card'),
            ('credit', 'Credit'),
        ],
        string='Care Connector Code',
        help='Code used by Care Connector API to identify this journal for payments. '
             'Credit is used for Care of Accounts (charity/sponsor payments).',
    )
