from io import BytesIO
from xml.etree import ElementTree
from zipfile import ZipFile

from odoo import Command
from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestCareStockExport(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = new_test_user(
            cls.env, login="stock-export-manager", groups="stock.group_stock_manager"
        )
        cls.reader = new_test_user(cls.env, login="stock-export-reader")
        other = cls.env["res.company"].create({"name": "Other stock company"})
        cls.other_manager = new_test_user(
            cls.env,
            login="stock-export-other",
            groups="stock.group_stock_manager",
            company_id=other.id,
            company_ids=[Command.set(other.ids)],
        )
        products = cls.env["product.product"].create(
            [{"name": "=Medicine"}, {"name": "=Medicine"}]
        )
        cls.product_ids = products.ids
        items = [
            {
                "item_uuid": "item-a",
                "name": "=Medicine",
                "product_id": products[0].id,
                "base_unit": {"display": "count"},
                "quantity": "15.25",
                "reported_total_value": "152.50",
            },
            {
                "item_uuid": "item-b",
                "name": "=Medicine",
                "product_id": products[1].id,
                "base_unit": {"display": "mL"},
                "quantity": "-2",
                "reported_total_value": "0",
            },
            {
                "item_uuid": "unused",
                "name": "Unused",
                "product_id": products[0].id,
                "quantity": "0",
                "reported_total_value": "0",
            },
        ]
        details = []
        for item, batch, location, quantity, value, incoming in [
            ("item-a", "batch-a", "north", "10", "100", "0"),
            ("item-a", "batch-b", "north", "5", "50", "0"),
            ("item-a", "batch-c", "south", "0.25", "2.5", "0.25"),
            ("item-b", "batch-d", "north", "-2", "0", "0"),
        ]:
            details.append(
                {
                    "item_uuid": item,
                    "item": "=Medicine",
                    "batch_uuid": batch,
                    "batch": batch,
                    "expiry": "2027-01-31",
                    "location_uuid": location,
                    "location": "Pharmacy",
                    "quantity": quantity,
                    "available_quantity": "0" if incoming != "0" else quantity,
                    "incoming_quantity": incoming,
                    "effective_cost": "10" if item == "item-a" else "0",
                    "value": value,
                }
            )
        cls.reports = cls.env["care.stock.close"]
        for state in ("current", "archived"):
            period = cls.env["care.stock.period"].create(
                {
                    "key": f"stock-export-{state}",
                    "facility_uuid": "export-facility",
                    "month": "2026-04",
                    "company_id": cls.env.company.id,
                    "state": state,
                }
            )
            cls.reports |= cls.env["care.stock.close"].create(
                {
                    "period_id": period.id,
                    "month": "2026-04",
                    "source_hash": "export-source",
                    "snapshot": {
                        "items": items,
                        "details": details,
                        "quantity_basis": "owned",
                        "total_value": "152.50",
                    },
                }
            )
        # Later live cost changes must not change the saved month-end export.
        products.standard_price = 999

    def test_download_keeps_saved_item_and_location_values(self):
        self.authenticate(self.manager.login, self.manager.login)
        namespace = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        for report in self.reports:
            with self.subTest(state=report.period_id.state):
                response = self.url_open(
                    report.with_user(self.manager).action_export_xlsx()["url"]
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    "stock-by-item-2026-04.xlsx",
                    response.headers["Content-Disposition"],
                )
                with ZipFile(BytesIO(response.content)) as archive:
                    shared = ElementTree.fromstring(
                        archive.read("xl/sharedStrings.xml")
                    )
                    strings = ["".join(node.itertext()) for node in shared]

                    def cells(sheet, strings=strings):
                        xml = ElementTree.fromstring(
                            archive.read(f"xl/worksheets/sheet{sheet}.xml")
                        )
                        result = {}
                        for cell in xml.findall(".//s:c", namespace):
                            value = cell.find("s:v", namespace)
                            if value is not None:
                                result[cell.attrib["r"]] = (
                                    strings[int(value.text)]
                                    if cell.attrib.get("t") == "s"
                                    else float(value.text)
                                )
                        return xml, result

                    matrix_xml, matrix = cells(1)
                    self.assertEqual(
                        [matrix["A6"], matrix["A7"]], ["=Medicine", "=Medicine"]
                    )
                    self.assertIsNone(matrix_xml.find(".//s:c[@r='A6']/s:f", namespace))
                    self.assertEqual([matrix["B6"], matrix["B7"]], self.product_ids)
                    self.assertEqual([matrix["J6"], matrix["J7"]], ["item-a", "item-b"])
                    self.assertEqual(
                        [matrix["D4"], matrix["F4"]],
                        ["Pharmacy (north)", "Pharmacy (south)"],
                    )
                    self.assertEqual(
                        [matrix["D6"], matrix["E6"], matrix["F6"], matrix["G6"]],
                        [15, 150, 0.25, 2.5],
                    )
                    self.assertEqual(
                        [matrix["H6"], matrix["I6"], matrix["H7"], matrix["I7"]],
                        [15.25, 152.5, -2, 0],
                    )
                    self.assertEqual(
                        [matrix["H8"], matrix["I8"], matrix["B3"]],
                        [13.25, 152.5, 152.5],
                    )
                    self.assertEqual(
                        matrix["C3"], f"Revision: {report.period_id.state}"
                    )
                    _, detail = cells(2)
                    self.assertEqual(
                        [
                            detail["I8"],
                            detail["J8"],
                            detail["K8"],
                            detail["L8"],
                            detail["M8"],
                        ],
                        [0.25, 0, 0.25, 10, 2.5],
                    )
                    self.assertEqual(detail["E8"], "batch-c")

    def test_download_respects_inventory_and_company_access(self):
        url = f"/care/stock/{self.reports[0].id}/xlsx"
        for user in (self.reader, self.other_manager):
            with self.subTest(user=user.login):
                self.authenticate(user.login, user.login)
                self.assertEqual(self.url_open(url).status_code, 403)

    def test_report_without_location_detail_is_not_exported_as_zero(self):
        report = self.env["care.stock.close"].create(
            {
                "period_id": self.reports[0].period_id.id,
                "month": "2026-03",
                "source_hash": "legacy-export",
                "snapshot": {"items": [], "total_value": "100"},
            }
        )
        self.authenticate(self.manager.login, self.manager.login)
        response = self.url_open(f"/care/stock/{report.id}/xlsx")
        self.assertEqual(response.status_code, 400)
        self.assertIn("no location detail", response.text)
