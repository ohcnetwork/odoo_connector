from datetime import datetime

from markupsafe import Markup

from odoo import Command
from odoo.tools import float_compare

from .account_move import AccountUtility

# Invoice cash rounding can put the Odoo total up to a rupee away from Care's
TOTAL_TOLERANCE = 1.0
# The line fields the sync sets, compared with Care's, with the names used in the results and notes
LINE_FIELDS = {
    "product_id": "product",
    "quantity": "quantity",
    "received_qty": "received quantity",
    "free_qty": "free quantity",
    "price_unit": "price",
    "discount": "discount",
    "discount_group_id": "discount group",
    "commission_user_id": "agent",
}
# What the result shows of the invoice before and after correcting, in Odoo's standard read() format
INVOICE_FIELDS = [
    "name",
    "state",
    "move_type",
    "invoice_date",
    "journal_id",
    "partner_id",
    "amount_untaxed",
    "amount_tax",
    "amount_total",
    "payment_state",
]
INVOICE_LINE_FIELDS = ["x_care_id", *LINE_FIELDS, "tax_ids", "price_subtotal"]


class _Stop(Exception):
    """Undo this invoice and report the reason as its status."""


class InvoiceResyncUtility:
    """Brings posted Care invoices back in line with Care."""

    @classmethod
    def resync(cls, env, invoice):
        """
        Correct the invoice if its lines differ from Care's.

        An invoice that matches is left untouched. One that differs is reset to draft, corrected,
        re-posted (keeping its number) and re-matched to the payments it had, and kept only if its total
        then equals Care's. Anything that stops the correction is rolled back and reported as the status.
        Nothing is committed here: the caller's transaction saves the result.

        Returns the result as a dict.
        """
        # The status comes first; the changes and the invoice before and after are added once they're known
        result = {"status": None}
        data = invoice.data
        try:
            with env.cr.savepoint():
                move = cls._find_move(env, invoice.number, data)
                result["old"] = cls._snapshot(move)
                if move.state != "posted":
                    raise _Stop(f"invoice is {move.state}")
                cls._check_header(move, data)

                changes = cls._line_changes(env, move, data.invoice_items)
                if not changes:
                    # Matching lines can still total differently, e.g. through taxes or lines added in Odoo
                    if not cls._total_matches(move, invoice.care_total):
                        raise _Stop(f"needs manual fix: the lines match Care, but the total {move.amount_total_signed} doesn't")
                    raise _Stop("in sync")
                result["changes"] = [description for _command, description in changes]
                if "insurance.claim" in env and env["insurance.claim"].sudo().search_count(
                    [("claimed_move_line_ids", "in", move.invoice_line_ids.ids)]
                ):
                    raise _Stop("skipped: lines are on an insurance claim, fix manually")

                taxed = move.is_taxed if "is_taxed" in move._fields else None  # checked after correcting
                rematched = cls._correct(move, changes)
                result["new"] = cls._snapshot(move)
                cls._check_corrected(move, invoice, taxed)
                cls._post_note(move, changes, result, rematched)
            result["status"] = "updated"
        except Exception as error:  # noqa: BLE001 - report it as the status
            env.invalidate_all(flush=False)
            result["status"] = str(error) if isinstance(error, _Stop) else f"error: {error}"
        return result

    @classmethod
    def _find_move(cls, env, number, data):
        # Care refunds are synced as credit notes
        move_type = "out_refund" if data.is_refund else "out_invoice"
        move = env["account.move"].search(
            [("name", "=", number), ("x_care_id", "=", data.x_care_id), ("move_type", "=", move_type)]
        )
        if len(move) != 1:
            raise _Stop(f"not found ({len(move)} matching Odoo invoices)")
        return move

    @classmethod
    def _snapshot(cls, move):
        """The invoice and its Care lines in Odoo's standard read() format."""
        snapshot = move.read(INVOICE_FIELDS)[0]
        lines = move.invoice_line_ids.filtered("x_care_id")
        snapshot["lines"] = lines.read([field for field in INVOICE_LINE_FIELDS if field in lines._fields])
        return snapshot

    @classmethod
    def _total_matches(cls, move, care_total):
        # Written so that a NaN total (e.g. from a NaN discount rate) doesn't match
        return abs(move.amount_total_signed - care_total) <= TOTAL_TOLERANCE

    @classmethod
    def _label(cls, line):
        return line.product_id.display_name or line.name

    @classmethod
    def _check_header(cls, move, data):
        """Differences that are reported rather than changed: they need a person to decide."""
        if move.partner_id.x_care_id != data.partner_data.x_care_id:
            raise _Stop(
                f"needs manual fix: the partner differs (Odoo {move.partner_id.display_name}, "
                f"Care patient {data.partner_data.x_care_id})"
            )
        care_date = datetime.strptime(data.invoice_date, "%d-%m-%Y").date()
        if move.invoice_date != care_date:
            raise _Stop(f"needs manual fix: the invoice date differs (Odoo {move.invoice_date}, Care {care_date})")

    @classmethod
    def _check_corrected(cls, move, invoice, taxed):
        """Corrections that can't be kept: the invoice is rolled back and the reason reported."""
        # sales_journal_tax_selection picks the taxed or untaxed journal only when an invoice is created,
        # so a correction that adds its first tax or removes its last would leave it in the wrong journal
        if taxed is not None and move.is_taxed != taxed:
            journal = "taxed" if move.is_taxed else "untaxed"
            raise _Stop(f"needs manual fix: the changes would move it to the {journal} journal")
        if move.name != invoice.number:
            raise _Stop(f"rolled back: number would change to {move.name}")
        if not cls._total_matches(move, invoice.care_total):
            raise _Stop(f"rolled back: Odoo total {move.amount_total_signed} would not match Care")

    @classmethod
    def _line_changes(cls, env, move, items):
        """(command, description) for each line that has to change to match Care's items."""
        care_ids = {item.x_care_id for item in items}
        lines = move.invoice_line_ids.filtered("x_care_id")
        fields = [field for field in LINE_FIELDS if field in lines._fields]
        changes = []
        # Products and agents archived since the invoice was synced must still be found
        lookup_env = env(context=dict(env.context, active_test=False))
        for item in items:
            vals = AccountUtility._prepare_invoice_line_vals(lookup_env, item, move.move_type)
            line = lines.filtered(lambda l, care_id=item.x_care_id: l.x_care_id == care_id)
            if len(line) > 1:
                raise _Stop(f"{len(line)} Odoo lines for charge item {item.x_care_id}")
            if not line:
                product = env["product.product"].browse(vals["product_id"])
                description = f"added {product.display_name} ({vals['quantity']:g} × {vals['price_unit']:g})"
                changes.append((Command.create(vals), description))
                continue
            differing = {
                field: vals.get(field, False) for field in fields if cls._differs(line, field, vals.get(field, False))
            }
            # Without an agent the commission falls back to the invoice's salesperson, so a person decides
            if "commission_user_id" in differing and not differing["commission_user_id"]:
                agent = line.commission_user_id.display_name
                raise _Stop(f"needs manual fix: the changes would remove agent {agent} from {cls._label(line)}")
            if differing:
                changes.append((Command.update(line.id, differing), cls._describe(line, differing)))
        for line in lines.filtered(lambda l: l.x_care_id not in care_ids):
            changes.append((Command.delete(line.id), f"removed {cls._label(line)}"))
        return changes

    @classmethod
    def _differs(cls, line, field, value):
        definition = line._fields[field]
        if definition.type == "many2one":
            return line[field].id != (value or False)
        digits = definition.get_digits(line.env)
        return float_compare(line[field], value or 0.0, precision_digits=digits[1] if digits else 2) != 0

    @classmethod
    def _describe(cls, line, differing):
        parts = []
        for field, value in differing.items():
            definition = line._fields[field]
            if definition.type == "many2one":
                old = line[field].display_name or "none"
                new = line.env[definition.comodel_name].browse(value).display_name if value else "none"
            else:
                unit = "%" if field == "discount" else ""
                old, new = f"{line[field]:g}{unit}", f"{value:g}{unit}"
            parts.append(f"{LINE_FIELDS[field]} {old} → {new}")
        return f"{cls._label(line)}: {', '.join(parts)}"

    @classmethod
    def _correct(cls, move, changes):
        """Reset, correct and re-post the invoice; returns whether payments were re-matched."""
        receivable = move.line_ids.filtered(lambda l: l.account_id.account_type == "asset_receivable")
        counterparts = (
            receivable.matched_debit_ids.debit_move_id | receivable.matched_credit_ids.credit_move_id
        ) - receivable

        move.button_draft()
        move.write({"invoice_line_ids": [command for command, _description in changes]})
        move.action_post()
        # Re-posting removes the payment matching; match the same payments again
        for counterpart in counterparts.filtered(lambda l: not l.reconciled):
            if move.currency_id.is_zero(move.amount_residual):
                break
            move.js_assign_outstanding_line(counterpart.id)
        return bool(counterparts)

    @classmethod
    def _post_note(cls, move, changes, result, rematched):
        items = Markup("").join(Markup("<li>%s</li>") % description for _command, description in changes)
        move.message_post(
            body=Markup("<p>Invoice resynced from Care.</p><ul>%s</ul><p>Total %s → %s.%s</p>")
            % (
                items,
                f"{result['old']['amount_total']:.2f}",
                f"{result['new']['amount_total']:.2f}",
                " Payment re-matched." if rematched else "",
            ),
            subtype_xmlid="mail.mt_note",
        )
