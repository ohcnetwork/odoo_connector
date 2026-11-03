"""Care stock identity and bill-value inputs; Odoo owns the costing algorithm."""

from odoo import api, fields, models


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
    state = fields.Selection(
        [("building", "Building"), ("current", "Current"), ("archived", "Archived")],
        default="current",
        required=True,
        index=True,
    )
    _key_unique = models.Constraint(
        "UNIQUE(key, company_id)", "Care period keys must be unique."
    )


class CareStockClose(models.Model):
    _name = "care.stock.close"
    _description = "Care monthly inventory report"
    _rec_name = "month"
    _order = "month desc, id desc"

    period_id = fields.Many2one("care.stock.period", required=True, ondelete="restrict")
    company_id = fields.Many2one(related="period_id.company_id", store=True)
    month = fields.Char(required=True)
    source_hash = fields.Char(required=True)
    snapshot = fields.Json(required=True)
    facility_uuid = fields.Char(related="period_id.facility_uuid")
    facility_name = fields.Char(
        string="Facility", compute="_compute_facility_name", store=True
    )
    state = fields.Selection(related="period_id.state")
    total_value = fields.Monetary(
        currency_field="currency_id", compute="_compute_total_value"
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    line_ids = fields.One2many("care.stock.close.line", "close_id")
    _month_unique = models.Constraint(
        "UNIQUE(period_id, month)", "A month can only be closed once."
    )

    @api.depends("snapshot")
    def _compute_total_value(self):
        for report in self:
            report.total_value = float((report.snapshot or {}).get("total_value", 0))

    @api.depends("period_id.metadata", "company_id.name")
    def _compute_facility_name(self):
        for report in self:
            report.facility_name = (report.period_id.metadata or {}).get(
                "facility_name"
            ) or report.company_id.name

    def action_details(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Care Stock by Batch and Location",
            "res_model": "care.stock.close.line",
            "view_mode": "list",
            "domain": [("close_id", "=", self.id)],
        }


class CareStockCloseLine(models.Model):
    _name = "care.stock.close.line"
    _description = "Care stock by batch and location"
    _order = "item, location, batch, id"

    close_id = fields.Many2one(
        "care.stock.close", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="close_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    item_uuid = fields.Char(index=True)
    item = fields.Char()
    batch_uuid = fields.Char()
    batch = fields.Char()
    expiry = fields.Char()
    location_uuid = fields.Char()
    location = fields.Char()
    quantity = fields.Float(digits=(24, 6))
    available_quantity = fields.Float(digits=(24, 6))
    incoming_quantity = fields.Float(digits=(24, 6))
    effective_cost = fields.Float(digits=(24, 12))
    value = fields.Monetary(currency_field="currency_id")


class CareStockProduct(models.Model):
    _inherit = "product.product"

    care_stock_item_uuid = fields.Char(index=True, copy=False)
    care_stock_facility_uuid = fields.Char(index=True, copy=False)
    care_stock_company_id = fields.Many2one(
        "res.company", related="company_id", store=True
    )
    care_stock_period_id = fields.Many2one("care.stock.period", copy=False, index=True)
    _care_item_unique = models.Constraint(
        "UNIQUE(care_stock_item_uuid, care_stock_period_id, care_stock_company_id)",
        "A Care inventory item can only map to one stock product per revision.",
    )

    def init(self):
        # Adopt products posted by the earlier, single-ledger implementation.
        self.env.cr.execute("""
            UPDATE product_product p SET care_stock_period_id = m.period_id
            FROM (
                SELECT product_id, MIN(care_stock_period_id) AS period_id FROM stock_move
                WHERE care_stock_period_id IS NOT NULL GROUP BY product_id
                HAVING COUNT(DISTINCT care_stock_period_id) = 1
            ) m WHERE p.id = m.product_id AND p.care_stock_item_uuid IS NOT NULL
                AND p.care_stock_period_id IS NULL
        """)

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

    def _get_value_from_account_move(self, quantity, at_date=None):
        self.ensure_one()
        if self.care_stock_key and self.care_stock_cost_basis:
            return {
                "value": self.company_id.currency_id.round(self.care_stock_input_value),
                "quantity": quantity,
                "description": f"Care {self.care_stock_cost_basis}: {self.care_stock_key}",
            }
        return super()._get_value_from_account_move(quantity, at_date)
