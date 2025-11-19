import json
from odoo import api, fields, models
from odoo.tools.float_utils import float_is_zero

class AccountMove(models.Model):
    _inherit = "account.move"

    discount_list = fields.Char(
        compute='_compute_discount_summary',
        string="Discount",
        store=False
    )

    @api.depends('invoice_line_ids.account_discount')
    def _compute_discount_summary(self):
        for move in self:
            move.discount_list = None
            if move.move_type == 'out_invoice':
                discount_dict = {}
                for line in move.invoice_line_ids:
                    if line.account_discount:
                        product_tmpl_id = line.account_discount.id
                        matched_line = move.invoice_line_ids.filtered(
                            lambda l: l.product_id.product_tmpl_id.id == product_tmpl_id
                        )
                        if matched_line:
                            discount_dict[matched_line.product_id.discount_group.name] = abs(matched_line.price_subtotal)

                discount_str = '\n'.join(f"{k} : {v}" for k, v in discount_dict.items())
                move.discount_list = discount_str

    @api.model
    def create(self, vals):
        move = super(AccountMove, self).create(vals)
        if move.move_type == 'out_invoice':
            discount_lines = move.invoice_line_ids.filtered(lambda l: l.account_discount)

            if not discount_lines:
                return move
            section_line_commands = []

            section_line_commands.append((0, 0, {
                "display_type": "line_section",
                "name": "Discount",
            }))

            for line in discount_lines:
                product_tmpl = line.account_discount
                if not product_tmpl:
                    continue

                section_line_commands.append((0, 0, {
                    "product_id": product_tmpl.id,
                    "received_qty": -1,
                    "quantity": -1,
                    "name": product_tmpl.name,
                }))

            if section_line_commands:
                move.write({"invoice_line_ids": section_line_commands})

        return move

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    account_discount = fields.Many2one(
        'product.template',
        string="Discount",
        domain=[('is_disc_item', '=', True)]
    )