"""Monthly native AVCO, detailed reports and replaceable valuation series."""

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from odoo.exceptions import ValidationError

from odoo import Command, fields

from .stock_sync import StockSync, decimal, utc_date


def bounds(month):
    first = datetime.strptime(month, "%Y-%m").replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    if first.strftime("%Y-%m") != month:
        raise ValidationError("Month must be YYYY-MM.")
    return first, first.replace(
        year=first.year + (first.month == 12), month=first.month % 12 + 1
    )


class MonthlyStockSync:
    @classmethod
    def check(cls, env, data, allow_closed=False):
        period = StockSync.period(env, data)
        if period.mode != "monthly":
            raise ValidationError("This operation requires a monthly valuation ledger.")
        if period.state == "archived" and not allow_closed:
            raise ValidationError(
                "This revision is archived. Rebuild the current series to make corrections."
            )
        month = data["stock_month"]
        start, end = bounds(month)
        latest = env["care.stock.close"].search(
            [("period_id", "=", period.id)], order="month desc", limit=1
        )
        expected = bounds(latest.month)[1].strftime("%Y-%m") if latest else period.month
        closed = (
            env["care.stock.close"].search_count(
                [
                    ("period_id", "=", period.id),
                    ("month", "=", month),
                ],
                limit=1,
            )
            if allow_closed
            else False
        )
        if month != expected and not closed:
            raise ValidationError(
                f"Close months consecutively. Next month: {expected}."
            )
        return period, start, end

    @classmethod
    def prepare(cls, env, data):
        period, _start, _end = cls.check(env, data)
        return StockSync.prepare(
            env,
            {
                **data,
                "locations": [{"uuid": "valuation", "name": "Care monthly valuation"}],
                "batches": [],
            },
        )

    @classmethod
    def events(cls, env, data):
        period, start, end = cls.check(env, data, allow_closed=True)
        if period.state == "archived":
            raise ValidationError(
                "This revision is archived. Its saved reports remain available."
            )
        for event in data.get("events", []):
            at = utc_date(event["date"])
            opening = event["kind"] in {"opening", "opening_negative"}
            if (event["source"] == "valuation") == (
                event["destination"] == "valuation"
            ):
                raise ValidationError(
                    "A monthly movement must cross the valuation boundary."
                )
            expected_basis = (
                "opening"
                if event["kind"] == "opening"
                else "monthly_receipt"
                if event["kind"] == "receipt"
                else "native_average"
            )
            if event.get("cost_basis") != expected_basis:
                raise ValidationError("The monthly movement has an invalid cost basis.")
            if opening:
                if data["stock_month"] != period.month or at != utc_date(
                    (start - timedelta(seconds=1)).isoformat()
                ):
                    raise ValidationError(
                        "Only the first month can import the approved opening."
                    )
            elif not utc_date(start.isoformat()) <= at < utc_date(end.isoformat()):
                raise ValidationError("A movement is outside its stated month.")
        return StockSync.events(env, data)

    @classmethod
    def close(cls, env, data):
        period, start, end = cls.check(env, data, allow_closed=True)
        request_hash = hashlib.sha256(
            json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        existing = env["care.stock.close"].search(
            [("period_id", "=", period.id), ("month", "=", data["stock_month"])],
            limit=1,
        )
        if existing:
            if existing.snapshot["request_hash"] != request_hash:
                raise ValidationError(
                    "Use a new revision to rebuild this month and subsequent months."
                )
            return {"snapshot": existing.snapshot, "already_closed": True}
        cls.check(env, data)
        at = utc_date((end - timedelta(seconds=1)).isoformat())
        domain = [
            ("care_stock_period_id", "=", period.id),
            ("state", "=", "done"),
            ("date", "<=", at),
        ]
        if data["stock_month"] != period.month:
            domain.append(("date", ">=", utc_date(start.isoformat())))
        actual_keys = set(env["stock.move"].search(domain).mapped("care_stock_key"))
        if actual_keys != set(data["event_keys"]):
            raise ValidationError(
                "The month's completed stock events do not match its frozen Care plan."
            )
        if env["stock.move"].search_count(
            [("care_stock_period_id", "=", period.id), ("date", ">", at)], limit=1
        ):
            raise ValidationError(
                "A later month was posted before this month was closed."
            )
        # Bills may be corrected in Odoo without an update arriving in Care.
        # A rebuild re-reads corrected costs for the whole series.
        for move in env["stock.move"].search(
            [
                ("care_stock_period_id", "=", period.id),
                ("care_stock_cost_basis", "=", "monthly_receipt"),
            ]
        ):
            for receipt in move.care_stock_evidence.get("receipts", []):
                if receipt["cost_basis"] != "posted_bill":
                    continue
                lines = (
                    env["account.move.line"].browse(receipt["bill_line_ids"]).exists()
                )
                amount = sum(
                    (decimal(line.balance) for line in lines), Decimal(0)
                ) * decimal(receipt.get("bill_fraction", "1"))
                if (
                    len(lines) != len(receipt["bill_line_ids"])
                    or any(line.move_id.state != "posted" for line in lines)
                    or abs(amount - decimal(receipt["input_value"])) > Decimal("0.005")
                ):
                    raise ValidationError(
                        f"A purchase cost changed: {receipt['care_line_uuid']}. Rebuild the series to apply the correction."
                    )
        rows = StockSync.report(
            env, {**data, "as_of": (end - timedelta(seconds=1)).isoformat()}
        )["items"]
        expected = data["closing_quantities"]
        names = {item["uuid"]: item for item in data["items"]}
        for row in rows:
            if abs(
                decimal(row["quantity"]) - decimal(expected.get(row["item_uuid"], 0))
            ) > Decimal("0.000001"):
                raise ValidationError(
                    f"Care/Odoo closing quantity differs for {row['item_uuid']}."
                )
            row.update(
                {
                    "name": names[row["item_uuid"]]["name"],
                    "base_unit": names[row["item_uuid"]].get("base_unit"),
                }
            )
            if data.get("quantity_basis") == "owned":
                available = decimal(
                    data["available_quantities"].get(row["item_uuid"], 0)
                )
                transit = decimal(
                    data["in_transit_quantities"].get(row["item_uuid"], 0)
                )
                if abs(available + transit - decimal(row["quantity"])) > Decimal(
                    "0.000001"
                ):
                    raise ValidationError(
                        "Available stock plus internal transit must equal owned stock."
                    )
                row.update(
                    {
                        "available_quantity": float(available),
                        "in_transit_quantity": float(transit),
                    }
                )
        if set(expected) - {row["item_uuid"] for row in rows}:
            raise ValidationError("A Care item is missing from Odoo.")
        snapshot = {
            "month": data["stock_month"],
            "quantity_basis": data.get("quantity_basis", "available"),
            "as_of": (end - timedelta(seconds=1)).isoformat(),
            "request_hash": request_hash,
            "source_hash": data["source_hash"],
            "location_uuids": data["location_uuids"],
            "items": rows,
            "total_value": str(
                sum((decimal(r["reported_total_value"]) for r in rows), Decimal(0))
            ),
        }
        if "stock_details" in data:
            snapshot["details"] = cls.details(env, data["stock_details"], rows)
        env["care.stock.close"].create(
            {
                "period_id": period.id,
                "month": data["stock_month"],
                "source_hash": data["source_hash"],
                "snapshot": snapshot,
                "line_ids": [
                    Command.create(row) for row in snapshot.get("details", [])
                ],
            }
        )
        period.closed_through = at
        return {"snapshot": snapshot, "already_closed": False}

    @staticmethod
    def details(env, dimensions, items):
        """Validate Care dimensions and allocate native rounded item values exactly."""
        groups, seen = defaultdict(list), set()
        known = {item["item_uuid"]: item for item in items}
        for source in dimensions:
            key = (source["item_uuid"], source["batch_uuid"], source["location_uuid"])
            if key in seen or key[0] not in known:
                raise ValidationError(
                    "Report dimensions contain duplicate or unknown stock identities."
                )
            seen.add(key)
            quantity, incoming = (
                decimal(source["quantity"]),
                decimal(source["incoming_quantity"]),
            )
            if incoming < 0:
                raise ValidationError("Incoming stock cannot be negative.")
            groups[key[0]].append(
                {
                    "item_uuid": key[0],
                    "item": known[key[0]]["name"],
                    "batch_uuid": key[1],
                    "batch": source.get("batch") or "",
                    "expiry": source.get("expiry") or "",
                    "location_uuid": key[2],
                    "location": source["location"],
                    "quantity": str(quantity),
                    "incoming_quantity": str(incoming),
                    "available_quantity": str(quantity - incoming),
                    "effective_cost": str(known[key[0]]["average_cost"]),
                }
            )
        result = []
        currency = env.company.currency_id
        step = decimal(currency.rounding)
        for item in items:
            rows = groups[item["item_uuid"]]
            if abs(
                sum((decimal(row["quantity"]) for row in rows), Decimal(0))
                - decimal(item["quantity"])
            ) > Decimal("0.000001") or abs(
                sum((decimal(row["incoming_quantity"]) for row in rows), Decimal(0))
                - decimal(item.get("in_transit_quantity", 0))
            ) > Decimal("0.000001"):
                raise ValidationError(
                    "Batch/location quantities do not reconcile with the product totals."
                )
            raw = [
                decimal(row["quantity"]) * decimal(item["average_cost"]) for row in rows
            ]
            values = [decimal(currency.round(float(value))) for value in raw]
            delta = int(
                (decimal(item["reported_total_value"]) - sum(values, Decimal(0))) / step
            )
            if delta and not rows:
                raise ValidationError("An item value has no batch/location allocation.")
            order = sorted(
                range(len(rows)),
                key=lambda i: (raw[i] - values[i], i),
                reverse=delta > 0,
            )
            for index in range(abs(delta)):
                values[order[index % len(order)]] += step if delta > 0 else -step
            result.extend(
                {**row, "value": str(value)} for row, value in zip(rows, values)
            )
        return result

    @staticmethod
    def current(env, data):
        StockSync.authorize(env)
        env.cr.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            [f"care-stock:{env.company.id}:{data['facility_uuid']}"],
        )
        period = env["care.stock.period"].search(
            [
                ("facility_uuid", "=", data["facility_uuid"]),
                ("company_id", "=", env.company.id),
                ("mode", "=", "monthly"),
                ("state", "=", "current"),
            ]
        )
        if len(period) > 1:
            raise ValidationError(
                "More than one current valuation series exists for this facility."
            )
        latest = (
            env["care.stock.close"].search(
                [("period_id", "=", period.id)], order="month desc", limit=1
            )
            if period
            else None
        )
        return {
            "period_key": period.key if period else None,
            "through_month": latest.month if latest else None,
        }

    @classmethod
    def publish(cls, env, data):
        period = StockSync.period(env, data)
        if period.mode != "monthly" or period.state == "archived":
            raise ValidationError(
                "Only a current or building monthly series can be published."
            )
        through = data["through_month"]
        bounds(through)
        closes = env["care.stock.close"].search(
            [("period_id", "=", period.id)], order="month"
        )
        if period.state == "current":
            if not closes or closes[-1].month < through:
                raise ValidationError(
                    "Complete the requested months before publishing."
                )
            return {"published": True, "already_current": True}
        expected, month = [], period.month
        while month <= through:
            expected.append(month)
            month = bounds(month)[1].strftime("%Y-%m")
        if not expected or closes.mapped("month") != expected:
            raise ValidationError(
                "Complete every required month before publishing the replacement."
            )
        current = cls.current(env, data)
        if current["period_key"] != data.get("replaces_period_key"):
            raise ValidationError(
                "The current revision changed while rebuilding. Rerun against the current series."
            )
        if current["through_month"] and current["through_month"] > through:
            raise ValidationError(
                "Complete all subsequent months before replacing the current series."
            )
        old_periods = env["care.stock.period"].search(
            [
                ("facility_uuid", "=", period.facility_uuid),
                ("company_id", "=", env.company.id),
                ("mode", "=", "monthly"),
                ("id", "!=", period.id),
                ("state", "!=", "archived"),
            ]
        )
        # Native stock is retired as part of this same transaction. Merely
        # archiving report records would leave its quantities counted twice.
        for old in old_periods:
            products = (
                env["product.product"]
                .with_context(active_test=False)
                .search([("care_stock_period_id", "=", old.id)])
            )
            events = []
            for product in products:
                quantity = decimal(product.qty_available)
                if abs(quantity) < Decimal("0.0000005"):
                    continue
                events.append(
                    {
                        "key": f"{old.key}:archive:{product.id}",
                        "item_uuid": product.care_stock_item_uuid,
                        "quantity": str(abs(quantity)),
                        "date": fields.Datetime.now()
                        .replace(tzinfo=ZoneInfo("UTC"))
                        .isoformat(),
                        "source": "valuation" if quantity > 0 else "adjustment",
                        "destination": "adjustment" if quantity > 0 else "valuation",
                        "kind": "archive",
                        "cost_basis": "native_average",
                    }
                )
            for offset in range(0, len(events), 500):
                StockSync.events(
                    env,
                    {
                        "period_key": old.key,
                        "facility_uuid": old.facility_uuid,
                        "month": old.month,
                        "mode": "monthly",
                        "events": events[offset : offset + 500],
                    },
                )
            if any(abs(product.qty_available) > 0.000001 for product in products):
                raise ValidationError(
                    "The previous native stock balance could not be retired."
                )
            products.write({"active": False})
        old_periods.write({"state": "archived"})
        env["product.product"].with_context(active_test=False).search(
            [("care_stock_period_id", "=", period.id)]
        ).write({"active": True})
        period.state = "current"
        return {"published": True, "already_current": False}

    @classmethod
    def snapshot(cls, env, data):
        period = StockSync.period(env, data)
        closed = env["care.stock.close"].search(
            [("period_id", "=", period.id), ("month", "=", data["stock_month"])],
            limit=1,
        )
        if not closed:
            raise ValidationError("This inventory month is not closed.")
        return {"snapshot": closed.snapshot}

    @classmethod
    def status(cls, env, data):
        period = StockSync.period(env, data)
        closed = env["care.stock.close"].search(
            [
                ("period_id", "=", period.id),
                ("month", "=", data["stock_month"]),
            ],
            limit=1,
        )
        return {"closed": bool(closed), "snapshot": closed.snapshot if closed else None}
