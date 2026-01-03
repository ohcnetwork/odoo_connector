from odoo import models, fields
from datetime import timedelta
from odoo.exceptions import UserError
import io
import base64
import xlsxwriter


class TrialBalanceExcelWizard(models.TransientModel):
    _name = 'trial.balance.excel.wizard'
    _description = 'Trial Balance Excel Report Wizard'

    def _default_date_from(self):
        """Get default start date (April 1st of current fiscal year) based on user's timezone"""
        today = fields.Date.context_today(self)
        # If before April, use previous year's April 1st
        if today.month < 4:
            return today.replace(year=today.year - 1, month=4, day=1)
        return today.replace(month=4, day=1)

    def _default_date_to(self):
        """Get default end date (today) based on user's timezone"""
        return fields.Date.context_today(self)

    date_from = fields.Date(
        string="Date From",
        required=True,
        default=_default_date_from,
    )
    date_to = fields.Date(
        string="Date To",
        required=True,
        default=_default_date_to,
    )
    target_move = fields.Selection(
        selection=[
            ('posted', 'Posted Entries'),
            ('all', 'All Entries'),
        ],
        string="Target Moves",
        required=True,
        default='posted',
    )
    hide_zero_balance = fields.Boolean(
        string="Hide Zero Balance Accounts",
        default=True,
        help="Hide accounts where closing debit and credit are both zero"
    )
    journal_ids = fields.Many2many(
        'account.journal',
        string="Journals",
        help="Leave empty to include all journals"
    )
    account_ids = fields.Many2many(
        'account.account',
        string="Accounts",
        help="Leave empty to include all accounts"
    )

    def _format_date(self, dt):
        """Format date as DD-MM-YYYY"""
        return dt.strftime('%d-%m-%Y')

    def _get_trial_balance_data(self):
        """
        Get trial balance data using optimized read_group queries.
        Returns list of dicts with account and balance data.
        """
        AccountMoveLine = self.env['account.move.line']
        
        # Build base domain
        base_domain = [
            ('company_id', '=', self.env.company.id),
        ]
        
        # Filter by target moves (posted/all)
        if self.target_move == 'posted':
            base_domain.append(('parent_state', '=', 'posted'))
        
        # Filter by journals if specified
        if self.journal_ids:
            base_domain.append(('journal_id', 'in', self.journal_ids.ids))
        
        # Filter by accounts if specified
        if self.account_ids:
            base_domain.append(('account_id', 'in', self.account_ids.ids))
        
        # Opening balance: all entries before date_from
        opening_domain = base_domain + [('date', '<', self.date_from)]
        opening_data = AccountMoveLine.read_group(
            domain=opening_domain,
            fields=['account_id', 'debit:sum', 'credit:sum'],
            groupby=['account_id'],
        )
        
        # Period transactions: entries within the date range
        period_domain = base_domain + [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]
        period_data = AccountMoveLine.read_group(
            domain=period_domain,
            fields=['account_id', 'debit:sum', 'credit:sum'],
            groupby=['account_id'],
        )
        
        # Build consolidated data
        account_data = {}
        
        # Process opening balances
        for item in opening_data:
            if item['account_id']:
                acc_id = item['account_id'][0]
                account_data[acc_id] = {
                    'opening_debit': item['debit'] or 0.0,
                    'opening_credit': item['credit'] or 0.0,
                    'period_debit': 0.0,
                    'period_credit': 0.0,
                }
        
        # Process period transactions
        for item in period_data:
            if item['account_id']:
                acc_id = item['account_id'][0]
                if acc_id not in account_data:
                    account_data[acc_id] = {
                        'opening_debit': 0.0,
                        'opening_credit': 0.0,
                        'period_debit': 0.0,
                        'period_credit': 0.0,
                    }
                account_data[acc_id]['period_debit'] = item['debit'] or 0.0
                account_data[acc_id]['period_credit'] = item['credit'] or 0.0
        
        if not account_data:
            raise UserError("No transactions found for the selected criteria.")
        
        # Fetch account details
        accounts = self.env['account.account'].browse(list(account_data.keys()))
        
        # Build final result with account info
        result = []
        for account in accounts.sorted(key=lambda a: a.name or ''):
            data = account_data[account.id]
            closing_debit = data['opening_debit'] + data['period_debit']
            closing_credit = data['opening_credit'] + data['period_credit']
            
            # Skip zero balance accounts if option is enabled
            if self.hide_zero_balance:
                if closing_debit == 0.0 and closing_credit == 0.0:
                    continue
            
            result.append({
                'account': account,
                'opening_debit': data['opening_debit'],
                'opening_credit': data['opening_credit'],
                'period_debit': data['period_debit'],
                'period_credit': data['period_credit'],
                'closing_debit': closing_debit,
                'closing_credit': closing_credit,
            })
        
        if not result:
            raise UserError("No accounts with balances found for the selected criteria.")
        
        return result

    def action_export_excel(self):
        """Export trial balance report to Excel"""
        self.ensure_one()
        
        if self.date_from > self.date_to:
            raise UserError("Start date cannot be after end date!")

        # Get report data
        report_data = self._get_trial_balance_data()
        
        # Create Excel workbook
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet("Trial Balance")

        # Get company name
        company_name = self.env.company.name or 'Company'

        # Calculate opening balance date (day before date_from)
        opening_date = self.date_from - timedelta(days=1)

        # Define formats
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'align': 'left',
        })
        info_format = workbook.add_format({
            'italic': True,
            'font_size': 10,
            'align': 'left',
        })
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4472C4',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
        })
        sub_header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#FFFF00',
            'border': 1,
            'align': 'center',
        })
        text_format = workbook.add_format({
            'border': 1,
            'align': 'left',
        })
        number_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'num_format': '#,##0.00',
        })
        total_text_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'border': 1,
            'align': 'left',
        })
        total_number_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'border': 1,
            'num_format': '#,##0.00',
            'align': 'right',
        })

        # Title section
        sheet.write('A1', company_name, title_format)
        sheet.write('A2', 'SCHEDULE WISE TRIAL BALANCE', title_format)
        sheet.write('A3', f"From {self._format_date(self.date_from)} To {self._format_date(self.date_to)}", title_format)
        sheet.write('A4', '(Including Opening Balance)', title_format)
        
        # Filter info
        target_move_label = "Posted Entries" if self.target_move == 'posted' else "All Entries"
        sheet.write('A5', f"Target Moves: {target_move_label}", info_format)

        # Header row
        row = 7
        sheet.merge_range(row, 0, row + 1, 0, "ACCOUNT", header_format)
        sheet.merge_range(row, 1, row, 2, f"As On {self._format_date(opening_date)}", header_format)
        sheet.merge_range(row, 3, row, 4, f"From {self._format_date(self.date_from)} To {self._format_date(self.date_to)}", header_format)
        sheet.merge_range(row, 5, row, 6, f"As On {self._format_date(self.date_to)}", header_format)

        # Sub-header row
        row += 1
        sheet.write(row, 1, "DEBIT", sub_header_format)
        sheet.write(row, 2, "CREDIT", sub_header_format)
        sheet.write(row, 3, "DEBIT", sub_header_format)
        sheet.write(row, 4, "CREDIT", sub_header_format)
        sheet.write(row, 5, "DEBIT", sub_header_format)
        sheet.write(row, 6, "CREDIT", sub_header_format)
        row += 1

        # Freeze panes - freeze header rows
        sheet.freeze_panes(row, 1)

        # Initialize totals
        totals = {
            'opening_debit': 0.0,
            'opening_credit': 0.0,
            'period_debit': 0.0,
            'period_credit': 0.0,
            'closing_debit': 0.0,
            'closing_credit': 0.0,
        }

        # Write data rows
        for item in report_data:
            account = item['account']
            
            sheet.write(row, 0, account.name or '', text_format)
            sheet.write_number(row, 1, item['opening_debit'], number_format)
            sheet.write_number(row, 2, item['opening_credit'], number_format)
            sheet.write_number(row, 3, item['period_debit'], number_format)
            sheet.write_number(row, 4, item['period_credit'], number_format)
            sheet.write_number(row, 5, item['closing_debit'], number_format)
            sheet.write_number(row, 6, item['closing_credit'], number_format)
            row += 1

            # Accumulate totals
            for key in totals:
                totals[key] += item[key]

        # Write totals row
        sheet.write(row, 0, "Total", total_text_format)
        sheet.write_number(row, 1, totals['opening_debit'], total_number_format)
        sheet.write_number(row, 2, totals['opening_credit'], total_number_format)
        sheet.write_number(row, 3, totals['period_debit'], total_number_format)
        sheet.write_number(row, 4, totals['period_credit'], total_number_format)
        sheet.write_number(row, 5, totals['closing_debit'], total_number_format)
        sheet.write_number(row, 6, totals['closing_credit'], total_number_format)

        # Set column widths
        sheet.set_column('A:A', 45)
        sheet.set_column('B:G', 18)

        workbook.close()

        # Create attachment
        file_data = base64.b64encode(output.getvalue())
        output.close()

        file_name = f"Trial_Balance_{self.date_from}_to_{self.date_to}.xlsx"

        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'type': 'binary',
            'datas': file_data,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{attachment.id}?download=true",
            'target': 'new',
        }
