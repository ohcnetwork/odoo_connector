# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests import freeze_time, tagged

from odoo.addons.sale_commission.tests.test_sale_commission_common import (
    TestSaleCommissionCommon,
)


@tagged("post_install", "-at_install")
class TestLineLevelCommissionReport(TestSaleCommissionCommon):
    def _approve_plan(self, plan, achievement_type, rate):
        plan.write({
            "type": "achieve",
            "achievement_ids": [
                Command.clear(),
                Command.create({"type": achievement_type, "rate": rate}),
            ],
        })
        plan.action_approve()

    def _create_commission_invoice(self, move_type):
        return self._create_invoice(
            move_type=move_type,
            invoice_date="2024-03-15",
            post=True,
            partner_id=self.partner,
            invoice_user_id=self.commission_user_1,
            team_id=self.team_commission,
            invoice_line_ids=[
                self._prepare_invoice_line(
                    product_id=self.commission_product_1,
                    price_unit=100,
                    quantity=2,
                    discount=10,
                    tax_ids=[],
                    commission_user_id=self.commission_user_2.id,
                ),
                self._prepare_invoice_line(
                    product_id=self.commission_product_2,
                    price_unit=50,
                    tax_ids=[],
                ),
            ],
        )

    @freeze_time("2024-04-02")
    def test_invoice_line_assignment_refunds_and_filtered_report(self):
        self._approve_plan(self.commission_plan_user, "amount_invoiced", 0.1)
        self._approve_plan(self.commission_plan_manager, "amount_invoiced", 0.1)
        invoices = [
            (self._create_commission_invoice("out_invoice"), 1),
            (self._create_commission_invoice("out_refund"), -1),
        ]
        line_ids = [
            line.id
            for invoice, _sign in invoices
            for line in invoice.invoice_line_ids
        ]
        report = self.env["sale.commission.achievement.report"]
        report._pre_achievement_operation()
        person_domain = [
            ("plan_id", "=", self.commission_plan_user.id),
            ("related_res_model", "=", "account.move.line"),
            ("related_res_id", "in", line_ids),
        ]

        # The first query must not discard invoices whose header salesperson differs.
        scoped_rows = report.with_context(
            commission_user_ids=self.commission_user_2.ids,
        ).search(person_domain)
        self.assertEqual(len(scoped_rows), 2)
        self.assertEqual(scoped_rows.user_id, self.commission_user_2)
        self.assertEqual(scoped_rows.product_id, self.commission_product_1)

        # Reusing the report after a filtered read must still expose all salespeople.
        person_rows = report.search(person_domain)
        self.assertEqual(len(person_rows), 4)
        self.assertEqual(len(set(person_rows.ids)), 4)
        for invoice, sign in invoices:
            for product, user, amount in [
                (self.commission_product_1, self.commission_user_2, 180),
                (self.commission_product_2, self.commission_user_1, 50),
            ]:
                with self.subTest(move_type=invoice.move_type, product=product.name):
                    source_line = invoice.invoice_line_ids.filtered(
                        lambda line: line.product_id == product
                    )
                    row = person_rows.filtered(
                        lambda achievement: achievement.related_res_id == source_line.id
                    )
                    self.assertEqual(len(row), 1)
                    self.assertEqual(row.user_id, user)
                    self.assertEqual(row.product_id, product)
                    self.assertAlmostEqual(row.line_amount, sign * amount)
                    self.assertAlmostEqual(row.achieved, sign * amount * 0.1)

            team_rows = report.search([
                ("plan_id", "=", self.commission_plan_manager.id),
                ("related_res_model", "=", "account.move"),
                ("related_res_id", "=", invoice.id),
            ])
            self.assertEqual(len(team_rows), 1)
            self.assertEqual(team_rows.user_id, self.commission_manager)
            self.assertFalse(team_rows.product_id)
            self.assertAlmostEqual(team_rows.line_amount, sign * 230)
            self.assertAlmostEqual(team_rows.achieved, sign * 23)

    @freeze_time("2024-04-02")
    def test_sales_and_manual_adjustments_share_the_extended_report(self):
        self._approve_plan(self.commission_plan_user, "amount_sold", 0.04)
        self._approve_plan(self.commission_plan_manager, "amount_sold", 0.1)
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "user_id": self.commission_user_1.id,
            "team_id": self.team_commission.id,
            "order_line": [
                Command.create({
                    "product_id": self.commission_product_1.id,
                    "product_uom_qty": 2,
                    "price_unit": 100,
                    "tax_ids": [Command.clear()],
                }),
                Command.create({
                    "product_id": self.commission_product_2.id,
                    "price_unit": 50,
                    "tax_ids": [Command.clear()],
                }),
            ],
        })
        order.action_confirm()
        plan_users = self.commission_plan_user.user_ids
        adjustment = self.env["sale.commission.achievement"].create({
            "date": "2024-03-15",
            "achieved": 25,
            "add_user_id": plan_users.filtered(
                lambda plan_user: plan_user.user_id == self.commission_user_2
            ).id,
            "reduce_user_id": plan_users.filtered(
                lambda plan_user: plan_user.user_id == self.commission_user_1
            ).id,
        })
        report = self.env["sale.commission.achievement.report"]
        report._pre_achievement_operation()
        sale_rows = report.search([
            ("plan_id", "in", (self.commission_plan_user + self.commission_plan_manager).ids),
            ("related_res_model", "=", "sale.order"),
            ("related_res_id", "=", order.id),
        ])
        self.assertEqual(len(sale_rows), 2)
        for user, amount in [
            (self.commission_user_1, 10),
            (self.commission_manager, 25),
        ]:
            row = sale_rows.filtered(lambda achievement: achievement.user_id == user)
            self.assertEqual(len(row), 1)
            self.assertAlmostEqual(row.achieved, amount)
            self.assertAlmostEqual(row.line_amount, 250)
            self.assertFalse(row.product_id)

        adjustment_rows = report.search([
            ("plan_id", "=", self.commission_plan_user.id),
            ("related_res_model", "=", "sale.commission.achievement"),
            ("related_res_id", "=", adjustment.id),
        ])
        self.assertEqual(len(adjustment_rows), 2)
        self.assertEqual(len(set(adjustment_rows.ids)), 2)
        for user, amount in [
            (self.commission_user_1, -25),
            (self.commission_user_2, 25),
        ]:
            row = adjustment_rows.filtered(
                lambda achievement: achievement.user_id == user
            )
            self.assertEqual(len(row), 1)
            self.assertAlmostEqual(row.achieved, amount)
            self.assertEqual(row.line_amount, 0)
            self.assertFalse(row.product_id)
