from odoo import models, fields


class AccountJournal(models.Model):
    _inherit = "account.journal"

    x_care_journal_code = fields.Selection(
        selection=[
            ("cash", "Cash"),
            ("bank", "Bank"),
            ("credit", "Credit"),
        ],
        string="Care Connector Code",
        help="Code used by Care Connector API to identify this journal for payments. "
        "Credit is used for Care of Accounts (charity/sponsor payments). "
        "Card and Debit are configured as payment method lines on the Bank journal "
        "using the 'Care Payment Code' field.",
    )
