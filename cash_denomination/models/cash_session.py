from odoo import models, fields, api
from odoo.exceptions import UserError


class CashSession(models.Model):
    _name = "cash.session"
    _description = "Cash Session"
    _order = "opened_at desc"

    # === IDENTITY (from Care) ===
    external_user_id = fields.Char(
        string="User ID",
        required=True,
        index=True,
        help="External user identifier from Care system",
    )
    external_user_name = fields.Char(
        string="User Name", required=True, help="Display name from Care system"
    )

    # === LOCATION ===
    counter_id = fields.Many2one(
        "bill.counter", string="Counter", required=True, index=True
    )

    # === LIFECYCLE ===
    status = fields.Selection(
        [
            ("open", "Open"),
            ("closed", "Closed"),
        ],
        string="Status",
        default="open",
        required=True,
        index=True,
    )
    opened_at = fields.Datetime(
        string="Opened At", default=fields.Datetime.now, required=True
    )
    closed_at = fields.Datetime(string="Closed At")

    # === BALANCE ===
    opening_balance = fields.Float(string="Opening Balance", default=0.0)
    expected_amount = fields.Float(
        string="Expected Amount", compute="_compute_expected", store=False
    )

    # === CLOSING SNAPSHOT (frozen on close) ===
    closing_expected = fields.Float(string="Closing Expected", readonly=True)
    closing_declared = fields.Float(string="Closing Declared", readonly=True)
    closing_difference = fields.Float(string="Closing Difference", readonly=True)
    closing_denominations = fields.Json(string="Closing Denominations")

    # === CLOSED BY (Care identity) ===
    closed_by_ext_id = fields.Char(string="Closed By ID")
    closed_by_name = fields.Char(string="Closed By Name")

    # === VARIANCE RESOLUTION ===
    difference_status = fields.Selection(
        [
            ("none", "No Variance"),
            ("open", "Open"),
            ("recoverable", "Recoverable"),
            ("recovered", "Recovered"),
            ("written_off", "Written Off"),
        ],
        string="Variance Status",
        default="none",
    )
    difference_note = fields.Text(string="Resolution Note")

    # === RELATIONS ===
    payment_ids = fields.One2many(
        "account.payment", "cash_session_id", string="Payments"
    )
    outgoing_transfer_ids = fields.One2many(
        "cash.transfer", "from_session_id", string="Outgoing Transfers"
    )
    incoming_transfer_ids = fields.One2many(
        "cash.transfer", "to_session_id", string="Incoming Transfers"
    )

    # === COMPUTED FIELDS ===
    payment_count = fields.Integer(
        string="Payment Count", compute="_compute_payment_count"
    )
    pending_outgoing_count = fields.Integer(
        string="Pending Outgoing", compute="_compute_pending_counts"
    )
    pending_incoming_count = fields.Integer(
        string="Pending Incoming", compute="_compute_pending_counts"
    )
    pending_outgoing_amount = fields.Float(
        string="Pending Outgoing Amount",
        compute="_compute_pending_amounts",
        help="Total amount reserved in pending outgoing transfers",
    )
    available_balance = fields.Float(
        string="Available Balance",
        compute="_compute_available_balance",
        help="Balance available for new transfers (expected - pending outgoing)",
    )

    # === DISPLAY NAME ===
    display_name = fields.Char(compute="_compute_display_name", store=True)

    @api.constrains("external_user_id", "counter_id", "status")
    def _check_unique_open_session(self):
        """Ensure only one open session per user per counter."""
        for session in self:
            if session.status == "open":
                duplicate = self.search(
                    [
                        ("id", "!=", session.id),
                        ("external_user_id", "=", session.external_user_id),
                        ("counter_id", "=", session.counter_id.id),
                        ("status", "=", "open"),
                    ],
                    limit=1,
                )
                if duplicate:
                    raise UserError(
                        f"User {session.external_user_name} already has an open session "
                        f"at {session.counter_id.bill_counter}"
                    )

    @api.depends("external_user_name", "counter_id", "opened_at")
    def _compute_display_name(self):
        for session in self:
            counter_name = (
                session.counter_id.bill_counter if session.counter_id else "Unknown"
            )
            date_str = (
                session.opened_at.strftime("%Y-%m-%d %H:%M")
                if session.opened_at
                else ""
            )
            session.display_name = (
                f"{session.external_user_name} @ {counter_name} ({date_str})"
            )

    @api.depends("payment_ids")
    def _compute_payment_count(self):
        for session in self:
            session.payment_count = len(session.payment_ids)

    @api.depends("outgoing_transfer_ids", "incoming_transfer_ids")
    def _compute_pending_counts(self):
        for session in self:
            session.pending_outgoing_count = len(
                session.outgoing_transfer_ids.filtered(lambda t: t.status == "pending")
            )
            session.pending_incoming_count = len(
                session.incoming_transfer_ids.filtered(lambda t: t.status == "pending")
            )

    @api.depends(
        "outgoing_transfer_ids",
        "outgoing_transfer_ids.amount",
        "outgoing_transfer_ids.status",
    )
    def _compute_pending_amounts(self):
        for session in self:
            pending_transfers = session.outgoing_transfer_ids.filtered(
                lambda t: t.status == "pending"
            )
            session.pending_outgoing_amount = sum(pending_transfers.mapped("amount"))

    @api.depends("expected_amount", "pending_outgoing_amount")
    def _compute_available_balance(self):
        """Available balance = expected - pending outgoing (reserved funds)."""
        for session in self:
            session.available_balance = (
                session.expected_amount - session.pending_outgoing_amount
            )

    @api.depends(
        "opening_balance",
        "payment_ids",
        "payment_ids.amount",
        "payment_ids.payment_type",
        "payment_ids.journal_id",
        "payment_ids.state",
        "outgoing_transfer_ids",
        "outgoing_transfer_ids.amount",
        "outgoing_transfer_ids.status",
        "incoming_transfer_ids",
        "incoming_transfer_ids.amount",
        "incoming_transfer_ids.status",
    )
    def _compute_expected(self):
        for session in self:
            expected = session.opening_balance

            # + Cash payments received (inbound), excluding cancelled payments
            for payment in session.payment_ids:
                if payment.journal_id.type == "cash" and payment.state != "canceled":
                    if payment.payment_type == "inbound":
                        expected += payment.amount
                    elif payment.payment_type == "outbound":
                        expected -= payment.amount

            # + Accepted incoming transfers
            for transfer in session.incoming_transfer_ids:
                if transfer.status == "accepted":
                    expected += transfer.amount

            # - Accepted outgoing transfers
            for transfer in session.outgoing_transfer_ids:
                if transfer.status == "accepted":
                    expected -= transfer.amount

            session.expected_amount = expected

    @api.model
    def find_open_session(self, external_user_id, counter_x_care_id):
        """Find an open session for a user at a counter."""
        counter = self.env["bill.counter"].search(
            [("x_care_id", "=", counter_x_care_id)], limit=1
        )

        if not counter:
            return self.browse()

        return self.search(
            [
                ("external_user_id", "=", external_user_id),
                ("counter_id", "=", counter.id),
                ("status", "=", "open"),
            ],
            limit=1,
        )

    def action_close(self, closed_by_ext_id, closed_by_name):
        """Close the session.

        Close flow:
        1. Check for pending transfers
        2. For non-main-cash counters: if expected_amount != 0, flag as variance
           (cash should have been transferred to main cash)
        3. Main cash counters can close with any balance

        Note: Non-zero balance at non-main-cash counters represents untransferred
        cash (a liability) and is flagged for the accounts team to resolve.
        """
        self.ensure_one()

        if self.status != "open":
            raise UserError("Only open sessions can be closed")

        # Check for pending outgoing transfers
        pending_outgoing = self.outgoing_transfer_ids.filtered(
            lambda t: t.status == "pending"
        )
        if pending_outgoing:
            raise UserError(
                f"Cannot close session with {len(pending_outgoing)} pending outgoing transfer(s). "
                "Please wait for them to be accepted or rejected."
            )

        # Check for pending incoming transfers
        pending_incoming = self.incoming_transfer_ids.filtered(
            lambda t: t.status == "pending"
        )
        if pending_incoming:
            raise UserError(
                f"Cannot close session with {len(pending_incoming)} pending incoming transfer(s). "
                "Please accept or reject them first."
            )

        # Snapshot expected amount before closing
        expected = self.expected_amount
        is_main_cash = self.counter_id.is_main_cash

        # Determine variance status
        # For non-main-cash: flag if balance is not zero (untransferred cash)
        # For main cash: no variance check needed (it's where cash accumulates)
        if is_main_cash or abs(expected) < 0.01:
            diff_status = "none"
        else:
            # Non-zero balance at non-main-cash counter - flag for review
            diff_status = "open"

        self.write(
            {
                "status": "closed",
                "closed_at": fields.Datetime.now(),
                "closing_expected": expected,
                "closing_declared": 0.0,  # No longer tracking declared amount
                "closing_difference": -expected
                if not is_main_cash
                else 0.0,  # Difference from zero
                "closed_by_ext_id": closed_by_ext_id,
                "closed_by_name": closed_by_name,
                "difference_status": diff_status,
            }
        )

        return True

    def action_resolve_variance(self, status, note=None):
        """Resolve variance for a closed session."""
        self.ensure_one()

        if self.status != "closed":
            raise UserError("Only closed sessions can have variance resolved")

        if self.difference_status == "none":
            raise UserError("Session has no variance to resolve")

        if status not in ("recoverable", "recovered", "written_off"):
            raise UserError("Invalid variance status")

        self.write(
            {
                "difference_status": status,
                "difference_note": note,
            }
        )

        return True

    def action_view_outgoing_transfers(self):
        """View outgoing transfers for this session."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Outgoing Transfers",
            "res_model": "cash.transfer",
            "view_mode": "list,form",
            "domain": [("from_session_id", "=", self.id)],
            "context": {"default_from_session_id": self.id},
        }

    def action_view_incoming_transfers(self):
        """View incoming transfers for this session."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Incoming Transfers",
            "res_model": "cash.transfer",
            "view_mode": "list,form",
            "domain": [("to_session_id", "=", self.id)],
            "context": {"default_to_session_id": self.id},
        }
