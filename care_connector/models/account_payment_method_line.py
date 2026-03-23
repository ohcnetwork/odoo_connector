from odoo import models, fields


class AccountPaymentMethodLine(models.Model):
    _inherit = "account.payment.method.line"

    x_care_payment_code = fields.Selection(
        selection=[
            ("card", "Card"),
            ("debit", "Debit"),
        ],
        string="Care Payment Code",
        help="Code used by Care Connector API to identify this payment method. "
        "When set, the API can route payments to this journal's payment method line "
        "using the same journal_input field (e.g. 'card' or 'debit').",
    )
