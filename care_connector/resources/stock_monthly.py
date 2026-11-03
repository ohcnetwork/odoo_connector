"""Consecutive monthly native AVCO and immutable exports."""

import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from odoo.exceptions import ValidationError

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
                raise ValidationError("A closed inventory month cannot be replaced.")
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
        # Preserve closed reports and stop the next close for an explicit forward adjustment.
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
                        f"A purchase cost changed after freezing: {receipt['care_line_uuid']}. Review a forward-period adjustment; closed months remain unchanged."
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
        env["care.stock.close"].create(
            {
                "period_id": period.id,
                "month": data["stock_month"],
                "source_hash": data["source_hash"],
                "snapshot": snapshot,
            }
        )
        period.closed_through = at
        return {"snapshot": snapshot, "already_closed": False}

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
