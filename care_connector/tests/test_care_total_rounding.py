from odoo import Command
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.care_connector.pydantic_models.account_move import AccountMoveApiRequest
from odoo.addons.care_connector.pydantic_models.invoice_resync import InvoiceResyncApiRequest
from odoo.addons.care_connector.resources.account_move import AccountUtility
from odoo.addons.care_connector.resources.invoice_resync import InvoiceResyncUtility


@tagged("post_install", "-at_install")
class TestCareTotalRounding(AccountTestInvoicingCommon):
    """Invoices synced from Care are rounded to Care's total, not to Odoo's own line total."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rounding = cls.env["account.cash.rounding"].create({
            "name": "Round off",
            "rounding": 1.0,
            "strategy": "add_invoice_line",
            "rounding_method": "HALF-UP",
            "profit_account_id": cls.company_data["default_account_revenue"].copy().id,
            "loss_account_id": cls.company_data["default_account_expense"].copy().id,
        })

    def _invoice(self, price, care_total=None, move_type="out_invoice", discount=0.0, quantity=1.0):
        vals = {
            "move_type": move_type,
            "partner_id": self.partner_a.id,
            "invoice_date": "2026-06-01",
            "invoice_cash_rounding_id": self.rounding.id,
            "invoice_line_ids": [Command.create({
                "product_id": self.product_a.id,
                "quantity": quantity,
                "price_unit": price,
                "discount": discount,
                "tax_ids": [],
            })],
        }
        if care_total is not None:
            vals["x_care_total"] = care_total
        return self.env["account.move"].create(vals)

    def _round_off(self, move):
        return sum(move.line_ids.filtered(lambda line: line.display_type == "rounding").mapped("balance"))

    def test_without_care_total_rounds_as_odoo_does(self):
        move = self._invoice(445.50)
        self.assertEqual(move.amount_total, 446.0)

    def test_rounds_to_care_total(self):
        # Odoo's line total 445.50 would round up to 446; Care says 445
        move = self._invoice(445.50, care_total=445.0)
        self.assertEqual(move.amount_total, 445.0)
        self.assertAlmostEqual(self._round_off(move), 0.50)  # a debit: round-off expense
        move.action_post()
        self.assertEqual(move.amount_total, 445.0)
        self.assertEqual(move.amount_residual, 445.0)

    def test_discount_paisa_difference(self):
        # The INV/26-27/67925 case: 471.50 at 7% discount. Odoo takes 7% off the line (438.495 → 438.50, rounded
        # to 439); Care rounds the discount first (32.995 → 33.00), gets 438.50 - 0.01 = 438.49 and bills 438
        without_care_total = self._invoice(471.50, discount=7.0)
        self.assertEqual(without_care_total.amount_total, 439.0)
        move = self._invoice(471.50, care_total=438.0, discount=7.0)
        self.assertEqual(move.amount_total, 438.0)

    def test_round_off_follows_line_changes(self):
        move = self._invoice(445.50, care_total=445.0)
        line = move.invoice_line_ids
        move.write({"invoice_line_ids": [Command.update(line.id, {"price_unit": 444.80})]})
        self.assertEqual(move.amount_total, 445.0)
        self.assertAlmostEqual(self._round_off(move), -0.20)  # a credit: round-off income

    def test_far_from_care_total_rounds_as_odoo_does(self):
        # More than a rupee away means the lines differ from Care; don't hide that in the round-off
        move = self._invoice(445.50, care_total=450.0)
        self.assertEqual(move.amount_total, 446.0)

    def test_credit_note(self):
        move = self._invoice(445.50, care_total=445.0, move_type="out_refund")
        self.assertEqual(move.amount_total, 445.0)
        self.assertEqual(move.amount_total_signed, -445.0)

    def test_reversal_keeps_care_total(self):
        move = self._invoice(445.50, care_total=445.0)
        move.action_post()
        reversal = self.env["account.move.reversal"].with_context(
            active_model="account.move", active_ids=move.ids
        ).create({"journal_id": move.journal_id.id, "reason": "cancelled in Care"})
        reversal.reverse_moves()
        credit_note = move.reversal_move_ids
        self.assertEqual(credit_note.amount_total, 445.0)

    def _sync_from_care(self, care_total=None):
        """A one-line Care invoice synced through the connector; its 445.50 rounds up to 446 in Odoo."""
        self.env["ir.config_parameter"].sudo().set_param("care_connector.invoice_cash_rounding_id", self.rounding.id)
        self.env["product.product"].create({"name": "Care item", "x_care_id": "care-item", "taxes_id": [Command.clear()]})
        request = AccountMoveApiRequest(
            x_care_id="care-invoice", bill_type="customer", invoice_date="01-06-2026", due_date="01-06-2026",
            partner_data={"name": "Care patient", "x_care_id": "care-patient", "partner_type": "person"},
            invoice_items=[{
                "product_data": {
                    "product_name": "Care item", "x_care_id": "care-item",
                    "category": {"category_name": "Pharmacy", "x_care_id": "care-category"},
                },
                "quantity": 1, "sale_price": 445.50, "x_care_id": "care-charge-item",
            }],
            care_total=care_total,
        )
        return AccountUtility.get_or_create_account_move(self.env, request), request

    def _resync(self, move, request, care_total):
        return InvoiceResyncUtility.resync(
            self.env, InvoiceResyncApiRequest(number=move.name, care_total=care_total, data=request)
        )

    def test_resync_rounds_an_old_invoice_to_care_total(self):
        # Synced before Care sent its total: Odoo rounded up to 446, and Care's ₹445 payment left a rupee open
        move, request = self._sync_from_care()
        self.assertEqual(move.amount_total, 446.0)
        self.env["account.payment.register"].with_context(active_model="account.move", active_ids=move.ids).create(
            {"amount": 445.0}
        )._create_payments()
        self.assertEqual(move.amount_residual, 1.0)

        result = self._resync(move, request, 445.0)

        self.assertEqual(result["status"], "updated", result)
        self.assertEqual(result["changes"], ["round-off set to Care's total 445.00"])
        self.assertEqual(move.name, result["old"]["name"])
        self.assertEqual(move.amount_total, 445.0)
        self.assertEqual(move.amount_residual, 0.0)

    def test_resync_leaves_an_invoice_on_care_total_alone(self):
        move, request = self._sync_from_care(care_total=445.0)
        self.assertEqual(move.amount_total, 445.0)
        self.assertEqual(self._resync(move, request, 445.0)["status"], "in sync")

    def test_resync_reports_a_total_more_than_a_rupee_off(self):
        move, request = self._sync_from_care()
        result = self._resync(move, request, 443.0)
        self.assertTrue(result["status"].startswith("needs manual fix"), result)
        self.assertEqual(move.amount_total, 446.0)
