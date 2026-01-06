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
    include_opening_balance = fields.Boolean(
        string="Include Opening Balance",
        default=True,
        help="Uncheck to exclude opening balance columns from the report"
    )
    group_by_account_group = fields.Boolean(
        string="Group by Account Group",
        default=False,
        help="Group accounts by their account group with subtotals"
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
        
        # Build final result with account info (sorted by account code)
        result = []
        for account in accounts.sorted(key=lambda a: a.code or ''):
            data = account_data[account.id]
            closing_debit = data['opening_debit'] + data['period_debit']
            closing_credit = data['opening_credit'] + data['period_credit']
            
            # Skip zero balance accounts if option is enabled
            if self.hide_zero_balance:
                if closing_debit == 0.0 and closing_credit == 0.0:
                    continue
            
            result.append({
                'account': account,
                'account_group': account.group_id if account.group_id else False,
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
    
    def _get_grouped_trial_balance_data(self):
        """
        Get trial balance data grouped by account groups.
        Returns dict with group names as keys and list of account data as values.
        """
        data = self._get_trial_balance_data()
        
        # Group by account group
        grouped_data = {}
        ungrouped_accounts = []
        
        for item in data:
            group = item.get('account_group')
            if group:
                group_key = (group.id, group.name, group.code_prefix_start or '')
                if group_key not in grouped_data:
                    grouped_data[group_key] = {
                        'group': group,
                        'accounts': [],
                        'totals': {
                            'opening_debit': 0.0,
                            'opening_credit': 0.0,
                            'period_debit': 0.0,
                            'period_credit': 0.0,
                            'closing_debit': 0.0,
                            'closing_credit': 0.0,
                        }
                    }
                grouped_data[group_key]['accounts'].append(item)
                for key in grouped_data[group_key]['totals']:
                    grouped_data[group_key]['totals'][key] += item[key]
            else:
                ungrouped_accounts.append(item)
        
        # Sort groups by code prefix
        sorted_groups = sorted(grouped_data.items(), key=lambda x: x[0][2])
        
        # Add ungrouped accounts at the end if any
        if ungrouped_accounts:
            ungrouped_totals = {
                'opening_debit': 0.0,
                'opening_credit': 0.0,
                'period_debit': 0.0,
                'period_credit': 0.0,
                'closing_debit': 0.0,
                'closing_credit': 0.0,
            }
            for item in ungrouped_accounts:
                for key in ungrouped_totals:
                    ungrouped_totals[key] += item[key]
            
            sorted_groups.append((
                (0, 'Ungrouped Accounts', 'ZZZZ'),
                {
                    'group': None,
                    'accounts': ungrouped_accounts,
                    'totals': ungrouped_totals
                }
            ))
        
        return sorted_groups

    def action_export_excel(self):
        """Export trial balance report to Excel"""
        self.ensure_one()
        
        if self.date_from > self.date_to:
            raise UserError("Start date cannot be after end date!")

        # Create Excel workbook
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet("Trial Balance")

        # Get company name
        company_name = self.env.company.name or 'Company'

        # Calculate opening balance date (day before date_from)
        opening_date = self.date_from - timedelta(days=1)
        
        # Determine column layout based on options
        include_opening = self.include_opening_balance
        
        # Calculate last column index for merging
        if include_opening:
            last_col = 7  # 8 columns: Code, Account, Open Dr, Open Cr, Period Dr, Period Cr, Close Dr, Close Cr
        else:
            last_col = 5  # 6 columns: Code, Account, Period Dr, Period Cr, Close Dr, Close Cr

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
        group_header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#2F75B5',
            'font_color': 'white',
            'border': 1,
            'align': 'left',
            'font_size': 11,
        })
        group_total_text_format = workbook.add_format({
            'bold': True,
            'bg_color': '#BDD7EE',
            'border': 1,
            'align': 'left',
            'italic': True,
        })
        group_total_number_format = workbook.add_format({
            'bold': True,
            'bg_color': '#BDD7EE',
            'border': 1,
            'num_format': '#,##0.00',
            'align': 'right',
            'italic': True,
        })

        # Title section
        sheet.merge_range(0, 0, 0, last_col, company_name, title_format)
        sheet.merge_range(1, 0, 1, last_col, 'SCHEDULE WISE TRIAL BALANCE', title_format)
        sheet.merge_range(2, 0, 2, last_col, f"From {self._format_date(self.date_from)} To {self._format_date(self.date_to)}", title_format)
        
        opening_text = '(Including Opening Balance)' if include_opening else '(Excluding Opening Balance)'
        sheet.merge_range(3, 0, 3, last_col, opening_text, title_format)
        
        # Filter info
        target_move_label = "Posted Entries" if self.target_move == 'posted' else "All Entries"
        group_label = " | Grouped by Account Group" if self.group_by_account_group else ""
        sheet.merge_range(4, 0, 4, last_col, f"Target Moves: {target_move_label}{group_label}", info_format)

        # Header row
        row = 6
        
        if include_opening:
            # Full layout with opening balance
            sheet.merge_range(row, 0, row + 1, 0, "CODE", header_format)
            sheet.merge_range(row, 1, row + 1, 1, "ACCOUNT", header_format)
            sheet.merge_range(row, 2, row, 3, f"As On {self._format_date(opening_date)}", header_format)
            sheet.merge_range(row, 4, row, 5, f"From {self._format_date(self.date_from)} To {self._format_date(self.date_to)}", header_format)
            sheet.merge_range(row, 6, row, 7, f"As On {self._format_date(self.date_to)}", header_format)

            # Sub-header row
            row += 1
            sheet.write(row, 2, "DEBIT", sub_header_format)
            sheet.write(row, 3, "CREDIT", sub_header_format)
            sheet.write(row, 4, "DEBIT", sub_header_format)
            sheet.write(row, 5, "CREDIT", sub_header_format)
            sheet.write(row, 6, "DEBIT", sub_header_format)
            sheet.write(row, 7, "CREDIT", sub_header_format)
        else:
            # Layout without opening balance
            sheet.merge_range(row, 0, row + 1, 0, "CODE", header_format)
            sheet.merge_range(row, 1, row + 1, 1, "ACCOUNT", header_format)
            sheet.merge_range(row, 2, row, 3, f"From {self._format_date(self.date_from)} To {self._format_date(self.date_to)}", header_format)
            sheet.merge_range(row, 4, row, 5, f"As On {self._format_date(self.date_to)}", header_format)

            # Sub-header row
            row += 1
            sheet.write(row, 2, "DEBIT", sub_header_format)
            sheet.write(row, 3, "CREDIT", sub_header_format)
            sheet.write(row, 4, "DEBIT", sub_header_format)
            sheet.write(row, 5, "CREDIT", sub_header_format)
        
        row += 1

        # Freeze panes - freeze header rows and first two columns (Code + Account)
        sheet.freeze_panes(row, 2)

        # Initialize grand totals
        grand_totals = {
            'opening_debit': 0.0,
            'opening_credit': 0.0,
            'period_debit': 0.0,
            'period_credit': 0.0,
            'closing_debit': 0.0,
            'closing_credit': 0.0,
        }

        def write_data_row(row_num, item):
            """Helper to write a data row based on column layout"""
            account = item['account']
            sheet.write(row_num, 0, account.code or '', text_format)
            sheet.write(row_num, 1, account.name or '', text_format)
            
            if include_opening:
                sheet.write_number(row_num, 2, item['opening_debit'], number_format)
                sheet.write_number(row_num, 3, item['opening_credit'], number_format)
                sheet.write_number(row_num, 4, item['period_debit'], number_format)
                sheet.write_number(row_num, 5, item['period_credit'], number_format)
                sheet.write_number(row_num, 6, item['closing_debit'], number_format)
                sheet.write_number(row_num, 7, item['closing_credit'], number_format)
            else:
                sheet.write_number(row_num, 2, item['period_debit'], number_format)
                sheet.write_number(row_num, 3, item['period_credit'], number_format)
                sheet.write_number(row_num, 4, item['closing_debit'], number_format)
                sheet.write_number(row_num, 5, item['closing_credit'], number_format)

        def write_totals_row(row_num, label, totals_dict, text_fmt, num_fmt):
            """Helper to write a totals row based on column layout"""
            sheet.write(row_num, 0, "", text_fmt)
            sheet.write(row_num, 1, label, text_fmt)
            
            if include_opening:
                sheet.write_number(row_num, 2, totals_dict['opening_debit'], num_fmt)
                sheet.write_number(row_num, 3, totals_dict['opening_credit'], num_fmt)
                sheet.write_number(row_num, 4, totals_dict['period_debit'], num_fmt)
                sheet.write_number(row_num, 5, totals_dict['period_credit'], num_fmt)
                sheet.write_number(row_num, 6, totals_dict['closing_debit'], num_fmt)
                sheet.write_number(row_num, 7, totals_dict['closing_credit'], num_fmt)
            else:
                sheet.write_number(row_num, 2, totals_dict['period_debit'], num_fmt)
                sheet.write_number(row_num, 3, totals_dict['period_credit'], num_fmt)
                sheet.write_number(row_num, 4, totals_dict['closing_debit'], num_fmt)
                sheet.write_number(row_num, 5, totals_dict['closing_credit'], num_fmt)

        if self.group_by_account_group:
            # Grouped report
            grouped_data = self._get_grouped_trial_balance_data()
            
            for group_key, group_info in grouped_data:
                group = group_info['group']
                accounts = group_info['accounts']
                group_totals = group_info['totals']
                
                # Write group header
                group_name = group.name if group else "Ungrouped Accounts"
                group_code = group.code_prefix_start if group else ""
                group_label = f"{group_code} - {group_name}" if group_code else group_name
                
                sheet.merge_range(row, 0, row, last_col, group_label, group_header_format)
                row += 1
                
                # Write account rows for this group
                for item in accounts:
                    write_data_row(row, item)
                    row += 1
                
                # Write group subtotal
                write_totals_row(row, f"Subtotal: {group_name}", group_totals, 
                               group_total_text_format, group_total_number_format)
                row += 1
                
                # Add blank row between groups
                row += 1
                
                # Accumulate grand totals
                for key in grand_totals:
                    grand_totals[key] += group_totals[key]
        else:
            # Non-grouped report
            report_data = self._get_trial_balance_data()
            
            for item in report_data:
                write_data_row(row, item)
                row += 1
                
                # Accumulate totals
                for key in grand_totals:
                    grand_totals[key] += item[key]

        # Write grand totals row
        write_totals_row(row, "Grand Total" if self.group_by_account_group else "Total", 
                        grand_totals, total_text_format, total_number_format)

        # Set column widths
        sheet.set_column('A:A', 15)  # Code
        sheet.set_column('B:B', 40)  # Account Name
        if include_opening:
            sheet.set_column('C:H', 18)  # Numeric columns
        else:
            sheet.set_column('C:F', 18)  # Numeric columns

        workbook.close()

        # Create attachment
        file_data = base64.b64encode(output.getvalue())
        output.close()

        suffix = "_grouped" if self.group_by_account_group else ""
        file_name = f"Trial_Balance_{self.date_from}_to_{self.date_to}{suffix}.xlsx"

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
