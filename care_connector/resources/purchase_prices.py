"""Purchase-only monthly averages; no inventory moves or closing-stock inputs."""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal, localcontext

from pydantic import ValidationError as SchemaError

from odoo.exceptions import AccessError, ValidationError

from ..pydantic_models.purchase import CarePurchaseData, PurchaseMetadataRequest


def number(value):
    return Decimal(str(value or 0))


class PurchasePrices:
    @staticmethod
    def company_env(env, company_id=None):
        if not (
            env.user.has_group("account.group_account_invoice")
            or env.user.has_group("account.group_account_readonly")
        ):
            raise AccessError("Vendor bill access is required to read purchase prices.")
        try:
            company_id = (
                int(company_id) if company_id is not None else env.user.company_id.id
            )
        except (TypeError, ValueError) as error:
            raise ValidationError("company_id must be an integer.") from error
        if company_id not in env.user.company_ids.ids:
            raise AccessError("You do not have access to this company.")
        return env(context={**env.context, "allowed_company_ids": [company_id]})

    @staticmethod
    def months(data):
        def parse(value):
            try:
                parsed = datetime.strptime(value, "%Y-%m").date()
            except (TypeError, ValueError) as error:
                raise ValidationError("Months must be YYYY-MM.") from error
            if parsed.strftime("%Y-%m") != value:
                raise ValidationError("Months must be YYYY-MM.")
            return parsed

        start = parse(data.get("from_month"))
        last = parse(data.get("to_month", data.get("from_month")))
        count = (last.year - start.year) * 12 + last.month - start.month + 1
        if not 1 <= count <= 12:
            raise ValidationError("Request between one and twelve consecutive months.")
        months = []
        end = start
        for _ in range(count):
            months.append(end.strftime("%Y-%m"))
            end = end.replace(
                year=end.year + (end.month == 12), month=end.month % 12 + 1
            )
        return start, end, months

    @classmethod
    def metadata(cls, env, data):
        request = PurchaseMetadataRequest.model_validate(data)
        env = cls.company_env(env, request.company_id)
        if not env.user.has_group("account.group_account_invoice"):
            raise AccessError(
                "Vendor bill editing access is required to update purchase metadata."
            )
        lines = env["account.move.line"].search(
            [
                ("company_id", "=", env.company.id),
                ("move_id.move_type", "=", "in_invoice"),
                ("display_type", "=", "product"),
                ("x_care_id", "in", [str(e.care_line_uuid) for e in request.entries]),
            ]
        )
        by_receipt = defaultdict(lambda: env["account.move.line"])
        for line in lines:
            by_receipt[line.x_care_id] |= line
        results = []
        for entry in request.entries:
            candidates = by_receipt[str(entry.care_line_uuid)]
            # A cancelled predecessor is not the current bill for a receipt.
            candidates = candidates.filtered(
                lambda line: line.move_id.state != "cancel"
            )
            reason = None
            if len(candidates) != 1:
                reason = (
                    "bill_line_not_found" if not candidates else "ambiguous_bill_lines"
                )
            elif candidates.product_id.x_care_id != str(
                entry.care_purchase.charge_definition_uuid
            ):
                reason = "billing_product_mismatch"
            if reason:
                results.append(
                    {"care_line_uuid": str(entry.care_line_uuid), "status": reason}
                )
                continue
            value = entry.care_purchase.model_dump(mode="json")
            changed = candidates.care_purchase != value
            if changed:
                candidates.write({"care_purchase": value})
            results.append(
                {
                    "care_line_uuid": str(entry.care_line_uuid),
                    "bill_line_id": candidates.id,
                    "status": "updated" if changed else "unchanged",
                }
            )
        return {"company_id": env.company.id, "results": results}

    @classmethod
    def read(cls, env, data):
        env = cls.company_env(env, data.get("company_id"))
        start, end, months = cls.months(data)
        lines = env["account.move.line"].search(
            [
                ("company_id", "=", env.company.id),
                ("move_id.move_type", "=", "in_invoice"),
                ("move_id.state", "=", "posted"),
                ("move_id.invoice_date", ">=", start),
                ("move_id.invoice_date", "<", end),
                ("display_type", "=", "product"),
            ],
            order="date, move_id, id",
        )
        result = {
            "company_id": env.company.id,
            "currency": env.company.currency_id.name,
            "method": "purchase_only_weighted_average",
            "date_basis": "invoice_date",
            "quantity_unit": "care_base_unit",
            "months": [],
        }
        with localcontext() as context:
            context.prec = 50
            by_month = defaultdict(list)
            for line in lines:
                by_month[line.move_id.invoice_date.strftime("%Y-%m")].append(line)
            for month in months:
                result["months"].append(cls.month(month, by_month[month]))
        return result

    @staticmethod
    def month(month, lines):
        groups = {}
        unmapped = []
        total = Decimal(0)
        for line in lines:
            value = number(line.balance)
            total += value
            try:
                metadata = CarePurchaseData.model_validate(line.care_purchase or {})
                if not line.product_id or line.product_id.x_care_id != str(
                    metadata.charge_definition_uuid
                ):
                    raise ValueError("billing_product_mismatch")
                if not (
                    metadata.base_unit.get("code") or metadata.base_unit.get("display")
                ):
                    raise ValueError("missing_base_unit")
            except (SchemaError, ValueError) as error:
                unmapped.append(
                    {
                        "bill_line_id": line.id,
                        "bill_id": line.move_id.id,
                        "care_line_uuid": line.x_care_id or None,
                        "odoo_product_id": line.product_id.id or None,
                        "care_charge_definition_uuid": line.product_id.x_care_id
                        or None,
                        "net_purchase_value": str(value),
                        "reason": "missing_or_invalid_care_metadata"
                        if isinstance(error, SchemaError)
                        else str(error),
                    }
                )
                continue
            key = str(metadata.facility_uuid), str(metadata.item_uuid)
            group = groups.setdefault(
                key,
                {"metadata": metadata, "batches": {}, "units": set(), "flags": set()},
            )
            unit = metadata.base_unit
            group["units"].add(
                (unit.get("system", ""), unit.get("code") or unit["display"])
            )
            batch_key = str(metadata.product_uuid)
            batch = group["batches"].setdefault(
                batch_key,
                {
                    "care_product_id": metadata.product_id,
                    "care_product_uuid": batch_key,
                    "batch": metadata.batch,
                    "received_base_units": Decimal(0),
                    "free_base_units": Decimal(0),
                    "net_purchase_value": Decimal(0),
                    "bill_line_ids": [],
                    "flags": set(),
                },
            )
            if (
                batch["care_product_id"] != metadata.product_id
                or batch["batch"] != metadata.batch
            ):
                batch["flags"].add("conflicting_batch_identity")
            received, billed, free = (
                number(v) for v in (line.received_qty, line.quantity, line.free_qty)
            )
            # Manual Odoo bills may not populate the connector's received field.
            if received == 0 and billed + free > 0:
                received = billed + free
                batch["flags"].add("received_quantity_inferred_from_billed_plus_free")
            elif abs(received - billed - free) > Decimal("0.000001"):
                batch["flags"].add("received_quantity_differs_from_billed_plus_free")
            factor = number(line.product_uom_id.factor or 1) / number(
                line.product_id.uom_id.factor or 1
            )
            quantity = received * factor * metadata.pack_size
            if abs(quantity - metadata.received_base_units) > Decimal("0.000001"):
                batch["flags"].add("odoo_quantity_differs_from_care_receipt")
            if received <= 0 or billed < 0 or free < 0 or free > received:
                batch["flags"].add("invalid_purchase_quantity")
            batch["received_base_units"] += quantity
            batch["free_base_units"] += free * factor * metadata.pack_size
            batch["net_purchase_value"] += value
            batch["bill_line_ids"].append(line.id)

        items = []
        invalid = {
            "invalid_purchase_quantity",
            "conflicting_batch_identity",
            "conflicting_base_units",
        }
        for (facility, item_uuid), group in sorted(groups.items()):
            if len(group["units"]) > 1:
                group["flags"].add("conflicting_base_units")
            batches = []
            for _, batch in sorted(group["batches"].items()):
                group["flags"].update(batch["flags"])
                quantity = batch["received_base_units"]
                batch["weighted_average_price"] = (
                    str(batch["net_purchase_value"] / quantity)
                    if quantity > 0
                    and not batch["flags"] & invalid
                    and len(group["units"]) == 1
                    else None
                )
                batches.append(batch)
            quantity = sum((b["received_base_units"] for b in batches), Decimal(0))
            value = sum((b["net_purchase_value"] for b in batches), Decimal(0))
            item = {
                "facility_uuid": facility,
                "care_item_uuid": item_uuid,
                "item": group["metadata"].item_name,
                "base_unit": group["metadata"].base_unit,
                "received_base_units": str(quantity),
                "free_base_units": str(
                    sum((b["free_base_units"] for b in batches), Decimal(0))
                ),
                "net_purchase_value": str(value),
                "weighted_average_price": str(value / quantity)
                if quantity > 0 and not group["flags"] & invalid
                else None,
                "flags": sorted(group["flags"]),
                "batches": batches,
            }
            for batch in batches:
                batch["flags"] = sorted(batch["flags"])
                for field in (
                    "received_base_units",
                    "free_base_units",
                    "net_purchase_value",
                ):
                    batch[field] = str(batch[field])
            items.append(item)
        unmapped_value = sum(
            (number(row["net_purchase_value"]) for row in unmapped), Decimal(0)
        )
        return {
            "month": month,
            "bill_count": len({line.move_id.id for line in lines}),
            "bill_line_count": len(lines),
            "net_purchase_value": str(total),
            "mapped_purchase_value": str(total - unmapped_value),
            "unmapped_purchase_value": str(unmapped_value),
            "complete": not unmapped and not any(item["flags"] for item in items),
            "items": items,
            "unmapped_lines": unmapped,
        }
