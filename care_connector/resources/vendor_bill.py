from datetime import datetime

from markupsafe import Markup

from .account_move import AccountUtility
from .invoice_resync import InvoiceResyncUtility, _Stop


class _Unchanged(Exception):
    """The bill needs no change: undo anything comparing it wrote."""


class VendorBillUtility:
    """
    Keeps the vendor bill of a Care delivery order in line with the order.

    Care can move a completed order back to draft to add items, complete it again, or cancel it.
    The bill follows while it is a draft. A posted bill is final, so Care's change is refused instead.
    """

    @classmethod
    def find(cls, env, x_care_id):
        return env["account.move"].search(
            [("x_care_id", "=", x_care_id), ("move_type", "=", "in_invoice")], limit=1
        )

    @classmethod
    def create_or_update(cls, env, request_data):
        """Create the order's bill, or bring the one from an earlier completion in line with the order."""
        move = cls.find(env, request_data.x_care_id)
        if not move:
            return AccountUtility.get_or_create_account_move(env, request_data)

        # The controller commits even when it returns an error, and comparing can write too (discount groups),
        # so only a finished update is kept
        try:
            with env.cr.savepoint():
                cls._update(env, move, request_data)
        except _Unchanged:
            pass
        return move

    @classmethod
    def _update(cls, env, move, request_data):
        try:
            line_changes = InvoiceResyncUtility._line_changes(env, move, request_data.invoice_items)
        except _Stop as error:
            raise ValueError(str(error)) from error
        header, changes = cls._header_changes(move, request_data)
        changes = [description for _command, description in line_changes] + changes

        if move.state == "posted":
            # Completing the order again without changing it needs nothing from the bill
            if changes:
                raise ValueError(f"Vendor bill {move.name} is already posted in Odoo, so it can't be changed")
            raise _Unchanged
        if move.state == "cancel":
            move.button_draft()
            changes.insert(0, "reset to draft from cancelled")
        if not changes:
            raise _Unchanged
        move.write({**header, "invoice_line_ids": [command for command, _description in line_changes]})
        cls._post_note(move, "Vendor bill updated from Care, as its delivery order was completed again.", changes)

    @classmethod
    def _header_changes(cls, move, request_data):
        """
        The vendor bill number and date where Care's differ: (values to write, descriptions).
        The vendor is left alone: Care can't change an order's supplier, so a different one was set in Odoo.
        """
        vals, changes = {}, []
        # Without a bill number or date in Care, keep the bill's own, which may have been entered in Odoo
        if request_data.bill_number and move.ref != request_data.bill_number:
            vals["ref"] = request_data.bill_number
            changes.append(f"bill reference set to {request_data.bill_number}")
        bill_date = request_data.bill_date and datetime.strptime(request_data.bill_date, "%d-%m-%Y").date()
        if bill_date and move.invoice_date != bill_date:
            vals["invoice_date"] = bill_date
            changes.append(f"bill date set to {bill_date}")
        return vals, changes

    @classmethod
    def reopen(cls, env, request_data):
        """Care moves the order back to draft: refuse if the bill is posted, since it couldn't take more items."""
        move = cls.find(env, request_data.x_care_id)
        if not move:
            return move
        if move.state == "posted":
            raise ValueError(
                f"Vendor bill {move.name} is already posted in Odoo, so the delivery order can't be moved back to draft"
            )
        cls._post_note(
            move,
            "Care moved the delivery order back to draft. This bill is updated when the order is completed again.",
        )
        return move

    @classmethod
    def cancel(cls, env, request_data):
        """Care cancels the order: cancel its bill, unless it is posted."""
        move = cls.find(env, request_data.x_care_id)
        if not move or move.state == "cancel":
            return move
        if move.state == "posted":
            raise ValueError(f"Vendor bill {move.name} is already posted in Odoo, so it can't be cancelled")
        with env.cr.savepoint():
            # button_cancel would reset a posted bill to draft first, which is why that is refused above
            move.button_cancel()
            reason = f": {request_data.reason}" if request_data.reason else ""
            cls._post_note(move, f"Vendor bill cancelled from Care{reason}.")
        return move

    @classmethod
    def _post_note(cls, move, title, changes=()):
        items = Markup("").join(Markup("<li>%s</li>") % change for change in changes)
        body = Markup("<p>%s</p>") % title
        if items:
            body += Markup("<ul>%s</ul>") % items
        move.message_post(body=body, subtype_xmlid="mail.mt_note")
