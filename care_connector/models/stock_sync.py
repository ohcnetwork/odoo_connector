"""Care stock identity and bill-value inputs; Odoo owns the costing algorithm."""

from odoo.exceptions import ValidationError

from odoo import fields, models


class CareStockPeriod(models.Model):
    _name = "care.stock.period"
    _description = "Care inventory period"

    key = fields.Char(required=True, index=True)
    facility_uuid = fields.Char(required=True)
    month = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True)
    metadata = fields.Json(default=dict)
    location_map = fields.Json(default=dict)
    mode = fields.Selection(
        [("detailed", "Detailed trial"), ("monthly", "Monthly summary")],
        default="detailed",
        required=True,
    )
    closed_through = fields.Datetime(copy=False)
    _key_unique = models.Constraint(
        "UNIQUE(key, company_id)", "Care period keys must be unique."
    )

    def write(self, vals):
        if {"key", "facility_uuid", "month", "company_id", "mode"}.intersection(vals):
            raise ValidationError(
                "The identity of a Care valuation ledger cannot change."
            )
        if "closed_through" in vals and any(
            p.closed_through
            and (
                not vals["closed_through"]
                or fields.Datetime.to_datetime(vals["closed_through"])
                <= p.closed_through
            )
            for p in self
        ):
            raise ValidationError("A Care valuation ledger cannot be reopened.")
        return super().write(vals)


class CareStockClose(models.Model):
    _name = "care.stock.close"
    _description = "Immutable Care inventory month-end"

    period_id = fields.Many2one("care.stock.period", required=True, ondelete="restrict")
    company_id = fields.Many2one(related="period_id.company_id", store=True)
    month = fields.Char(required=True)
    source_hash = fields.Char(required=True)
    snapshot = fields.Json(required=True)
    _month_unique = models.Constraint(
        "UNIQUE(period_id, month)", "A month can only be closed once."
    )

    def write(self, vals):
        raise ValidationError("Closed inventory snapshots cannot be changed.")

    def unlink(self):
        raise ValidationError("Closed inventory snapshots cannot be deleted.")


class CareStockProduct(models.Model):
    _inherit = "product.product"

    care_stock_item_uuid = fields.Char(index=True, copy=False)
    care_stock_facility_uuid = fields.Char(index=True, copy=False)
    care_stock_company_id = fields.Many2one(
        "res.company", related="company_id", store=True
    )
    _care_item_unique = models.Constraint(
        "UNIQUE(care_stock_item_uuid, care_stock_facility_uuid, care_stock_company_id)",
        "A Care inventory item can only map to one stock product per company.",
    )

    def _update_standard_price(self, extra_value=None, extra_quantity=None):
        result = super()._update_standard_price(extra_value, extra_quantity)
        # Odoo 19 skips a zero AVCO result, leaving the previous cost after a
        # fully free receipt. Keep its native calculation and persist zero too.
        for product in self.filtered(
            lambda p: p.care_stock_item_uuid and p.cost_method == "average"
        ):
            if product.standard_price and product._run_avco()[0] == 0:
                product.sudo().with_context(
                    disable_auto_revaluation=True
                ).standard_price = 0
        return result


class CareStockLot(models.Model):
    _inherit = "stock.lot"

    care_stock_batch_uuid = fields.Char(index=True, copy=False)
    _care_batch_unique = models.Constraint(
        "UNIQUE(care_stock_batch_uuid, company_id)",
        "Care stock batches must be unique.",
    )


class CareStockLocation(models.Model):
    _inherit = "stock.location"

    care_stock_location_uuid = fields.Char(index=True, copy=False)
    care_stock_facility_uuid = fields.Char(index=True, copy=False)
    _care_location_unique = models.Constraint(
        "UNIQUE(care_stock_location_uuid, company_id)",
        "Care stock locations must be unique.",
    )


class CareStockMove(models.Model):
    _inherit = "stock.move"

    care_stock_key = fields.Char(index=True, copy=False)
    care_stock_hash = fields.Char(copy=False)
    care_stock_period_id = fields.Many2one("care.stock.period", copy=False, index=True)
    care_stock_kind = fields.Char(copy=False)
    care_stock_cost_basis = fields.Char(copy=False)
    care_stock_input_value = fields.Float(digits=(24, 10), copy=False)
    care_stock_bill_line_ids = fields.Many2many("account.move.line", copy=False)
    care_stock_evidence = fields.Json(copy=False)
    _care_key_unique = models.Constraint(
        "UNIQUE(care_stock_key, company_id)",
        "A Care stock event can only be posted once.",
    )

    def write(self, vals):
        protected = {
            "date",
            "product_id",
            "product_uom_qty",
            "quantity",
            "location_id",
            "location_dest_id",
            "state",
            "care_stock_input_value",
            "care_stock_evidence",
            "care_stock_hash",
            "care_stock_key",
            "care_stock_period_id",
            "care_stock_bill_line_ids",
        }
        if protected.intersection(vals) and any(
            move.care_stock_period_id.mode == "monthly"
            and move.care_stock_period_id.closed_through
            and move.date <= move.care_stock_period_id.closed_through
            for move in self
        ):
            raise ValidationError(
                "Stock movements in a closed Care month cannot be changed."
            )
        return super().write(vals)

    def unlink(self):
        if any(
            move.care_stock_period_id.mode == "monthly" and move.state == "done"
            for move in self
        ):
            raise ValidationError("Completed Care monthly movements cannot be deleted.")
        return super().unlink()

    def _get_value_from_account_move(self, quantity, at_date=None):
        self.ensure_one()
        if self.care_stock_key and self.care_stock_cost_basis:
            return {
                "value": self.company_id.currency_id.round(self.care_stock_input_value),
                "quantity": quantity,
                "description": f"Care {self.care_stock_cost_basis}: {self.care_stock_key}",
            }
        return super()._get_value_from_account_move(quantity, at_date)


class CareStockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def write(self, vals):
        if {
            "date",
            "quantity",
            "product_id",
            "lot_id",
            "location_id",
            "location_dest_id",
            "move_id",
        }.intersection(vals) and any(
            line.move_id.care_stock_period_id.mode == "monthly"
            and line.move_id.care_stock_period_id.closed_through
            and line.date <= line.move_id.care_stock_period_id.closed_through
            for line in self
        ):
            raise ValidationError(
                "Stock lines in a closed Care month cannot be changed."
            )
        return super().write(vals)

    def unlink(self):
        if any(
            line.move_id.care_stock_period_id.mode == "monthly"
            and line.move_id.state == "done"
            for line in self
        ):
            raise ValidationError(
                "Completed Care monthly stock lines cannot be deleted."
            )
        return super().unlink()
