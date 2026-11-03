import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from odoo.exceptions import AccessError, ValidationError

from odoo import Command


def decimal(value):
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise ValidationError("Stock quantities and values must be numeric.") from error
    if not result.is_finite():
        raise ValidationError("Stock quantities and values must be finite.")
    return result


def utc_date(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValidationError("Stock event dates must include a timezone.")
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


class StockSync:
    @classmethod
    def bill_sources(cls, env, data):
        cls.authorize(env)
        lines = data.get("care_line_uuids", [])
        orders = data.get("care_order_uuids", [])
        if len(lines) > 500 or len(orders) > 500:
            raise ValidationError("Read at most 500 Care IDs per request.")
        found = env["account.move.line"].search(
            [
                ("move_id.move_type", "in", ["in_invoice", "in_refund"]),
                ("display_type", "=", "product"),
                ("company_id", "=", env.company.id),
                "|",
                ("x_care_id", "in", lines),
                ("move_id.x_care_id", "in", orders),
            ]
        )
        return {
            "bill_lines": [
                {
                    "id": line.id,
                    "care_line_uuid": line.x_care_id or None,
                    "care_order_uuid": line.move_id.x_care_id or None,
                    "bill_id": line.move_id.id,
                    "bill_name": line.move_id.name,
                    "state": line.move_id.state,
                    "move_type": line.move_id.move_type,
                    "accounting_date": str(line.move_id.date),
                    "product_care_id": line.product_id.x_care_id or None,
                    "company_value": str(line.balance),
                    "received_packs": str(line.received_qty),
                    "billed_packs": str(line.quantity),
                    "free_packs": str(line.free_qty),
                    "discount_percent": str(line.discount),
                }
                for line in found
            ]
        }

    @staticmethod
    def authorize(env):
        if not env.user.has_group("stock.group_stock_manager"):
            raise AccessError(
                "Care stock sync requires Inventory Administrator access."
            )

    @classmethod
    def period(cls, env, data):
        cls.authorize(env)
        env.cr.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            [f"care-stock:{env.company.id}:{data['facility_uuid']}"],
        )
        model = env["care.stock.period"]
        period = model.search(
            [("key", "=", data["period_key"]), ("company_id", "=", env.company.id)],
            limit=1,
        )
        if not period:
            period = model.create(
                {
                    "key": data["period_key"],
                    "month": data["month"],
                    "facility_uuid": data["facility_uuid"],
                    "company_id": env.company.id,
                    "metadata": data.get("metadata", {}),
                    "mode": data.get("mode", "detailed"),
                }
            )
        if (
            period.month != data["month"]
            or period.facility_uuid != data["facility_uuid"]
            or period.mode != data.get("mode", "detailed")
        ):
            raise ValidationError(
                "The period key already belongs to a different source."
            )
        return period

    @classmethod
    def prepare(cls, env, data):
        period = cls.period(env, data)
        facility = period.facility_uuid
        if env["stock.move"].search_count(
            [
                ("company_id", "=", env.company.id),
                ("product_id.care_stock_facility_uuid", "=", facility),
                ("care_stock_period_id", "!=", period.id),
                ("state", "=", "done"),
            ],
            limit=1,
        ):
            raise ValidationError(
                "This facility already has an opening trial. Roll forward its prior closing stock; "
                "do not import another opening balance."
            )
        category = env["product.category"].search(
            [("name", "=", f"Care inventory {facility}")], limit=1
        )
        if not category:
            category = env["product.category"].create(
                {
                    "name": f"Care inventory {facility}",
                    "property_cost_method": "average",
                    "property_valuation": "periodic",
                }
            )
        env["decimal.precision"].search([("name", "=", "Product Price")]).write(
            {"digits": 12}
        )
        env["decimal.precision"].search([("name", "=", "Product Unit")]).write(
            {"digits": 6}
        )
        unit = env["uom.uom"].search([("name", "=", "Care base unit")], limit=1)
        if not unit:
            unit = env["uom.uom"].create(
                {"name": "Care base unit", "relative_factor": 1}
            )
        warehouse_code = "C" + facility.replace("-", "")[:4].upper()
        warehouse = env["stock.warehouse"].search(
            [
                ("company_id", "=", env.company.id),
                "|",
                ("name", "=", f"Care inventory {facility}"),
                ("lot_stock_id.child_ids.care_stock_facility_uuid", "=", facility),
            ],
            limit=1,
        )
        if not warehouse:
            attempt = 0
            while env["stock.warehouse"].search_count(
                [
                    ("company_id", "=", env.company.id),
                    ("code", "=", warehouse_code),
                ],
                limit=1,
            ):
                attempt += 1
                if attempt > 256:
                    raise ValidationError("No free Care warehouse code is available.")
                warehouse_code = (
                    "C"
                    + hashlib.sha256(f"{facility}:{attempt}".encode())
                    .hexdigest()[:4]
                    .upper()
                )
            warehouse = env["stock.warehouse"].create(
                {
                    "name": f"Care inventory {facility}",
                    "code": warehouse_code,
                    "company_id": env.company.id,
                }
            )
        location_map = dict(period.location_map or {})
        for key, name, usage in [
            ("external", "Care external stock", "supplier"),
            ("consumption", "Care consumption", "customer"),
            ("adjustment", "Care stock adjustments", "inventory"),
            ("transit", "Care stock outside valued stores", "supplier"),
        ]:
            if key not in location_map:
                location = env["stock.location"].create(
                    {"name": name, "usage": usage, "company_id": env.company.id}
                )
                location_map[key] = location.id
        for source in data.get("locations", []):
            identity = (
                f"{facility}:{source['uuid']}"
                if period.mode == "monthly"
                else source["uuid"]
            )
            location = env["stock.location"].search(
                [
                    ("care_stock_location_uuid", "=", identity),
                    ("company_id", "=", env.company.id),
                ],
                limit=1,
            )
            if not location and period.mode == "monthly":
                location = env["stock.location"].search(
                    [
                        ("care_stock_location_uuid", "=", source["uuid"]),
                        ("care_stock_facility_uuid", "=", facility),
                        ("company_id", "=", env.company.id),
                    ],
                    limit=1,
                )
                if location:
                    location.care_stock_location_uuid = identity
            if not location:
                location = env["stock.location"].create(
                    {
                        "name": source["name"],
                        "usage": "internal",
                        "company_id": env.company.id,
                        "location_id": warehouse.lot_stock_id.id,
                        "care_stock_location_uuid": identity,
                        "care_stock_facility_uuid": facility,
                    }
                )
            location_map[source["uuid"]] = location.id
        period.location_map = location_map
        product_map = {}
        for source in data.get("items", []):
            product = env["product.product"].search(
                [
                    ("care_stock_item_uuid", "=", source["uuid"]),
                    ("care_stock_facility_uuid", "=", facility),
                    ("company_id", "=", env.company.id),
                ],
                limit=1,
            )
            if not product:
                product = (
                    env["product.product"]
                    .with_context(disable_auto_revaluation=True)
                    .create(
                        {
                            "name": source["name"],
                            "care_stock_item_uuid": source["uuid"],
                            "care_stock_facility_uuid": facility,
                            "company_id": env.company.id,
                            "type": "consu",
                            "is_storable": True,
                            "tracking": "none" if period.mode == "monthly" else "lot",
                            "lot_valuated": False,
                            "uom_id": unit.id,
                            "categ_id": category.id,
                        }
                    )
                )
                opening_rate = float(decimal(source.get("opening_unit_cost", "0")))
                product.with_context(
                    disable_auto_revaluation=True
                ).standard_price = opening_rate
                seed = {
                    "product_id": product.id,
                    "value": opening_rate,
                    "date": utc_date(data["opening_at"]) - timedelta(seconds=1),
                    "description": f"Care opening rate: {period.key}",
                }
                # Product creation records a zero-price history entry dated
                # today. Date that new product's initial history at the opening
                # boundary, otherwise it overrides every backdated receipt.
                initial_history = env["product.value"].search(
                    [
                        ("product_id", "=", product.id),
                        ("move_id", "=", False),
                        ("lot_id", "=", False),
                    ]
                )
                if initial_history:
                    initial_history.write(seed)
                else:
                    env["product.value"].create(seed)
            product_map[source["uuid"]] = product
        for source in data.get("batches", []):
            product = product_map.get(source["item_uuid"]) or env[
                "product.product"
            ].search(
                [
                    ("care_stock_item_uuid", "=", source["item_uuid"]),
                    ("care_stock_facility_uuid", "=", facility),
                    ("company_id", "=", env.company.id),
                ],
                limit=1,
            )
            if not product:
                raise ValidationError("Prepare the Care stock item before its batch.")
            lot = env["stock.lot"].search(
                [
                    ("care_stock_batch_uuid", "=", source["uuid"]),
                    ("company_id", "=", env.company.id),
                ],
                limit=1,
            )
            if not lot:
                env["stock.lot"].create(
                    {
                        "name": f"{source.get('lot_number') or 'Care batch'} [{source['uuid'][:8]}]",
                        "product_id": product.id,
                        "company_id": env.company.id,
                        "care_stock_batch_uuid": source["uuid"],
                    }
                )
            elif lot.product_id != product:
                raise ValidationError(
                    "The Care batch is already linked to another stock item."
                )
        return {
            "period_id": period.id,
            "prepared_items": len(data.get("items", [])),
            "prepared_batches": len(data.get("batches", [])),
        }

    @classmethod
    def events(cls, env, data):
        period = cls.period(env, data)
        events = data.get("events", [])
        if len(events) > 500:
            raise ValidationError("Post at most 500 stock events per request.")
        existing = {
            m.care_stock_key: m
            for m in env["stock.move"].search(
                [
                    ("care_stock_key", "in", [e["key"] for e in events]),
                    ("company_id", "=", env.company.id),
                ]
            )
        }
        lots = {
            lot.care_stock_batch_uuid: lot
            for lot in env["stock.lot"].search(
                [
                    (
                        "care_stock_batch_uuid",
                        "in",
                        list({e["batch_uuid"] for e in events if e.get("batch_uuid")}),
                    ),
                    ("company_id", "=", env.company.id),
                ]
            )
        }
        products = (
            {
                product.care_stock_item_uuid: product
                for product in env["product.product"].search(
                    [
                        (
                            "care_stock_item_uuid",
                            "in",
                            list({e.get("item_uuid") for e in events} - {None}),
                        ),
                        ("care_stock_facility_uuid", "=", period.facility_uuid),
                        ("company_id", "=", env.company.id),
                    ]
                )
            }
            if period.mode == "monthly"
            else {}
        )
        bill_ids = list({i for e in events for i in e.get("bill_line_ids", [])})
        bills = {
            line.id: line for line in env["account.move.line"].browse(bill_ids).exists()
        }
        allocations = defaultdict(Decimal)
        for previous in env["stock.move"].search(
            [
                ("care_stock_period_id", "=", period.id),
                ("care_stock_bill_line_ids", "in", bill_ids),
            ]
        ):
            evidence = previous.care_stock_evidence
            for receipt in evidence.get("receipts", [evidence]):
                for line_id in receipt.get("bill_line_ids", []):
                    allocations[line_id] += decimal(receipt.get("bill_fraction", "1"))
        values = []
        dates = defaultdict(list)
        seen = set()
        for event in events:
            if event["key"] in seen:
                raise ValidationError("Duplicate event key within the request.")
            seen.add(event["key"])
            digest = hashlib.sha256(
                json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            if event["key"] in existing:
                if (
                    existing[event["key"]].state != "done"
                    or existing[event["key"]].care_stock_hash != digest
                ):
                    raise ValidationError(
                        "A completed Care event cannot be changed by retrying it."
                    )
                continue
            quantity = decimal(event["quantity"])
            if quantity <= 0:
                raise ValidationError(
                    "Stock event quantities must be positive; express direction with locations."
                )
            if (
                period.closed_through
                and utc_date(event["date"]) <= period.closed_through
            ):
                raise ValidationError(
                    "A closed Care stock month cannot receive new movements."
                )
            lot = lots.get(event.get("batch_uuid"))
            product = (
                products.get(event.get("item_uuid"))
                if period.mode == "monthly"
                else lot.product_id
                if lot
                else None
            )
            if not product or product.care_stock_facility_uuid != period.facility_uuid:
                raise ValidationError(
                    "The Care stock batch has not been prepared for this facility."
                )
            source = period.location_map.get(event["source"])
            destination = period.location_map.get(event["destination"])
            if not source or not destination or source == destination:
                raise ValidationError(
                    "Stock events need two distinct prepared locations."
                )
            basis = event.get("cost_basis", "native_average")
            value = Decimal(0)
            linked = []
            if basis == "monthly_receipt":
                if (
                    period.mode != "monthly"
                    or event["source"] != "external"
                    or event["destination"] != "valuation"
                ):
                    raise ValidationError(
                        "Monthly receipt values require the valuation location."
                    )
                received = Decimal(0)
                for receipt in event.get("receipts", []):
                    received += decimal(receipt["quantity"])
                    if receipt["cost_basis"] == "posted_bill":
                        fraction = decimal(receipt.get("bill_fraction", "1"))
                        if not 0 <= fraction <= 1:
                            raise ValidationError("Invalid bill allocation fraction.")
                        amount = Decimal(0)
                        for line_id in receipt.get("bill_line_ids", []):
                            line = bills.get(line_id)
                            if (
                                not line
                                or line.move_id.state != "posted"
                                or line.move_id.move_type != "in_invoice"
                                or line.company_id != env.company
                            ):
                                raise ValidationError(
                                    "Monthly costs require posted vendor bill lines in this company."
                                )
                            if not (
                                (
                                    receipt.get("care_line_uuid")
                                    and line.x_care_id == receipt["care_line_uuid"]
                                )
                                or (
                                    receipt.get("care_order_uuid")
                                    and line.move_id.x_care_id
                                    == receipt["care_order_uuid"]
                                )
                            ):
                                raise ValidationError(
                                    "The bill is not linked to this Care receipt/order."
                                )
                            allocations[line_id] += fraction
                            if allocations[line_id] > Decimal("1.000000000001"):
                                raise ValidationError(
                                    "A vendor bill line cannot be allocated more than once."
                                )
                            amount += decimal(line.balance) * fraction
                            linked.append(line_id)
                        if not receipt.get("bill_line_ids") or abs(
                            amount - decimal(receipt["input_value"])
                        ) > Decimal("0.005"):
                            raise ValidationError(
                                "The posted bill value changed since the monthly plan was frozen."
                            )
                    elif receipt["cost_basis"] == "care_unmatched":
                        amount = decimal(receipt["input_value"])
                    else:
                        raise ValidationError("Unknown monthly receipt cost source.")
                    value += amount
                if received != quantity or abs(
                    value - decimal(event["input_value"])
                ) > Decimal("0.005"):
                    raise ValidationError(
                        "Monthly receipts do not reconcile to the summary quantity/value."
                    )
            elif basis == "posted_bill":
                fraction = decimal(event.get("bill_fraction", "1"))
                if fraction < 0 or fraction > 1:
                    raise ValidationError(
                        "Bill allocation fractions must be between zero and one."
                    )
                for line_id in event.get("bill_line_ids", []):
                    line = bills.get(line_id)
                    if (
                        not line
                        or line.move_id.state != "posted"
                        or line.move_id.move_type != "in_invoice"
                        or line.company_id != env.company
                    ):
                        raise ValidationError(
                            "Receipt costs require posted vendor bill lines in this company."
                        )
                    linked.append(line.id)
                    if not (
                        line.x_care_id == event.get("care_line_uuid")
                        or line.move_id.x_care_id == event.get("care_order_uuid")
                    ):
                        raise ValidationError(
                            "The vendor bill is not linked to this Care receipt/order."
                        )
                    allocations[line.id] += fraction
                    if allocations[line.id] > Decimal("1.000000000001"):
                        raise ValidationError(
                            "A vendor bill line cannot be allocated more than once."
                        )
                    value += decimal(line.balance) * fraction
                if not linked:
                    raise ValidationError(
                        "A bill-valued receipt needs at least one posted bill line."
                    )
                if abs(value - decimal(event["input_value"])) > Decimal("0.005"):
                    raise ValidationError(
                        "The posted bill value changed since the Care plan was prepared."
                    )
            elif basis in {"opening", "care_legacy", "care_unmatched"}:
                value = decimal(event["input_value"])
            else:
                if period.mode == "monthly":
                    at = utc_date(event["date"])
                    cutoff = (
                        at
                        if event["kind"] == "opening_negative"
                        else at - timedelta(seconds=1)
                    )
                    # All recoveries use the native post-purchase monthly rate.
                    # Querying before their phase avoids batch-dependent penny drift.
                    average = product._run_avco(at_date=cutoff)[0]
                    value = decimal(average) * quantity
                else:
                    value = decimal(product.standard_price) * quantity
            vals = {
                "inventory_name": event.get("description", event["key"]),
                "company_id": env.company.id,
                "product_id": product.id,
                "product_uom": product.uom_id.id,
                "product_uom_qty": float(quantity),
                "location_id": source,
                "location_dest_id": destination,
                "care_stock_key": event["key"],
                "care_stock_hash": digest,
                "care_stock_period_id": period.id,
                "care_stock_kind": event["kind"],
                "care_stock_cost_basis": basis,
                "care_stock_input_value": float(value),
                "care_stock_bill_line_ids": [Command.set(linked)],
                "care_stock_evidence": event,
                "move_line_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_id": product.uom_id.id,
                            "location_id": source,
                            "location_dest_id": destination,
                            "lot_id": lot.id if lot else False,
                            "quantity": float(quantity),
                            "picked": True,
                        }
                    )
                ],
            }
            dates[utc_date(event["date"])].append(len(values))
            values.append(vals)
        moves = env["stock.move"].create(values)
        if moves:
            moves._action_confirm(merge=False)
            moves.picked = True
            done = moves._action_done()
            if set(done.ids) != set(moves.ids) or any(
                move.state != "done" for move in moves
            ):
                raise ValidationError(
                    "Odoo did not complete every stock event in the batch."
                )
            for date, indices in dates.items():
                env["stock.move"].browse([moves[i].id for i in indices]).write(
                    {"date": date}
                )
            moves.product_id._update_standard_price()
        return {
            "posted": len(moves),
            "already_posted": len(existing),
            "requested": len(events),
        }

    @classmethod
    def report(cls, env, data):
        period = cls.period(env, data)
        domain = [
            ("care_stock_facility_uuid", "=", period.facility_uuid),
            ("company_id", "=", env.company.id),
        ]
        if data.get("item_uuids"):
            domain.append(("care_stock_item_uuid", "in", data["item_uuids"]))
        at_date = utc_date(data["as_of"]) if data.get("as_of") else None
        rows = []
        for product in env["product.product"].search(domain):
            historic = product.with_context(to_date=at_date) if at_date else product
            average, value = product._run_avco(at_date=at_date)
            rows.append(
                {
                    "item_uuid": product.care_stock_item_uuid,
                    "product_id": product.id,
                    "quantity": historic.qty_available,
                    "average_cost": average,
                    "value": value,
                    "reported_total_value": historic.total_value,
                    "current_cost": product.standard_price,
                }
            )
        return {"items": rows, "period_id": period.id}
