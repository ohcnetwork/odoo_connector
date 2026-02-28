import json
from odoo import api, fields, models
from odoo.tools.float_utils import float_is_zero


class AccountMove(models.Model):
    _inherit = "account.move"

    discount_list = fields.Char(
        compute="_compute_discount_summary", string="Discount", store=False
    )

    @api.depends("invoice_line_ids.account_discount")
    def _compute_discount_summary(self):
        for move in self:
            move.discount_list = None
            if move.move_type == "out_invoice":
                discount_dict = {}
                for line in move.invoice_line_ids:
                    if line.account_discount:
                        for disc in line.account_discount:
                            # Check if it's amount-based or percentage-based discount
                            if disc.disc_amount:
                                # Amount-based discount
                                discount_amount = abs(disc.disc_amount * line.quantity)
                            else:
                                # Percentage-based discount
                                discount_amount = abs(
                                    line.price_subtotal * (disc.disc_percent / 100.0)
                                )
                            discount_amount = round(discount_amount, 2)

                            if disc.discount_group.name not in discount_dict:
                                discount_dict[disc.discount_group.name] = 0.0

                            discount_dict[disc.discount_group.name] += discount_amount
                discount_str = "\n".join(
                    f"{k} : {format(v, '.2f')}" for k, v in discount_dict.items()
                )
                move.discount_list = discount_str

    @api.model
    def create(self, vals):
        move = super(AccountMove, self).create(vals)
        if move.move_type == "out_invoice":
            discount_lines = move.invoice_line_ids.filtered(
                lambda l: l.account_discount
            )

            if not discount_lines:
                return move
            section_line_commands = []

            section_line_commands.append(
                (
                    0,
                    0,
                    {
                        "display_type": "line_section",
                        "name": "Discount",
                    },
                )
            )
            discount_dict = {}
            for line in discount_lines:
                for disc in line.account_discount:
                    # Check if it's amount-based or percentage-based discount
                    if disc.disc_amount:
                        # Amount-based discount
                        discount_amount = abs(disc.disc_amount * line.quantity)
                    else:
                        # Percentage-based discount
                        discount_amount = abs(
                            line.price_subtotal * (disc.disc_percent / 100.0)
                        )
                    discount_amount = round(discount_amount, 2)

                    if disc.id not in discount_dict:
                        discount_dict[disc.id] = 0.0

                    discount_dict[disc.id] += discount_amount
            if discount_dict:
                for product_tmpl_id, amount in discount_dict.items():
                    product = self.env["product.product"].search(
                        [("product_tmpl_id", "=", product_tmpl_id)], limit=1
                    )
                    if product:
                        section_line_commands.append(
                            (
                                0,
                                0,
                                {
                                    "product_id": product.id,
                                    "received_qty": -1,
                                    "quantity": -1,
                                    "price_unit": amount,
                                    "name": product.name,
                                },
                            )
                        )

            if section_line_commands:
                move.write({"invoice_line_ids": section_line_commands})
        return move


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    account_discount = fields.Many2many(
        "product.template", string="Discount", domain=[("is_disc_item", "=", True)]
    )
