from odoo import fields, models, api


class AccountPayment(models.Model):
    _inherit = 'account.payment'


    def action_post(self):
        res = super(AccountPayment, self).action_post()

        for payment in self:
            if payment.partner_type == 'customer':
                if payment.journal_id.type == "cash" and payment.state =='paid':
                    cash_denomination_model = self.env['cash.denomination']

                    existing_denomination = cash_denomination_model.sudo().search([
                        ('user', '=', payment.cashier.id),
                        ('counter', '=', payment.location.id),
                        ('state', '=', 'draft')
                    ], limit=1)

                    if existing_denomination:
                        denomination = existing_denomination
                    else:
                        denomination = cash_denomination_model.sudo().create({
                            'date': fields.Date.today(),
                            'user': payment.cashier.id,
                            'counter': payment.location.id,
                            'state': 'draft'
                        })

                    existing_line = denomination.payment_ids.filtered(
                        lambda l: l.payment_id.id == payment.id
                    )

                    if not existing_line:
                        self.env['denomination.payment.lines'].sudo().create({
                            'denomination_id': denomination.id,
                            'payment_id': payment.id,
                        })

        return res



    def write(self, vals):
        res = super(AccountPayment, self).write(vals)

        for rec in self:
            if 'state' in vals:  # state changed
                cash_denomination_model = self.env['cash.denomination']
                existing_denomination = cash_denomination_model.sudo().search([
                    ('user', '=', rec.cashier.id),
                    ('counter', '=', rec.location.id),
                    ('state', '=', 'draft')
                ], limit=1)

                existing_line = False
                if existing_denomination:
                    existing_line = existing_denomination.payment_ids.filtered(
                        lambda l: l.payment_id.id == rec.id
                    )

                if rec.state == 'paid':
                    if existing_denomination and not existing_line:
                        self.env['denomination.payment.lines'].sudo().create({
                            'denomination_id': existing_denomination.id,
                            'payment_id': rec.id,
                        })

                else:
                    if existing_line:
                        existing_line.sudo().unlink()

        return res