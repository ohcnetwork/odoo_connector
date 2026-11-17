import logging
import math
import os

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

# How far Care's total may be from the unrounded line total for the round-off to absorb it.
# Rounding to the rupee moves a total by at most 50 paise; Care's paise-level discount rounding adds a few more.
CARE_TOTAL_MAX_ROUND_OFF = 1.0


class AccountMove(models.Model):
    _inherit = "account.move"

    x_care_id = fields.Char(string="Care ID")
    x_identifier = fields.Char(string="Identifier in Care")
    x_created_by = fields.Char(string="Created By in Care")

    care_url = fields.Char(string="CARE Link", compute="_compute_care_url", store=False)
    x_care_total = fields.Monetary(
        string="Total in Care",
        currency_field="currency_id",
        # Kept on copies so a credit note reversing the invoice rounds to the same total
        help="The invoice total in Care. When set, the cash rounding line makes the Odoo total equal to it.",
    )

    def _recompute_cash_rounding_lines(self):
        """Round the invoice to Care's total instead of rounding Odoo's own total.

        Care rounds each item's discount to the paisa while Odoo applies the discount % to the line, so the
        two can be a paisa apart before rounding and a rupee apart after it. Making the round-off whatever
        brings the lines to Care's total keeps both systems on the same amount.
        """
        self.ensure_one()
        difference = self._care_total_round_off()
        if difference is None:
            return super()._recompute_cash_rounding_lines()
        return super(
            AccountMove, self.with_context(care_cash_rounding_difference=difference)
        )._recompute_cash_rounding_lines()

    def _care_total_round_off(self):
        """The round-off that brings the invoice to x_care_total, or None to round as Odoo normally does."""
        if not self.x_care_total or not self.is_invoice(include_receipts=True):
            return None
        if self.currency_id != self.company_id.currency_id:
            return None
        # Same lines as the standard computation: everything except the receivable/payable and the round-off
        lines = self.line_ids.filtered(
            lambda line: line.account_id.account_type not in ("asset_receivable", "liability_payable")
            and line.display_type != "rounding"
        )
        total = sum(lines.mapped("amount_currency"))
        if self.currency_id.is_zero(total):
            return None
        # The lines carry the opposite sign of the receivable, so match the sign of their sum
        target = math.copysign(abs(self.x_care_total), total)
        difference = self.currency_id.round(target - total)
        if abs(difference) > CARE_TOTAL_MAX_ROUND_OFF:
            _logger.warning(
                "Invoice %s: Care total %s is %s away from the line total, rounding normally",
                self.name or self.x_care_id, self.x_care_total, difference,
            )
            return None
        return difference

    @api.depends("x_care_id")
    def _compute_care_url(self):
        care_domain = os.getenv("CARE_DOMAIN")
        facility_id = os.getenv("CARE_FACILITY_ID")
        for rec in self:
            if rec.x_care_id and care_domain and facility_id:
                rec.care_url = (
                    f"{care_domain}/facility/{facility_id}/"
                    f"billing/invoices/{rec.x_care_id}"
                )
            else:
                rec.care_url = False


class AccountCashRounding(models.Model):
    _inherit = "account.cash.rounding"

    def compute_difference(self, currency, amount):
        # Set by AccountMove._recompute_cash_rounding_lines when the invoice is rounded to Care's total
        difference = self.env.context.get("care_cash_rounding_difference")
        if difference is not None:
            return difference
        return super().compute_difference(currency, amount)


class AccountMoveLines(models.Model):
    _inherit = "account.move.line"

    x_care_id = fields.Char(string="Care Charge Item ID")
    received_qty = fields.Float(string="Quantity", store=True)
    free_qty = fields.Float(string="Free Quantity")

    @api.onchange("received_qty", "free_qty")
    def _onchange_received_qty(self):
        if self.move_id.move_type == "in_invoice":
            self.quantity = self.received_qty - self.free_qty
            if self.free_qty > self.received_qty:
                self.free_qty = 0
                self.quantity = self.received_qty
        else:
            self.quantity = self.received_qty
            self.free_qty = 0
