from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    discount_summary = fields.Text(
        string="Discount Summary",
        compute="_compute_discount_summary",
        store=False,
    )

    @api.depends("invoice_line_ids.discount", "invoice_line_ids.discount_group_id")
    def _compute_discount_summary(self):
        for move in self:
            move.discount_summary = False
            if move.move_type not in ("out_invoice", "in_invoice"):
                continue

            discount_totals = {}
            for line in move.invoice_line_ids.filtered(lambda l: l.discount > 0):
                group_name = line.discount_group_id.name if line.discount_group_id else "General"
                # Calculate discount amount from the native discount percentage
                discount_amount = line.price_unit * line.quantity * line.discount / 100
                discount_totals[group_name] = discount_totals.get(group_name, 0.0) + discount_amount

            if discount_totals:
                move.discount_summary = "\n".join(
                    f"{name}: {amount:.2f}" for name, amount in discount_totals.items()
                )


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # Track discount metadata - the actual discount is in the native 'discount' field
    discount_group_id = fields.Many2one(
        "account.discount.group",
        string="Discount Group",
        help="The discount group/scheme applied to this line",
    )
    discount_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ], string="Discount Type", default='percentage')
    x_care_discount_id = fields.Char(
        string="Care Discount ID",
        help="Reference ID from Care system",
    )
