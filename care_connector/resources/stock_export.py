"""Item/location workbooks from saved Odoo monthly valuations."""

import calendar
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from io import BytesIO
from math import ceil

import xlsxwriter
from odoo.exceptions import UserError
from xlsxwriter.utility import xl_col_to_name, xl_rowcol_to_cell


def export_stock_xlsx(report):
    _ = report.env._
    snapshot = report.snapshot
    if "details" not in snapshot:
        raise UserError(
            _(
                "This saved report has no location detail. Rebuild the stock series to export it by location."
            )
        )
    items = {row["item_uuid"]: row for row in snapshot["items"]}
    locations = {}
    balances = defaultdict(lambda: [Decimal(0), Decimal(0)])
    quantities = defaultdict(Decimal)
    values = defaultdict(Decimal)
    details = snapshot["details"]
    for row in details:
        key = row["item_uuid"]
        if key not in items:
            raise UserError(
                _("A stock detail has no matching item in this saved report.")
            )
        location = row["location_uuid"]
        locations[location] = row["location"]
        quantity, value = Decimal(str(row["quantity"])), Decimal(str(row["value"]))
        balances[key, location][0] += quantity
        balances[key, location][1] += value
        quantities[key] += quantity
        values[key] += value
    for key, item in items.items():
        if abs(quantities[key] - Decimal(str(item["quantity"]))) > Decimal(
            "0.000001"
        ) or abs(values[key] - Decimal(str(item["reported_total_value"]))) > Decimal(
            "0.005"
        ):
            raise UserError(
                _(
                    "The saved item and location totals differ. Rebuild the stock series before exporting."
                )
            )
    if abs(
        sum(values.values(), Decimal(0)) - Decimal(snapshot["total_value"])
    ) > Decimal("0.005"):
        raise UserError(
            _("The saved location values do not match the monthly valuation.")
        )

    detail_items = {row["item_uuid"] for row in details}
    ordered_items = sorted(
        (
            row
            for key, row in items.items()
            if key in detail_items or quantities[key] or values[key]
        ),
        key=lambda row: (row["name"].casefold(), row["item_uuid"]),
    )
    ordered_locations = sorted(
        locations, key=lambda key: (locations[key].casefold(), key)
    )
    names = Counter(locations.values())
    output = BytesIO()
    workbook = xlsxwriter.Workbook(
        output,
        {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False},
    )
    base = {"font_name": "Calibri", "font_size": 10, "border": 1, "valign": "vcenter"}
    text = workbook.add_format({**base, "text_wrap": True})
    qty = workbook.add_format(
        {**base, "num_format": '#,##0.0#####;[Red](#,##0.0#####);"-"'}
    )
    money = workbook.add_format({**base, "num_format": '#,##0.00;[Red](#,##0.00);"-"'})
    cost = workbook.add_format(
        {**base, "num_format": '#,##0.000000;[Red](#,##0.000000);"-"'}
    )
    header = workbook.add_format(
        {
            **base,
            "bold": True,
            "align": "center",
            "text_wrap": True,
            "bg_color": "#FFCC99",
        }
    )
    subheader = workbook.add_format(
        {**base, "bold": True, "align": "center", "bg_color": "#CCFFFF"}
    )
    total_text = workbook.add_format({**base, "bold": True, "bg_color": "#CCFFFF"})
    total_qty = workbook.add_format(
        {**base, "bold": True, "bg_color": "#CCFFFF", "num_format": qty.num_format}
    )
    total_money = workbook.add_format(
        {**base, "bold": True, "bg_color": "#CCFFFF", "num_format": money.num_format}
    )
    title = workbook.add_format({"font_name": "Calibri", "font_size": 12, "bold": True})
    note = workbook.add_format({"font_name": "Calibri", "font_size": 10})
    year, month = map(int, report.month.split("-"))
    closing_date = date(year, month, calendar.monthrange(year, month)[1])
    sheet = workbook.add_worksheet("Stock by Item")
    sheet.hide_gridlines(2)
    sheet.set_column(0, 0, 50)
    sheet.set_column(1, 1, 18)
    sheet.set_column(2, 2, 12)
    sheet.merge_range(0, 0, 0, 7, report.facility_name, title)
    sheet.merge_range(
        1,
        0,
        1,
        7,
        _("ITEM WISE STOCK VALUE AS ON %s") % closing_date.strftime("%d-%m-%Y"),
        title,
    )
    sheet.write_string(
        2, 0, _("Total stock value (%s)") % report.currency_id.name, note
    )
    sheet.merge_range(2, 2, 2, 3, _("Revision: %s") % report.period_id.state, note)
    sheet.merge_range(
        2,
        4,
        2,
        9,
        (
            _("Owned quantity includes internal stock in transit.")
            if snapshot.get("quantity_basis") == "owned"
            else _("Available stock quantity.")
        ),
        note,
    )
    for col, label in enumerate([_("Item"), _("Product ID"), _("Unit")]):
        sheet.write_blank(3, col, None, header)
        sheet.write_string(4, col, label, subheader)
    for index, key in enumerate(ordered_locations):
        col = 3 + index * 2
        label = (
            locations[key]
            if names[locations[key]] == 1
            else f"{locations[key]} ({key[:8]})"
        )
        sheet.merge_range(3, col, 3, col + 1, label, header)
        sheet.write_row(4, col, [_("QTY"), _("AMOUNT")], subheader)
        sheet.set_column(col, col, 12)
        sheet.set_column(col + 1, col + 1, 18)
    total_col = 3 + len(ordered_locations) * 2
    sheet.merge_range(3, total_col, 3, total_col + 1, _("TOTAL"), subheader)
    sheet.write_row(4, total_col, [_("QTY"), _("AMOUNT")], subheader)
    sheet.set_column(total_col, total_col, 16)
    sheet.set_column(total_col + 1, total_col + 1, 20)
    sheet.set_column(total_col + 2, total_col + 2, 39)
    sheet.write_blank(3, total_col + 2, None, header)
    sheet.write_string(4, total_col + 2, _("Care item UUID"), subheader)
    sheet.set_row(3, 42)
    sheet.set_row(4, 22)
    for row, item in enumerate(ordered_items, 5):
        key = item["item_uuid"]
        sheet.set_row(row, max(16, 14 * ceil(len(item["name"]) / 48)))
        unit = item.get("base_unit") or ""
        if isinstance(unit, dict):
            unit = unit.get("display") or unit.get("code") or ""
        sheet.write_string(row, 0, item["name"], text)
        sheet.write_number(row, 1, item["product_id"], text)
        sheet.write_string(row, 2, unit, text)
        sheet.write_string(row, total_col + 2, key, text)
        for index, location in enumerate(ordered_locations):
            quantity, value = balances[key, location]
            sheet.write_number(row, 3 + index * 2, float(quantity), qty)
            sheet.write_number(row, 4 + index * 2, float(value), money)
        for offset, fmt, result in [
            (0, total_qty, quantities[key]),
            (1, total_money, values[key]),
        ]:
            cells = ",".join(
                xl_rowcol_to_cell(row, col) for col in range(3 + offset, total_col, 2)
            )
            sheet.write_formula(
                row,
                total_col + offset,
                f"=SUM({cells})" if cells else "=0",
                fmt,
                float(result),
            )
    total_row = 5 + len(ordered_items)
    sheet.merge_range(total_row, 0, total_row, 2, _("TOTAL"), total_text)
    for col in range(3, total_col + 2):
        is_qty = (col - 3) % 2 == 0
        if col >= total_col:
            result = sum((quantities if is_qty else values).values(), Decimal(0))
        else:
            location = ordered_locations[(col - 3) // 2]
            result = sum(
                (
                    balances[item["item_uuid"], location][0 if is_qty else 1]
                    for item in ordered_items
                ),
                Decimal(0),
            )
        letter = xl_col_to_name(col)
        sheet.write_formula(
            total_row,
            col,
            f"=SUM({letter}6:{letter}{total_row})" if ordered_items else "=0",
            total_qty if is_qty else total_money,
            float(result),
        )
    sheet.write_formula(
        2,
        1,
        f"={xl_rowcol_to_cell(total_row, total_col + 1)}",
        money,
        float(snapshot["total_value"]),
    )
    sheet.freeze_panes(5, 3)
    sheet.autofilter(4, 0, max(4, total_row - 1), total_col + 2)
    sheet.set_landscape()
    sheet.set_paper(8)
    sheet.repeat_rows(0, 4)
    sheet.repeat_columns(0, 2)
    sheet.print_area(0, 0, total_row, total_col + 1)

    detail_sheet = workbook.add_worksheet("Batch and Location")
    detail_sheet.hide_gridlines(2)
    detail_sheet.merge_range(0, 0, 0, 7, report.facility_name, title)
    detail_sheet.merge_range(
        1,
        0,
        1,
        7,
        _("Saved Odoo valuation: %s (%s)") % (report.month, report.period_id.state),
        title,
    )
    detail_sheet.merge_range(
        2,
        0,
        2,
        7,
        _(
            "Product ID is the Odoo product. Care item UUID identifies the item; batch UUID identifies the Care batch."
        ),
        note,
    )
    fields = [
        "item",
        "product_id",
        "item_uuid",
        "batch",
        "batch_uuid",
        "expiry",
        "location",
        "location_uuid",
        "quantity",
        "available_quantity",
        "incoming_quantity",
        "effective_cost",
        "value",
    ]
    labels = [
        _("Item"),
        _("Product ID"),
        _("Care item UUID"),
        _("Batch"),
        _("Batch UUID"),
        _("Expiry"),
        _("Location"),
        _("Location UUID"),
        (
            _("Owned quantity")
            if snapshot.get("quantity_basis") == "owned"
            else _("Quantity")
        ),
        _("Available quantity"),
        _("Incoming quantity"),
        _("Effective unit cost"),
        _("Amount (%s)") % report.currency_id.name,
    ]
    detail_sheet.write_row(4, 0, labels, header)
    detail_sheet.set_row(4, 32)
    detail_sheet.set_column(0, 0, 50)
    detail_sheet.set_column(1, 1, 18)
    detail_sheet.set_column(2, 2, 39)
    detail_sheet.set_column(3, 3, 24)
    detail_sheet.set_column(4, 4, 39)
    detail_sheet.set_column(5, 5, 28)
    detail_sheet.set_column(6, 6, 32)
    detail_sheet.set_column(7, 7, 39)
    detail_sheet.set_column(8, 12, 22)
    for index, row in enumerate(
        sorted(
            details,
            key=lambda r: (
                items[r["item_uuid"]]["name"].casefold(),
                r["item_uuid"],
                r["location_uuid"],
                r["batch_uuid"],
            ),
        ),
        5,
    ):
        detail_sheet.set_row(
            index,
            max(
                16,
                14
                * max(
                    ceil(len(row["item"]) / 48),
                    ceil(len(row.get("batch") or "") / 22),
                    ceil(len(row["location"]) / 30),
                ),
            ),
        )
        for col, field in enumerate(fields):
            value = (
                items[row["item_uuid"]]["product_id"]
                if field == "product_id"
                else row.get(field, "")
            )
            if col == 1 or col >= 8:
                detail_sheet.write_number(
                    index,
                    col,
                    float(value),
                    (
                        money
                        if col == 12
                        else cost if col == 11 else qty if col >= 8 else text
                    ),
                )
            else:
                detail_sheet.write_string(index, col, str(value or ""), text)
    detail_sheet.freeze_panes(5, 1)
    detail_sheet.autofilter(4, 0, 4 + len(details), len(fields) - 1)
    workbook.close()
    return output.getvalue()
