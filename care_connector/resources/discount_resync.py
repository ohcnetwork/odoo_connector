from markupsafe import Markup

from odoo import Command
from odoo.tools import float_compare

from .account_move import AccountUtility

ENABLED_PARAM = "care_connector.discount_resync_enabled"
# Invoice cash rounding can put the Odoo total up to a rupee away from Care's
TOTAL_TOLERANCE = 1.0
OK_STATUSES = ("fixed", "would fix", "already correct")


class _Stop(Exception):
    """Undo this invoice and report the reason as its status."""


class _UndoBatch(Exception):
    """Undo every invoice in an all-or-nothing batch."""


class DiscountResyncUtility:
    """
    One-off correction of Care invoices synced before the care_odoo applied-discounts fix, when
    Odoo summed every discount an item was eligible for instead of only the ones Care applied.
    """

    @classmethod
    def check_enabled(cls, user_env):
        """The API is off unless the system parameter is set."""
        if not user_env["ir.config_parameter"].sudo().get_param(ENABLED_PARAM):
            raise PermissionError(f"Discount resync is disabled. Set the system parameter {ENABLED_PARAM} to enable it.")

    @classmethod
    def resync(cls, user_env, request_data):
        """
        Give each invoice's lines the discounts Care applied.

        Each invoice is reset to draft, corrected, re-posted (keeping its number) and re-matched to
        the payments it had, and kept only if its total then equals Care's. Dry runs undo every
        invoice; all_or_nothing undoes the whole batch if any invoice fails. Nothing is committed
        here: the caller's transaction saves what's kept.

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
                if result["status"] in ("fixed", "would fix"):
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
            with env.cr.savepoint():
                move = env["account.move"].search(
                    [("name", "=", invoice.invoice), ("x_care_id", "=", invoice.x_care_id), ("move_type", "=", "out_invoice")]
                )
                if len(move) != 1:
                    raise _Stop(f"not found ({len(move)} matching Odoo invoices)")
                result.update(
                    invoice_date=str(move.invoice_date),
                    journal=move.journal_id.code,
                    old_untaxed=move.amount_untaxed,
                    old_tax=move.amount_tax,
                    old_total=move.amount_total,
                    old_payment_state=move.payment_state,
                )
                if move.state != "posted":
                    raise _Stop(f"invoice is {move.state}")

                changes = cls._line_changes(env, move, invoice.lines)
                if not changes:
                    raise _Stop("already correct")
                if "insurance.claim" in env and env["insurance.claim"].sudo().search_count(
                    [("claimed_move_line_ids", "in", move.invoice_line_ids.ids)]
                ):
                    raise _Stop("skipped: lines are on an insurance claim, fix manually")

                rematched = cls._correct(move, changes)
                result.update(
                    lines_fixed=len(changes),
                    new_untaxed=move.amount_untaxed,
                    new_tax=move.amount_tax,
                    new_total=move.amount_total,
                    new_payment_state=move.payment_state,
                )
                if move.name != invoice.invoice:
                    raise _Stop(f"rolled back: number would change to {move.name}")
                if abs(move.amount_total - invoice.care_total) > TOTAL_TOLERANCE:
                    raise _Stop(f"rolled back: Odoo total {move.amount_total} would not match Care")
                if dry_run:
                    raise _Stop("would fix")
                cls._post_note(move, changes, result, rematched)
            result["status"] = "fixed"
        except _Stop as stop:
            env.invalidate_all(flush=False)
            result["status"] = str(stop)
        except Exception as error:  # noqa: BLE001 - report it and carry on with the next invoice
            env.invalidate_all(flush=False)
            result["status"] = f"error: {error}"
        return result

    @classmethod
    def _line_changes(cls, env, move, lines):
        """(line, vals, old discount, old group names) for each line whose discount differs from Care's."""
        has_breakdown = "discount_line_ids" in env["account.move.line"]._fields
        changes = []
        for line_data in lines:
            line = move.invoice_line_ids.filtered(lambda l, care_id=line_data.x_care_id: l.x_care_id == care_id)
            if len(line) != 1:
                raise _Stop(f"{len(line)} Odoo lines for charge item {line_data.x_care_id}")
            info = AccountUtility._calculate_discount(env, line_data.discounts, line.price_unit)
            if float_compare(line.discount, info["discount_percent"], precision_digits=2) == 0:
                continue
            vals = {
                "discount": info["discount_percent"],
                "discount_group_id": info.get("discount_group_id") or False,
            }
            if has_breakdown:
                vals["discount_line_ids"] = [Command.clear()] + [
                    Command.create(discount_line) for discount_line in info.get("discount_lines", [])
                ]
            changes.append((line, vals, line.discount, cls._group_names(line)))
        return changes

    @classmethod
    def _correct(cls, move, changes):
        """Reset, correct and re-post the invoice; returns whether payments were re-matched."""
        receivable = move.line_ids.filtered(lambda l: l.account_id.account_type == "asset_receivable")
        counterparts = (
            receivable.matched_debit_ids.debit_move_id | receivable.matched_credit_ids.credit_move_id
        ) - receivable

        move.button_draft()
        for line, vals, _old_discount, _old_groups in changes:
            line.write(vals)
        move.action_post()
        # Re-posting removes the payment matching; match the same payments again
        for counterpart in counterparts.filtered(lambda l: not l.reconciled):
            if move.currency_id.is_zero(move.amount_residual):
                break
            move.js_assign_outstanding_line(counterpart.id)
        return bool(counterparts)

    @classmethod
    def _group_names(cls, line):
        if "discount_line_ids" in line._fields and line.discount_line_ids:
            return ", ".join(line.discount_line_ids.discount_group_id.mapped("name"))
        return line.discount_group_id.name or ""

    @classmethod
    def _post_note(cls, move, changes, result, rematched):
        items = Markup("").join(
            Markup("<li>%s: %s%% → %s%%%s</li>")
            % (
                line.product_id.display_name or line.name,
                old_discount,
                line.discount,
                Markup(" (%s → %s)") % (old_groups or "-", cls._group_names(line) or "-")
                if old_groups != cls._group_names(line)
                else "",
            )
            for line, _vals, old_discount, old_groups in changes
        )
        move.message_post(
            body=Markup("<p>Discounts corrected to match Care.</p><ul>%s</ul><p>Total %s → %s.%s</p>")
            % (
                items,
                f"{result['old_total']:.2f}",
                f"{result['new_total']:.2f}",
                " Payment re-matched." if rematched else "",
            ),
            subtype_xmlid="mail.mt_note",
        )
