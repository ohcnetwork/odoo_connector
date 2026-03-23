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

    _sql_constraints = [
        (
            "x_care_payment_code_company_payment_type_uniq",
            "unique(company_id, payment_type, x_care_payment_code)",
            "Care Payment Code must be unique per company and payment type.",
        ),
    ]
