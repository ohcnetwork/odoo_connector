from decimal import Decimal
from uuid import uuid4

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from odoo import Command, fields

from ..resources.stock_monthly import MonthlyStockSync
from ..resources.stock_sync import StockSync


@tagged("post_install", "-at_install")
class TestCareStockSync(TransactionCase):
    def test_rebuild_replaces_two_months_without_double_stock_and_keeps_old_reports(
        self,
    ):
        facility, item, batch = (str(uuid4()) for _ in range(3))
        items = [{"uuid": item, "name": "Rebuild medicine", "opening_unit_cost": "8"}]

        def prepare(staged=True):
            period = {
                "period_key": f"rebuild-test:{uuid4()}",
                "facility_uuid": facility,
                "month": "2026-04",
                "stock_month": "2026-04",
                "mode": "monthly",
                "staged": staged,
            }
            MonthlyStockSync.prepare(
                self.env,
                {**period, "items": items, "opening_at": "2026-03-31T18:29:59Z"},
            )
            return period

        def close(period, month, receipt_value):
            events = []
            if month == "2026-04":
                events.append(
                    {
                        "key": f"{period['period_key']}:opening",
                        "item_uuid": item,
                        "source": "external",
                        "destination": "valuation",
                        "quantity": "100",
                        "date": "2026-03-31T18:29:59Z",
                        "kind": "opening",
                        "cost_basis": "opening",
                        "input_value": "800",
                    }
                )
                evidence = {
                    "cost_basis": "care_unmatched",
                    "input_value": str(receipt_value),
                    "quantity": "100",
                }
                events.append(
                    {
                        "key": f"{period['period_key']}:receipt",
                        "item_uuid": item,
                        "source": "external",
                        "destination": "valuation",
                        "quantity": "100",
                        "date": "2026-04-30T18:29:56Z",
                        "kind": "receipt",
                        "cost_basis": "monthly_receipt",
                        "input_value": str(receipt_value),
                        "receipts": [evidence],
                    }
                )
            events.append(
                {
                    "key": f"{period['period_key']}:{month}:issue",
                    "item_uuid": item,
                    "source": "valuation",
                    "destination": "consumption",
                    "quantity": "50" if month == "2026-04" else "20",
                    "date": "2026-04-30T18:29:58Z"
                    if month == "2026-04"
                    else "2026-05-31T18:29:58Z",
                    "kind": "dispense",
                    "cost_basis": "native_average",
                }
            )
            request = {**period, "stock_month": month}
            MonthlyStockSync.events(self.env, {**request, "events": events})
            quantity = 150 if month == "2026-04" else 130
            return MonthlyStockSync.close(
                self.env,
                {
                    **request,
                    "items": items,
                    "source_hash": f"{period['period_key']}:{month}",
                    "quantity_basis": "owned",
                    "event_keys": [e["key"] for e in events],
                    "closing_quantities": {item: str(quantity)},
                    "available_quantities": {item: str(quantity - 20)},
                    "in_transit_quantities": {item: "20"},
                    "location_uuids": ["store", "ward"],
                    "stock_details": [
                        {
                            "item_uuid": item,
                            "batch_uuid": batch,
                            "batch": "B1",
                            "expiry": "2027-01-31",
                            "location_uuid": "store",
                            "location": "Store",
                            "quantity": str(quantity - 80),
                            "incoming_quantity": "0",
                        },
                        {
                            "item_uuid": item,
                            "batch_uuid": batch,
                            "batch": "B1",
                            "expiry": "2027-01-31",
                            "location_uuid": "ward",
                            "location": "Ward",
                            "quantity": "80",
                            "incoming_quantity": "20",
                        },
                    ],
                },
            )["snapshot"]

        old = prepare(staged=False)
        april = close(old, "2026-04", 1000)
        may = close(old, "2026-05", 1000)
        # This prepare used to reject any second ledger for the same facility.
        new = prepare()
        self.assertEqual(Decimal(april["total_value"]), 1350)
        self.assertEqual(Decimal(may["total_value"]), 1170)
        close(new, "2026-04", 800)
        publish = {
            **new,
            "through_month": "2026-05",
            "replaces_period_key": old["period_key"],
        }
        with self.assertRaisesRegex(ValidationError, "[Cc]omplete"):
            MonthlyStockSync.publish(self.env, publish)
        self.assertEqual(StockSync.period(self.env, old).state, "current")
        # An unfinished replacement must not block the current series from
        # preparing its next month.
        MonthlyStockSync.prepare(
            self.env,
            {
                **old,
                "stock_month": "2026-06",
                "items": items,
                "opening_at": "2026-05-31T18:29:59Z",
            },
        )
        replacement = close(new, "2026-05", 800)
        MonthlyStockSync.publish(self.env, publish)
        MonthlyStockSync.publish(self.env, publish)
        self.assertEqual(StockSync.period(self.env, old).state, "archived")
        self.assertEqual(MonthlyStockSync.snapshot(self.env, old)["snapshot"], april)
        self.assertEqual(Decimal(replacement["total_value"]), 1040)
        self.assertEqual(
            sum(Decimal(d["quantity"]) for d in replacement["details"]), 130
        )
        self.assertEqual(sum(Decimal(d["value"]) for d in replacement["details"]), 1040)
        self.assertEqual(
            sum(Decimal(d["incoming_quantity"]) for d in replacement["details"]), 20
        )
        products = (
            self.env["product.product"]
            .with_context(active_test=False)
            .search([("care_stock_item_uuid", "=", item)])
        )
        self.assertEqual(len(products), 2)
        self.assertEqual(sum(products.mapped("qty_available")), 130)
        self.assertEqual(sum(products.filtered("active").mapped("qty_available")), 130)
        self.assertFalse(products.filtered(lambda p: not p.active).qty_available)
        MonthlyStockSync.prepare(
            self.env,
            {
                **new,
                "stock_month": "2026-06",
                "items": items,
                "opening_at": "2026-05-31T18:29:59Z",
            },
        )

    def setUp(self):
        super().setUp()
        self.item, self.batch, self.location = (str(uuid4()) for _ in range(3))
        self.period = {
            "period_key": f"test:{uuid4()}",
            "month": "2026-04",
            "facility_uuid": str(uuid4()),
        }
        StockSync.prepare(
            self.env,
            {
                **self.period,
                "opening_at": "2026-03-31T18:29:59+00:00",
                "items": [
                    {
                        "uuid": self.item,
                        "name": "Stock calculation test",
                        "opening_unit_cost": "8",
                    }
                ],
                "batches": [
                    {"uuid": self.batch, "item_uuid": self.item, "lot_number": "TEST"}
                ],
                "locations": [{"uuid": self.location, "name": "Test store"}],
            },
        )
        self.product = self.env["product.product"].search(
            [("care_stock_item_uuid", "=", self.item)]
        )

    def event(
        self,
        key,
        quantity,
        source="external",
        destination=None,
        value="0",
        basis="care_legacy",
    ):
        return {
            "key": f"{self.period['period_key']}:{key}",
            "batch_uuid": self.batch,
            "source": source,
            "destination": destination or self.location,
            "quantity": str(quantity),
            "input_value": str(value),
            "cost_basis": basis,
            "kind": key,
            "date": "2026-04-10T10:00:00+00:00",
        }

    def post(self, *events):
        return StockSync.events(self.env, {**self.period, "events": list(events)})

    def test_discount_and_free_stock_use_posted_bill_value_and_retry_does_not_duplicate(
        self,
    ):
        opening = self.event("opening", 100, value=800, basis="opening")
        opening["date"] = "2026-03-31T18:29:59+00:00"
        self.post(opening)
        supplier = self.env["res.partner"].create(
            {"name": "Stock test supplier", "supplier_rank": 1}
        )
        journal = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", self.env.company.id)],
            limit=1,
        )
        expense = self.env["account.account"].search(
            [
                ("account_type", "=", "expense"),
                ("company_ids", "in", self.env.company.id),
            ],
            limit=1,
        )
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        grn_sequence = self.env["ir.sequence"].create(
            {"name": "Stock test GRN", "code": "grn.stock-test", "padding": 4}
        )
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": supplier.id,
                "journal_id": journal.id,
                "invoice_date": fields.Date.today(),
                "ref": "Stock test bill",
                "x_care_id": order_uuid,
                "grn_sequence_id": grn_sequence.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "100 paid and 50 free, ten percent discount",
                            "product_id": self.product.id,
                            "account_id": expense.id,
                            "quantity": 100,
                            "received_qty": 150,
                            "free_qty": 50,
                            "price_unit": 10,
                            "discount": 10,
                            "tax_ids": [Command.clear()],
                            "x_care_id": line_uuid,
                        }
                    )
                ],
            }
        )
        bill.action_post()
        line = bill.invoice_line_ids
        self.assertAlmostEqual(line.balance, 900, places=2)
        receipt = self.event("receipt", 150, value=900, basis="posted_bill")
        receipt.update(
            {
                "bill_line_ids": line.ids,
                "care_line_uuid": line_uuid,
                "care_order_uuid": order_uuid,
            }
        )
        self.post(receipt)
        self.assertAlmostEqual(self.product.qty_available, 250, places=6)
        self.assertAlmostEqual(self.product.standard_price, 6.8, places=8)
        self.post(receipt)
        self.assertAlmostEqual(self.product.qty_available, 250, places=6)
        changed = {**receipt, "quantity": "151"}
        with self.assertRaises(ValidationError):
            self.post(changed)
        issue = self.event(
            "dispense",
            170,
            source=self.location,
            destination="consumption",
            basis="native_average",
        )
        issue["date"] = "2026-04-30T18:29:58+00:00"
        self.post(issue)
        self.assertAlmostEqual(self.product.qty_available, 80, places=6)
        self.assertAlmostEqual(self.product.total_value, 544, places=2)
        history = self.product.with_context(to_date="2026-03-31 18:29:59")
        self.assertAlmostEqual(history.qty_available, 100, places=6)
        self.assertAlmostEqual(
            self.product._run_avco(
                at_date=fields.Datetime.to_datetime("2026-03-31 18:29:59")
            )[1],
            800,
            places=2,
        )

    def test_zero_cost_receipt_after_depletion_resets_the_native_average_to_zero(self):
        self.post(self.event("opening", 100, value=800))
        self.post(
            self.event(
                "deplete",
                100,
                source=self.location,
                destination="consumption",
                basis="native_average",
            )
        )
        self.post(self.event("fully_free", 50, value=0))
        self.assertAlmostEqual(self.product.qty_available, 50, places=6)
        self.assertAlmostEqual(self.product._run_avco()[0], 0, places=8)
        self.assertAlmostEqual(self.product.standard_price, 0, places=8)
        self.post(
            self.event(
                "free_issue",
                10,
                source=self.location,
                destination="consumption",
                basis="native_average",
            )
        )
        move = self.env["stock.move"].search(
            [("care_stock_key", "=", f"{self.period['period_key']}:free_issue")]
        )
        self.assertAlmostEqual(move.value, 0, places=2)

    def test_monthly_summary_rolls_forward_and_closed_exports_survive_later_months(
        self,
    ):
        facility, item = str(uuid4()), str(uuid4())
        period = {
            "period_key": f"monthly-test:{uuid4()}",
            "facility_uuid": facility,
            "month": "2026-04",
            "stock_month": "2026-04",
            "mode": "monthly",
        }
        items = [
            {
                "uuid": item,
                "name": "Monthly summary test",
                "opening_unit_cost": "8",
                "base_unit": "tablet",
            }
        ]
        MonthlyStockSync.prepare(
            self.env, {**period, "opening_at": "2026-03-31T18:29:59Z", "items": items}
        )

        def event(
            key,
            quantity,
            date,
            kind,
            source="external",
            destination="valuation",
            basis="care_unmatched",
            value="0",
        ):
            return {
                "key": f"{period['period_key']}:{key}",
                "item_uuid": item,
                "quantity": str(quantity),
                "date": date,
                "kind": kind,
                "source": source,
                "destination": destination,
                "cost_basis": basis,
                "input_value": str(value),
            }

        opening = event(
            "opening",
            100,
            "2026-03-31T18:29:59Z",
            "opening",
            basis="opening",
            value=800,
        )
        # Zero-cost quantity is included in the physical denominator.
        receipts = [
            event("paid", 100, "2026-04-30T18:29:56Z", "receipt", value=900),
            event("free", 50, "2026-04-30T18:29:56Z", "receipt", value=0),
        ]
        receipt = event(
            "receipt",
            150,
            "2026-04-30T18:29:56Z",
            "receipt",
            basis="monthly_receipt",
            value=900,
        )
        receipt["receipts"] = receipts
        issue = event(
            "issue",
            170,
            "2026-04-30T18:29:58Z",
            "dispense",
            "valuation",
            "consumption",
            "native_average",
        )
        events = [opening, receipt, issue]
        for row in events:
            MonthlyStockSync.events(self.env, {**period, "events": [row]})
        product = self.env["product.product"].search(
            [("care_stock_item_uuid", "=", item)]
        )
        self.assertEqual(product.tracking, "none")
        self.assertAlmostEqual(product.qty_available, 80)
        self.assertAlmostEqual(product.standard_price, 6.8)
        close = {
            **period,
            "source_hash": "april",
            "event_keys": [e["key"] for e in events],
            "closing_quantities": {item: "80"},
            "quantity_basis": "owned",
            "available_quantities": {item: "60"},
            "in_transit_quantities": {item: "20"},
            "location_uuids": ["care-store"],
            "items": items,
        }
        with self.assertRaisesRegex(ValidationError, "quantity differs"):
            MonthlyStockSync.close(
                self.env, {**close, "closing_quantities": {item: "81"}}
            )
        with self.assertRaisesRegex(ValidationError, "plus internal transit"):
            MonthlyStockSync.close(
                self.env, {**close, "available_quantities": {item: "61"}}
            )
        april = MonthlyStockSync.close(self.env, close)["snapshot"]
        self.assertEqual(april["quantity_basis"], "owned")
        self.assertEqual(april["items"][0]["available_quantity"], 60)
        self.assertEqual(april["items"][0]["in_transit_quantity"], 20)
        self.assertEqual(Decimal(april["total_value"]), Decimal("544"))
        self.assertTrue(MonthlyStockSync.close(self.env, close)["already_closed"])
        self.assertEqual(
            MonthlyStockSync.events(self.env, {**period, "events": events})["posted"], 0
        )
        with self.assertRaisesRegex(ValidationError, "new revision"):
            MonthlyStockSync.close(self.env, {**close, "source_hash": "changed"})
        with self.assertRaisesRegex(ValidationError, "closed Care stock month"):
            MonthlyStockSync.events(
                self.env, {**period, "events": [{**issue, "key": "late"}]}
            )
        with self.assertRaisesRegex(ValidationError, "consecutively"):
            MonthlyStockSync.prepare(self.env, {**period, "stock_month": "2026-06"})
        may = {**period, "stock_month": "2026-05"}
        MonthlyStockSync.prepare(
            self.env, {**may, "opening_at": "2026-04-30T18:29:59Z", "items": items}
        )
        may_receipt = event(
            "may-receipt", 20, "2026-05-31T18:29:56Z", "receipt", value=256
        )
        may_receipt.update(
            {"cost_basis": "monthly_receipt", "receipts": [dict(may_receipt)]}
        )
        MonthlyStockSync.events(self.env, {**may, "events": [may_receipt]})
        self.assertAlmostEqual(product.qty_available, 100)
        self.assertAlmostEqual(product.standard_price, 8)
        result = MonthlyStockSync.close(
            self.env,
            {
                **close,
                **may,
                "source_hash": "may",
                "event_keys": [may_receipt["key"]],
                "closing_quantities": {item: "100"},
                "available_quantities": {item: "80"},
            },
        )["snapshot"]
        self.assertEqual(Decimal(result["total_value"]), Decimal("800"))
        self.assertEqual(MonthlyStockSync.snapshot(self.env, period)["snapshot"], april)
        other = {
            **period,
            "period_key": f"monthly-test:{uuid4()}",
            "facility_uuid": str(uuid4()),
        }
        first_location = StockSync.period(self.env, period).location_map["valuation"]
        MonthlyStockSync.prepare(
            self.env, {**other, "items": [], "opening_at": "2026-03-31T18:29:59Z"}
        )
        self.assertNotEqual(
            first_location, StockSync.period(self.env, other).location_map["valuation"]
        )

    def test_monthly_recoveries_use_the_same_native_monthly_rate_across_batches(self):
        item = str(uuid4())
        period = {
            "period_key": f"monthly-test:{uuid4()}",
            "facility_uuid": str(uuid4()),
            "month": "2026-04",
            "stock_month": "2026-04",
            "mode": "monthly",
        }
        MonthlyStockSync.prepare(
            self.env,
            {
                **period,
                "opening_at": "2026-03-31T18:29:59Z",
                "items": [
                    {
                        "uuid": item,
                        "name": "Fractional monthly recovery",
                        "opening_unit_cost": "0.333333333333",
                    }
                ],
            },
        )
        opening = {
            "key": f"{period['period_key']}:opening",
            "item_uuid": item,
            "source": "external",
            "destination": "valuation",
            "quantity": "3",
            "input_value": "1",
            "kind": "opening",
            "cost_basis": "opening",
            "date": "2026-03-31T18:29:59Z",
        }
        MonthlyStockSync.events(self.env, {**period, "events": [opening]})
        recovery = {
            "key": f"{period['period_key']}:recovery1",
            "item_uuid": item,
            "source": "consumption",
            "destination": "valuation",
            "quantity": "1",
            "kind": "recovery",
            "cost_basis": "native_average",
            "date": "2026-04-30T18:29:57Z",
        }
        MonthlyStockSync.events(self.env, {**period, "events": [recovery]})
        second = {
            **recovery,
            "key": f"{period['period_key']}:recovery2",
            "quantity": "100",
            "source": "transit",
        }
        MonthlyStockSync.events(self.env, {**period, "events": [second]})
        move = self.env["stock.move"].search([("care_stock_key", "=", second["key"])])
        self.assertAlmostEqual(move.value, 33.33, places=2)
