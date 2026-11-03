import base64
import json
from decimal import Decimal
from urllib.parse import urlencode
from uuid import uuid4

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user

from ..pydantic_models.account_move import InvoiceItem
from ..resources.account_move import AccountUtility


@tagged("post_install", "-at_install")
class TestPurchasePrices(AccountTestInvoicingCommon, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = new_test_user(
            cls.env,
            login="purchase-api-manager",
            groups="account.group_account_invoice",
        )
        cls.reader = new_test_user(cls.env, login="purchase-api-reader")
        cls.account_reader = new_test_user(
            cls.env,
            login="purchase-api-account-reader",
            groups="account.group_account_readonly",
        )
        cls.facility, cls.item = str(uuid4()), str(uuid4())
        cls.product_a.x_care_id = str(uuid4())
        cls.product_b.x_care_id = str(uuid4())

    def metadata(self, product, product_id, pack_size, quantity, batch="0007"):
        return {
            "facility_uuid": self.facility,
            "item_uuid": self.item,
            "item_name": "Medicine",
            "product_id": product_id,
            "product_uuid": str(uuid4()),
            "batch": batch,
            "charge_definition_uuid": product.x_care_id,
            "pack_size": pack_size,
            "base_unit": {"code": "{tbl}", "display": "tablet"},
            "received_base_units": str(quantity),
        }

    def line(self, product, metadata, paid, free, price, discount=0):
        return {
            "product_id": product.id,
            "product_uom_id": product.uom_id.id,
            "account_id": self.company_data["default_account_expense"].id,
            "quantity": paid,
            "received_qty": paid + free,
            "free_qty": free,
            "price_unit": price,
            "discount": discount,
            "tax_ids": [Command.clear()],
            "x_care_id": str(uuid4()),
            "care_purchase": metadata,
        }

    def bill(self, lines, month="04", state="posted", move_type="in_invoice"):
        bill = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner_a.id,
                "journal_id": self.company_data[
                    "default_journal_sale"
                    if move_type == "out_invoice"
                    else "default_journal_purchase"
                ].id,
                "invoice_date": f"2026-{month}-10",
                # The endpoint groups by bill date, not this accounting date.
                "date": "2026-07-10",
                "invoice_line_ids": [Command.create(line) for line in lines],
            }
        )
        if state == "posted":
            bill.action_post()
        elif state == "cancel":
            bill.button_cancel()
        return bill

    def api(self, query=None, entries=None, user=None, authenticated=True):
        headers = {}
        if authenticated:
            login = (user or self.manager).login
            headers["Authorization"] = (
                "Basic " + base64.b64encode(f"{login}:{login}".encode()).decode()
            )
        if entries is not None:
            headers["Content-Type"] = "application/json"
            return self.url_open(
                "/api/purchases/metadata",
                data=json.dumps({"entries": entries}),
                headers=headers,
            )
        return self.url_open(
            "/api/purchases/monthly-prices?"
            + urlencode(query or {"from_month": "2026-04"}),
            headers=headers,
        )

    def test_monthly_purchase_average_pools_batches_free_units_and_discount_once(self):
        first = self.metadata(self.product_a, 101, 10, 1500)
        second = self.metadata(self.product_b, 102, 20, 1000, batch="0099")
        # 100 paid + 50 free packs of 10; 50 paid packs of 20.
        lines = [
            self.line(self.product_a, first, 100, 50, 100, discount=10),
            self.line(self.product_b, second, 50, 0, 200),
        ]
        # Exercise the actual Care invoice schema and bill-line writer, not just
        # a manually attached JSON fixture, for the second batch.
        invoice_item = InvoiceItem.model_validate(
            {
                "product_data": {
                    "product_name": self.product_b.name,
                    "x_care_id": self.product_b.x_care_id,
                    "category": {
                        "category_name": "Medicine",
                        "x_care_id": str(uuid4()),
                    },
                },
                "quantity": 50,
                "sale_price": 200,
                "x_care_id": lines[1]["x_care_id"],
                "care_purchase": second,
            }
        )
        lines[1].pop("care_purchase")
        lines[1].update(
            AccountUtility._prepare_invoice_line_vals(
                self.env, invoice_item, "in_invoice"
            )
        )
        double = self.env["uom.uom"].create(
            {
                "name": "Double pack",
                "relative_uom_id": self.product_a.uom_id.id,
                "relative_factor": 2,
            }
        )
        lines[0].update(
            product_uom_id=double.id,
            quantity=50,
            received_qty=75,
            free_qty=25,
            price_unit=200,
        )
        tax = self.env["account.tax"].create(
            {"name": "Purchase API tax", "amount": 5, "type_tax_use": "purchase"}
        )
        for line in lines:
            line["tax_ids"] = [Command.set(tax.ids)]
        bill = self.bill(lines)
        self.assertAlmostEqual(bill.amount_total, 19950)
        # These must not contribute to purchase-only posted-invoice averages.
        for state, move_type in (
            ("draft", "in_invoice"),
            ("cancel", "in_invoice"),
            ("posted", "in_refund"),
            ("posted", "out_invoice"),
        ):
            self.bill(
                [self.line(self.product_a, first, 100, 0, 999)],
                state=state,
                move_type=move_type,
            )
        free = self.metadata(self.product_a, 103, 10, 500, batch="FREE")
        self.bill([self.line(self.product_a, free, 0, 50, 100)], month="05")
        response = self.api({"from_month": "2026-04", "to_month": "2026-06"})
        self.assertEqual(response.status_code, 200, response.text)
        april, may, june = response.json()["months"]
        self.assertEqual(april["bill_count"], 1)
        item = april["items"][0]
        self.assertEqual(Decimal(item["received_base_units"]), 2500)
        self.assertEqual(Decimal(item["free_base_units"]), 500)
        self.assertEqual(Decimal(item["net_purchase_value"]), 19000)
        self.assertEqual(Decimal(item["weighted_average_price"]), Decimal("7.6"))
        batches = {b["care_product_id"]: b for b in item["batches"]}
        self.assertEqual(batches[101]["batch"], "0007")
        self.assertEqual(Decimal(batches[101]["weighted_average_price"]), 6)
        self.assertEqual(Decimal(batches[102]["weighted_average_price"]), 10)
        self.assertEqual(Decimal(may["items"][0]["weighted_average_price"]), 0)
        self.assertEqual(june["items"], [])
        self.assertEqual(june["net_purchase_value"], "0")

    def test_metadata_backfill_is_idempotent_and_corrected_bills_change_the_next_read(
        self,
    ):
        metadata = self.metadata(self.product_a, 101, 10, 1500)
        bill = self.bill([self.line(self.product_a, False, 100, 50, 100, discount=10)])
        line = bill.invoice_line_ids
        original = (
            bill.state,
            bill.amount_total,
            line.quantity,
            line.price_unit,
            line.discount,
        )
        before = self.api().json()["months"][0]
        self.assertEqual(before["items"], [])
        self.assertEqual(Decimal(before["unmapped_purchase_value"]), 9000)
        entry = {"care_line_uuid": line.x_care_id, "care_purchase": metadata}
        for expected in ("updated", "unchanged"):
            response = self.api(entries=[entry])
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["results"][0]["status"], expected)
        self.assertEqual(
            (
                bill.state,
                bill.amount_total,
                line.quantity,
                line.price_unit,
                line.discount,
            ),
            original,
        )
        self.assertEqual(
            Decimal(
                self.api().json()["months"][0]["items"][0]["weighted_average_price"]
            ),
            6,
        )
        bill.button_draft()
        line.price_unit = 200
        bill.action_post()
        self.assertEqual(
            Decimal(
                self.api().json()["months"][0]["items"][0]["weighted_average_price"]
            ),
            12,
        )
        # A mistyped billing product must not be attached to the receipt's batch.
        wrong = {**metadata, "charge_definition_uuid": self.product_b.x_care_id}
        response = self.api(entries=[{**entry, "care_purchase": wrong}])
        self.assertEqual(
            response.json()["results"][0]["status"], "billing_product_mismatch"
        )
        self.assertEqual(
            line.care_purchase["charge_definition_uuid"], self.product_a.x_care_id
        )

    def test_conflicting_units_and_invalid_quantities_are_reported_without_a_false_average(
        self,
    ):
        first = self.metadata(self.product_a, 101, 10, 100)
        second = self.metadata(self.product_b, 102, 20, 200)
        second["base_unit"] = {"code": "mL", "display": "milliliter"}
        self.bill(
            [
                self.line(self.product_a, first, 10, 0, 100),
                self.line(self.product_b, second, 10, 0, 100),
            ]
        )
        item = self.api().json()["months"][0]["items"][0]
        self.assertIsNone(item["weighted_average_price"])
        self.assertIn("conflicting_base_units", item["flags"])
        invalid = self.metadata(self.product_a, 103, 10, 0, batch="INVALID")
        self.bill([self.line(self.product_a, invalid, 0, 0, 100)], month="05")
        may = self.api({"from_month": "2026-05"}).json()["months"][0]
        self.assertFalse(may["complete"])
        self.assertIsNone(may["items"][0]["weighted_average_price"])
        self.assertIn("invalid_purchase_quantity", may["items"][0]["flags"])

    def test_authentication_company_access_and_month_validation(self):
        response = self.api(authenticated=False)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.api(user=self.reader).status_code, 403)
        self.assertEqual(self.api(user=self.account_reader).status_code, 200)
        entry = {
            "care_line_uuid": str(uuid4()),
            "care_purchase": self.metadata(self.product_a, 101, 10, 100),
        }
        self.assertEqual(
            self.api(entries=[entry], user=self.account_reader).status_code, 403
        )
        other = self.env["res.company"].create({"name": "Purchase API other company"})
        self.bill([self.line(self.product_a, entry["care_purchase"], 10, 0, 100)])
        other_reader = new_test_user(
            self.env,
            login="purchase-api-other-reader",
            groups="account.group_account_readonly",
            company_id=other.id,
            company_ids=[Command.set(other.ids)],
        )
        response = self.api(user=other_reader)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["company_id"], other.id)
        self.assertEqual(response.json()["months"][0]["bill_line_count"], 0)
        self.assertEqual(
            self.api({"from_month": "2026-04", "company_id": other.id}).status_code, 403
        )
        for query in (
            {"to_month": "2026-04"},
            {"from_month": "2026-4"},
            {"from_month": "2026-13"},
            {"from_month": "2026-04", "to_month": "2026-03"},
            {"from_month": "2026-04", "to_month": "2027-04"},
        ):
            self.assertEqual(self.api(query).status_code, 400)
