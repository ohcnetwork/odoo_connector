from odoo import models, fields, api
from odoo.tools import float_round

class ResPartner(models.Model):
    _inherit = "res.partner"

    closing_balance = fields.Monetary(
        string="Closing Balance",
        compute="_compute_closing_balance",
        currency_field="currency_id",
        store=False,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        readonly=True,
    )

    def _compute_closing_balance(self):
        account_move_line_model = self.env["account.move.line"].sudo()
        today = fields.Date.today()

        for partner in self:
            account_types = ["asset_receivable", "liability_payable"]
            accounts_model = self.env["account.account"]
            accounts = accounts_model.search([
                ("account_type", "in", account_types),
            ])
            account_ids = accounts.ids

            if not account_ids:
                partner.closing_balance = 0.0
                continue

            base_domain = [
                ("partner_id", "=", partner.id),
                ("account_id", "in", account_ids),
                ("move_id.state", "=", "posted"),
            ]

            opening_domain = base_domain + [("date", "<", today)]
            opening = account_move_line_model.read_group(
                opening_domain,
                ["debit:sum", "credit:sum"],
                []
            )
            if opening:
                ob = float_round((opening[0]["debit"] or 0.0) - (opening[0]["credit"] or 0.0), 2)
            else:
                ob = 0.0

            period_domain = base_domain + [("date", ">=", today)]
            period = account_move_line_model.read_group(
                period_domain,
                ["debit:sum", "credit:sum"],
                []
            )
            if period:
                total_debit = float_round(period[0]["debit"] or 0.0, 2)
                total_credit = float_round(period[0]["credit"] or 0.0, 2)
            else:
                total_debit = 0.0
                total_credit = 0.0

            partner.closing_balance = float_round(ob + total_debit - total_credit, 2)

    def action_open_customer_balance(self):
        self.ensure_one()

        account_types = ["asset_receivable", "liability_payable"]
        accounts = self.env["account.account"].search([
            ("account_type", "in", account_types),
        ])

        return {
            'name': 'Account Balance Details',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': [
                ('partner_id', '=', self.id),
                ('account_id', 'in', accounts.ids),
            ],

        }
