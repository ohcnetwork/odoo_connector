from datetime import datetime

from markupsafe import Markup
from pydantic import ValidationError

from odoo import Command
from odoo.tools import float_compare, str2bool

from ..pydantic_models.account_move import AccountMoveApiRequest
from .account_move import AccountUtility

ENABLED_PARAM = "care_connector.invoice_resync_enabled"
# Invoice cash rounding can put the Odoo total up to a rupee away from Care's
TOTAL_TOLERANCE = 1.0
OK_STATUSES = ("updated", "would update", "in sync")
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


class _Stop(Exception):
    """Undo this invoice and report the reason as its status."""


class _UndoBatch(Exception):
    """Undo every invoice in an all-or-nothing batch."""


class InvoiceResyncUtility:
    """
    Brings posted Care invoices back in line with Care. Care sends each invoice the way the live sync
    does, and lines that differ are corrected in place, keeping the invoice number and its payments.
    """

    @classmethod
    def check_enabled(cls, user_env):
        """The API is off unless the system parameter is set to True."""
        # Parameters are stored as text, so a value of "False" has to be parsed, not tested for truth
        if not str2bool(user_env["ir.config_parameter"].sudo().get_param(ENABLED_PARAM), default=False):
            raise PermissionError(f"Invoice resync is disabled. Set the system parameter {ENABLED_PARAM} to True to enable it.")

    @classmethod
    def resync(cls, user_env, request_data):
        """
        Correct each invoice whose lines differ from Care's.

        An invoice that matches is left untouched. One that differs is reset to draft, corrected,
        re-posted (keeping its number) and re-matched to the payments it had, and kept only if its total
        then equals Care's. Dry runs undo every invoice; all_or_nothing undoes the whole batch if any
        invoice fails. Nothing is committed here: the caller's transaction saves what's kept.

        Returns one result dict per invoice.
        """
        results = []
        try:
            with user_env.cr.savepoint():
                for invoice in request_data.invoices:
                    results.append(cls._resync_invoice(user_env, invoice, request_data.dry_run))
                if request_data.all_or_nothing and any(cls._failed(result) for result in results):
                    raise _UndoBatch
        except _UndoBatch:
            user_env.invalidate_all(flush=False)
            for result in results:
                if result["status"] in ("updated", "would update"):
                    verb = "would not be saved" if request_data.dry_run else "not saved"
                    result["status"] = f"{verb}: another invoice in this batch failed"
        return results

    @classmethod
    def _failed(cls, result):
        return result["status"] not in OK_STATUSES and not result["status"].startswith("skipped")

    @classmethod
    def _resync_invoice(cls, env, invoice, dry_run):
        result = {"invoice": invoice.invoice, "care_total": invoice.care_total}
        try:
            data = AccountMoveApiRequest.model_validate(invoice.data)
        except ValidationError as error:
            problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors())
            result["status"] = f"error: Care's invoice data isn't valid: {problems}"
            return result
        try:
            with env.cr.savepoint():
                # Care refunds are synced as credit notes
                move_type = "out_refund" if data.is_refund else "out_invoice"
                move = env["account.move"].search(
                    [("name", "=", invoice.invoice), ("x_care_id", "=", data.x_care_id), ("move_type", "=", move_type)]
                )
                if len(move) != 1:
                    raise _Stop(f"not found ({len(move)} matching Odoo invoices)")
                # Amounts are signed, like Care's: a refund's are negative
                result.update(
                    invoice_date=str(move.invoice_date),
                    journal=move.journal_id.code,
                    old_untaxed=move.amount_untaxed_signed,
                    old_tax=move.amount_tax_signed,
                    old_total=move.amount_total_signed,
                    old_payment_state=move.payment_state,
                )
                if move.state != "posted":
                    raise _Stop(f"invoice is {move.state}")
                cls._check_header(move, data)

                changes = cls._line_changes(env, move, data.invoice_items)
                if not changes:
                    # Matching lines can still total differently, e.g. through taxes or lines added in Odoo
                    if not abs(move.amount_total_signed - invoice.care_total) <= TOTAL_TOLERANCE:
                        raise _Stop(f"needs manual fix: the lines match Care, but the total {move.amount_total_signed} doesn't")
                    raise _Stop("in sync")
                result["changes"] = "; ".join(description for _action, _line, _vals, description in changes)
                if "insurance.claim" in env and env["insurance.claim"].sudo().search_count(
                    [("claimed_move_line_ids", "in", move.invoice_line_ids.ids)]
                ):
                    raise _Stop("skipped: lines are on an insurance claim, fix manually")

                # sales_journal_tax_selection picks the taxed or untaxed journal only when an invoice is
                # created, so a correction that adds its first tax or removes its last would leave it in the
                # wrong journal
                taxed = move.is_taxed if "is_taxed" in move._fields else None
                rematched = cls._correct(move, changes)
                result.update(
                    lines_changed=len(changes),
                    new_untaxed=move.amount_untaxed_signed,
                    new_tax=move.amount_tax_signed,
                    new_total=move.amount_total_signed,
                    new_payment_state=move.payment_state,
                )
                if taxed is not None and move.is_taxed != taxed:
                    journal = "taxed" if move.is_taxed else "untaxed"
                    raise _Stop(f"needs manual fix: the changes would move it to the {journal} journal")
                if move.name != invoice.invoice:
                    raise _Stop(f"rolled back: number would change to {move.name}")
                # Written so that a NaN total (e.g. from a NaN discount rate) fails too
                if not abs(move.amount_total_signed - invoice.care_total) <= TOTAL_TOLERANCE:
                    raise _Stop(f"rolled back: Odoo total {move.amount_total_signed} would not match Care")
                if dry_run:
                    raise _Stop("would update")
                cls._post_note(move, changes, result, rematched)
            result["status"] = "updated"
        except _Stop as stop:
            env.invalidate_all(flush=False)
            result["status"] = str(stop)
        except Exception as error:  # noqa: BLE001 - report it and carry on with the next invoice
            env.invalidate_all(flush=False)
            result["status"] = f"error: {error}"
        return result

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
    def _line_changes(cls, env, move, items):
        """(action, line, vals, description) for each line that has to change to match Care's items."""
        care_ids = [item.x_care_id for item in items]
        duplicates = {care_id for care_id in care_ids if care_ids.count(care_id) > 1}
        if duplicates:
            raise _Stop(f"charge item {min(duplicates)} is listed more than once")
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
                changes.append(("add", line, vals, description))
                continue
            differing = {
                field: vals.get(field, False) for field in fields if cls._differs(line, field, vals.get(field, False))
            }
            # Without an agent the commission falls back to the invoice's salesperson, so a person decides
            if "commission_user_id" in differing and not differing["commission_user_id"]:
                agent, product = line.commission_user_id.display_name, line.product_id.display_name or line.name
                raise _Stop(f"needs manual fix: the changes would remove agent {agent} from {product}")
            if differing:
                changes.append(("update", line, differing, cls._describe(line, differing)))
        for line in lines.filtered(lambda l: l.x_care_id not in care_ids):
            changes.append(("remove", line, None, f"removed {line.product_id.display_name or line.name}"))
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
        return f"{line.product_id.display_name or line.name}: {', '.join(parts)}"

    @classmethod
    def _correct(cls, move, changes):
        """Reset, correct and re-post the invoice; returns whether payments were re-matched."""
        receivable = move.line_ids.filtered(lambda l: l.account_id.account_type == "asset_receivable")
        counterparts = (
            receivable.matched_debit_ids.debit_move_id | receivable.matched_credit_ids.credit_move_id
        ) - receivable

        move.button_draft()
        commands = []
        for action, line, vals, _description in changes:
            if action == "add":
                commands.append(Command.create(vals))
            elif action == "update":
                commands.append(Command.update(line.id, vals))
            else:
                commands.append(Command.delete(line.id))
        move.write({"invoice_line_ids": commands})
        move.action_post()
        # Re-posting removes the payment matching; match the same payments again
        for counterpart in counterparts.filtered(lambda l: not l.reconciled):
            if move.currency_id.is_zero(move.amount_residual):
                break
            move.js_assign_outstanding_line(counterpart.id)
        return bool(counterparts)

    @classmethod
    def _post_note(cls, move, changes, result, rematched):
        items = Markup("").join(Markup("<li>%s</li>") % description for _action, _line, _vals, description in changes)
        move.message_post(
            body=Markup("<p>Invoice resynced from Care.</p><ul>%s</ul><p>Total %s → %s.%s</p>")
            % (
                items,
                f"{abs(result['old_total']):.2f}",
                f"{abs(result['new_total']):.2f}",
                " Payment re-matched." if rematched else "",
            ),
            subtype_xmlid="mail.mt_note",
        )
