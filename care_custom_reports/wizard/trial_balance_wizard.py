import base64
import io
import xlsxwriter

from odoo import fields, models

from datetime import date


class TrialBalanceWizard(models.TransientModel):
    _name = "trial.balance.wizard"
    _description = "Trial Balance Report Wizard"

    def _default_date_from(self):
        today = date.today()
        # Indian FY: April 1 – March 31
        year = today.year if today.month >= 4 else today.year - 1
        return date(year, 4, 1)

    def _default_date_to(self):
        today = date.today()
        year = today.year if today.month >= 4 else today.year - 1
        return date(year + 1, 3, 31)

    date_from = fields.Date(string="Start Date", required=True, default=_default_date_from)
    date_to = fields.Date(string="End Date", required=True, default=_default_date_to)
    target_move = fields.Selection(
        [("posted", "All Posted Entries"), ("all", "All Entries")],
        string="Target Moves",
        default="posted",
        required=True,
    )
    hide_zero_balance = fields.Boolean(
        string="Hide Zero Balance Accounts", default=True
    )
    include_opening_balance = fields.Boolean(
        string="Include Opening Balance", default=True
    )
    show_partner_detail = fields.Boolean(
        string="Show Partner Detail",
        default=False,
        help="Show partner-wise breakdown for Receivable and Payable accounts.",
    )
    journal_ids = fields.Many2many(
        "account.journal",
        string="Journals",
        help="Leave empty to include all journals.",
    )
    account_ids = fields.Many2many(
        "account.account",
        string="Accounts",
        help="Leave empty to include all accounts.",
    )

    # ── helpers ───────────────────────────────────────────────────────

    def _common_domain(self):
        domain = []
        if self.target_move == "posted":
            domain.append(("move_id.state", "=", "posted"))
        if self.journal_ids:
            domain.append(("journal_id", "in", self.journal_ids.ids))
        if self.account_ids:
            domain.append(("account_id", "in", self.account_ids.ids))
        return domain

    def _base_domain(self):
        return [
            ("date", ">=", self.date_from),
            ("date", "<=", self.date_to),
        ] + self._common_domain()

    def _opening_domain(self):
        return [
            ("date", "<", self.date_from),
        ] + self._common_domain()

    # ── data collection ───────────────────────────────────────────────

    def _get_trial_balance_data(self):
        MoveLine = self.env["account.move.line"]

        # period totals
        period_data = {}
        groups = MoveLine.read_group(
            self._base_domain(),
            ["debit:sum", "credit:sum"],
            ["account_id"],
        )
        for g in groups:
            if not g["account_id"]:
                continue
            acc_id = g["account_id"][0]
            period_data[acc_id] = {
                "debit": g["debit"] or 0.0,
                "credit": g["credit"] or 0.0,
            }

        # opening totals
        opening_data = {}
        if self.include_opening_balance:
            groups = MoveLine.read_group(
                self._opening_domain(),
                ["debit:sum", "credit:sum"],
                ["account_id"],
            )
            for g in groups:
                if not g["account_id"]:
                    continue
                acc_id = g["account_id"][0]
                opening_data[acc_id] = {
                    "debit": g["debit"] or 0.0,
                    "credit": g["credit"] or 0.0,
                }

        # merge
        all_ids = set(period_data) | set(opening_data)
        if not all_ids:
            return []

        accounts = self.env["account.account"].browse(all_ids)
        rows = []
        for acc in accounts.sorted(key=lambda a: a.code):
            op = opening_data.get(acc.id, {"debit": 0, "credit": 0})
            per = period_data.get(acc.id, {"debit": 0, "credit": 0})

            # net opening balance split into Dr / Cr
            op_net = op["debit"] - op["credit"]
            op_debit = op_net if op_net > 0 else 0.0
            op_credit = -op_net if op_net < 0 else 0.0

            # net closing balance split into Dr / Cr
            cl_net = op_net + per["debit"] - per["credit"]
            cl_debit = cl_net if cl_net > 0 else 0.0
            cl_credit = -cl_net if cl_net < 0 else 0.0

            if self.hide_zero_balance and not (
                op_debit or op_credit or per["debit"] or per["credit"]
                or cl_debit or cl_credit
            ):
                continue

            rows.append(
                {
                    "code": acc.code,
                    "name": acc.name,
                    "op_debit": op_debit,
                    "op_credit": op_credit,
                    "debit": per["debit"],
                    "credit": per["credit"],
                    "cl_debit": cl_debit,
                    "cl_credit": cl_credit,
                    "account": acc,
                }
            )
        return rows

    def _get_partner_rows(self, account):
        """Return partner-wise breakdown for one account."""
        MoveLine = self.env["account.move.line"]

        period_groups = MoveLine.read_group(
            self._base_domain() + [("account_id", "=", account.id)],
            ["debit:sum", "credit:sum"],
            ["partner_id"],
        )
        period_map = {}
        for g in period_groups:
            pid = g["partner_id"][0] if g["partner_id"] else 0
            pname = g["partner_id"][1] if g["partner_id"] else "No Partner"
            period_map[pid] = {
                "name": pname,
                "debit": g["debit"] or 0.0,
                "credit": g["credit"] or 0.0,
            }

        opening_map = {}
        if self.include_opening_balance:
            opening_groups = MoveLine.read_group(
                self._opening_domain() + [("account_id", "=", account.id)],
                ["debit:sum", "credit:sum"],
                ["partner_id"],
            )
            for g in opening_groups:
                pid = g["partner_id"][0] if g["partner_id"] else 0
                pname = g["partner_id"][1] if g["partner_id"] else "No Partner"
                opening_map[pid] = {
                    "name": pname,
                    "debit": g["debit"] or 0.0,
                    "credit": g["credit"] or 0.0,
                }

        partner_ids = set(period_map) | set(opening_map)
        partner_rows = []
        for pid in sorted(partner_ids):
            op = opening_map.get(pid, {"name": "", "debit": 0, "credit": 0})
            per = period_map.get(pid, {"name": "", "debit": 0, "credit": 0})
            name = per.get("name") or op.get("name") or "No Partner"

            op_net = op["debit"] - op["credit"]
            op_debit = op_net if op_net > 0 else 0.0
            op_credit = -op_net if op_net < 0 else 0.0

            cl_net = op_net + per["debit"] - per["credit"]
            cl_debit = cl_net if cl_net > 0 else 0.0
            cl_credit = -cl_net if cl_net < 0 else 0.0

            if self.hide_zero_balance and not (
                op_debit or op_credit or per["debit"] or per["credit"]
                or cl_debit or cl_credit
            ):
                continue

            partner_rows.append(
                {
                    "name": name,
                    "op_debit": op_debit,
                    "op_credit": op_credit,
                    "debit": per["debit"],
                    "credit": per["credit"],
                    "cl_debit": cl_debit,
                    "cl_credit": cl_credit,
                }
            )
        partner_rows = sorted(partner_rows, key=lambda r: r["name"])
        return partner_rows

    # ── excel export ──────────────────────────────────────────────────

    def action_export_excel(self):
        self.ensure_one()
        rows = self._get_trial_balance_data()
        show_partners = self.show_partner_detail
        partner_types = ("asset_receivable", "liability_payable")

        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})
        ws = wb.add_worksheet("Trial Balance")

        # ── formats ──
        title_fmt = wb.add_format(
            {"bold": True, "font_size": 14, "align": "center"}
        )
        date_disp = wb.add_format({"align": "center", "font_size": 11})
        header_fmt = wb.add_format(
            {
                "bold": True,
                "bg_color": "#4472C4",
                "font_color": "white",
                "border": 1,
                "align": "center",
            }
        )
        acct_fmt = wb.add_format({"bold": True, "bg_color": "#D9E2F3", "border": 1})
        acct_num_fmt = wb.add_format(
            {
                "bold": True,
                "bg_color": "#D9E2F3",
                "border": 1,
                "num_format": "#,##0.00",
                "align": "right",
            }
        )
        partner_fmt = wb.add_format(
            {"indent": 2, "italic": True, "font_color": "#555555", "border": 1}
        )
        partner_num_fmt = wb.add_format(
            {
                "italic": True,
                "font_color": "#555555",
                "border": 1,
                "num_format": "#,##0.00",
                "align": "right",
            }
        )
        num_fmt = wb.add_format(
            {"num_format": "#,##0.00", "border": 1, "align": "right"}
        )
        total_fmt = wb.add_format(
            {"bold": True, "bg_color": "#4472C4", "font_color": "white", "border": 1}
        )
        total_num_fmt = wb.add_format(
            {
                "bold": True,
                "bg_color": "#4472C4",
                "font_color": "white",
                "border": 1,
                "num_format": "#,##0.00",
                "align": "right",
            }
        )

        # ── title ──
        ws.merge_range("A1:H1", self.env.company.name, title_fmt)
        ws.merge_range(
            "A2:H2",
            f"Trial Balance  |  {self.date_from}  to  {self.date_to}",
            date_disp,
        )

        # ── column widths ──
        ws.set_column("A:A", 12)   # Code
        ws.set_column("B:B", 40)   # Account
        ws.set_column("C:H", 18)   # 6 number columns

        # ── header rows (merged groups + sub-headers) ──
        row = 3
        # Group headers
        ws.merge_range(row, 2, row, 3, "Opening Balance", header_fmt)
        ws.merge_range(row, 4, row, 5, f"{self.date_from} to {self.date_to}", header_fmt)
        ws.merge_range(row, 6, row, 7, "Closing Balance", header_fmt)
        ws.write(row, 0, "", header_fmt)
        ws.write(row, 1, "", header_fmt)
        row += 1
        # Sub-headers
        headers = ["Code", "Account",
                    "Debit", "Credit",   # Opening
                    "Debit", "Credit",   # Transactions
                    "Debit", "Credit"]   # Closing
        for col, label in enumerate(headers):
            ws.write(row, col, label, header_fmt)
        row += 1

        # ── data rows ──
        totals = {
            "op_debit": 0, "op_credit": 0,
            "debit": 0, "credit": 0,
            "cl_debit": 0, "cl_credit": 0,
        }
        for r in rows:
            is_partner_acct = (
                show_partners and r["account"].account_type in partner_types
            )
            fmt = acct_fmt if is_partner_acct else None
            nf = acct_num_fmt if is_partner_acct else num_fmt

            ws.write(row, 0, r["code"], fmt)
            ws.write(row, 1, r["name"], fmt)
            ws.write(row, 2, r["op_debit"], nf)
            ws.write(row, 3, r["op_credit"], nf)
            ws.write(row, 4, r["debit"], nf)
            ws.write(row, 5, r["credit"], nf)
            ws.write(row, 6, r["cl_debit"], nf)
            ws.write(row, 7, r["cl_credit"], nf)
            row += 1

            if is_partner_acct:
                for pr in self._get_partner_rows(r["account"]):
                    ws.write(row, 0, "", partner_fmt)
                    ws.write(row, 1, pr["name"], partner_fmt)
                    ws.write(row, 2, pr["op_debit"], partner_num_fmt)
                    ws.write(row, 3, pr["op_credit"], partner_num_fmt)
                    ws.write(row, 4, pr["debit"], partner_num_fmt)
                    ws.write(row, 5, pr["credit"], partner_num_fmt)
                    ws.write(row, 6, pr["cl_debit"], partner_num_fmt)
                    ws.write(row, 7, pr["cl_credit"], partner_num_fmt)
                    row += 1

            totals["op_debit"] += r["op_debit"]
            totals["op_credit"] += r["op_credit"]
            totals["debit"] += r["debit"]
            totals["credit"] += r["credit"]
            totals["cl_debit"] += r["cl_debit"]
            totals["cl_credit"] += r["cl_credit"]

        # ── totals row ──
        ws.write(row, 0, "", total_fmt)
        ws.write(row, 1, "TOTAL", total_fmt)
        ws.write(row, 2, totals["op_debit"], total_num_fmt)
        ws.write(row, 3, totals["op_credit"], total_num_fmt)
        ws.write(row, 4, totals["debit"], total_num_fmt)
        ws.write(row, 5, totals["credit"], total_num_fmt)
        ws.write(row, 6, totals["cl_debit"], total_num_fmt)
        ws.write(row, 7, totals["cl_credit"], total_num_fmt)

        wb.close()
        excel_data = buf.getvalue()
        buf.close()

        # create attachment & return download action
        attachment = self.env["ir.attachment"].create(
            {
                "name": "trial_balance.xlsx",
                "type": "binary",
                "datas": base64.b64encode(excel_data),
                "mimetype": "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet",
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "new",
        }
