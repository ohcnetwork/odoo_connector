from odoo import fields, models

from ..memo_labels import care_reference_label, format_care_reference_memo


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    x_care_id = fields.Char(string='Care ID')
    location = fields.Many2one('bill.counter', string='Location')
    cancel_status = fields.Boolean(string="Cancelled", default=False)
    cashier = fields.Many2one('res.users', string='Cashier')
    bank_reference = fields.Char(
        string='Reference No',
        help='Reference (e.g. last 4 digits, UTR). Memo: "INV/…, CARD #2222" (type is uppercase: BANK, CASH, …).',
    )
    # Note: cash_session_id field is defined in cash_denomination module
    # to avoid circular dependency (cash.session model is defined there)


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    bank_reference = fields.Char(
        string='Reference No',
        help='Reference (e.g. last 4 digits, UTR). Memo: "INV/…, CARD #2222" (type is uppercase: BANK, CASH, …).',
    )

    def _create_payment_vals_from_wizard(self, batch_result):
        vals = super()._create_payment_vals_from_wizard(batch_result)
        if self.bank_reference:
            vals['bank_reference'] = self.bank_reference
            label = care_reference_label(
                journal_input=self.env.context.get('care_journal_input'),
                journal=self.journal_id,
                payment_method_line=self.payment_method_line_id,
            )
            ref_part = format_care_reference_memo(label, self.bank_reference)
            current_memo = vals.get('memo', '') or ''
            vals['memo'] = f"{current_memo}, {ref_part}" if current_memo else ref_part
        return vals