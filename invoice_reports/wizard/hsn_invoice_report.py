# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date
import io
import xlsxwriter
import base64
from collections import defaultdict

# Standard UQC codes as per GST portal
UQC_MAPPING = {
    # Weight
    'kg': 'KGS', 'kgs': 'KGS', 'kilogram': 'KGS', 'kilograms': 'KGS',
    'gm': 'GMS', 'gms': 'GMS', 'gram': 'GMS', 'grams': 'GMS',
    'ton': 'TON', 'tonne': 'TON', 'tonnes': 'TON', 'mt': 'TON',
    'quintal': 'QTL', 'qtl': 'QTL',
    'mg': 'OTH', 'milligram': 'OTH',
    # Volume
    'ltr': 'LTR', 'litre': 'LTR', 'liter': 'LTR', 'litres': 'LTR', 'l': 'LTR',
    'ml': 'OTH', 'millilitre': 'OTH',
    'kl': 'KLR', 'kilolitre': 'KLR',
    'cbm': 'CBM', 'cubic meter': 'CBM', 'cum': 'CBM',
    # Length
    'mtr': 'MTR', 'meter': 'MTR', 'metre': 'MTR', 'meters': 'MTR', 'm': 'MTR',
    'cm': 'CMS', 'centimeter': 'CMS',
    'km': 'KME', 'kilometer': 'KME',
    'yard': 'YDS', 'yards': 'YDS', 'yd': 'YDS',
    # Area
    'sqm': 'SQM', 'sq.m': 'SQM', 'square meter': 'SQM',
    'sqf': 'SQF', 'sq.ft': 'SQF', 'square feet': 'SQF', 'sqft': 'SQF',
    # Count
    'units': 'UNT', 'unit': 'UNT', 'ea': 'UNT', 'each': 'UNT',
    'nos': 'NOS', 'nos.': 'NOS', 'numbers': 'NOS', 'no': 'NOS', 'number': 'NOS',
    'pcs': 'PCS', 'pieces': 'PCS', 'piece': 'PCS', 'pc': 'PCS',
    'dozen': 'DOZ', 'doz': 'DOZ', 'dzn': 'DOZ',
    'gross': 'GRS', 'grs': 'GRS',
    'pair': 'PRS', 'pairs': 'PRS', 'pr': 'PRS',
    'set': 'SET', 'sets': 'SET',
    'thousand': 'THD', 'thousands': 'THD',
    # Packaging
    'box': 'BOX', 'boxes': 'BOX',
    'bag': 'BAG', 'bags': 'BAG',
    'bundle': 'BDL', 'bundles': 'BDL', 'bdl': 'BDL',
    'pack': 'PAC', 'packs': 'PAC', 'packet': 'PAC', 'packets': 'PAC',
    'roll': 'ROL', 'rolls': 'ROL',
    'drum': 'DRM', 'drums': 'DRM',
    'bottle': 'BTL', 'bottles': 'BTL',
    'can': 'CAN', 'cans': 'CAN',
    'carton': 'CTN', 'cartons': 'CTN',
    'tube': 'TUB', 'tubes': 'TUB',
}

# GST tax type identification keywords
GST_TAX_KEYWORDS = {
    'igst': ['igst', 'integrated'],
    'cgst': ['cgst', 'central'],
    'sgst': ['sgst', 'state', 'utgst'],
    'cess': ['cess', 'compensation'],
}


class HSNSummaryWizard(models.TransientModel):
    _name = 'invoice.hsn.excel.wizard'
    _description = 'HSN Summary Sheet Report'

    # ==================== FIELDS ====================

    company_id = fields.Many2one(
        'res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(
        string="From Date",
        required=True,
        default=lambda self: date.today().replace(day=1),
    )
    date_to = fields.Date(
        string="To Date",
        required=True,
        default=lambda self: date.today(),
    )
    gst_rate_id = fields.Many2one(
        'hsn.gst.rate',
        string="GST Rate",
        help="Filter by GST rate. Leave empty to include all rates.",
    )
    available_rate_ids = fields.Many2many(
        'hsn.gst.rate',
        compute='_compute_available_rates',
        string="Available Rates",
    )
    move_type = fields.Selection(
        selection=[
            ('out_invoice', 'Sales Invoices'),
            ('out_refund', 'Sales Credit Notes'),
            ('in_invoice', 'Purchase Bills'),
            ('in_refund', 'Purchase Debit Notes'),
            ('out_all', 'All Sales (Invoice + Credit Note)'),
            ('in_all', 'All Purchases (Bill + Debit Note)'),
        ],
        string="Transaction Type",
        default='out_invoice',
        required=True,
    )
    group_by = fields.Selection(
        selection=[
            ('hsn_rate', 'HSN + Tax Rate (GST Compliant)'),
            ('hsn_only', 'HSN Only'),
        ],
        string="Group By",
        default='hsn_rate',
        required=True,
        help="GST returns require grouping by HSN + Rate.",
    )
    journal_ids = fields.Many2many(
        'account.journal',
        string="Journals",
        help="Leave empty to include all applicable journals.",
    )
    include_zero_qty = fields.Boolean(
        string="Include Zero Quantity Lines",
        default=False,
        help="Include lines with zero quantity in the report.",
    )

    # ==================== COMPUTE / ONCHANGE ====================

    @api.depends('company_id')
    def _compute_available_rates(self):
        """Compute available GST rates from system taxes."""
        for wizard in self:
            wizard.available_rate_ids = self.env['hsn.gst.rate'].get_available_rates(
                wizard.company_id.id
            )

    @api.onchange('company_id')
    def _onchange_company_id(self):
        """Clear GST rate and sync rates when company changes."""
        self.gst_rate_id = False
        if self.company_id:
            self.env['hsn.gst.rate'].sync_gst_rates(self.company_id.id)

    # ==================== CONSTRAINTS ====================

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_("'From Date' cannot be later than 'To Date'."))

    # ==================== HELPER METHODS ====================

    def _get_uqc_code(self, uom_name):
        """Convert UOM name to standard UQC code as per GST portal."""
        if not uom_name:
            return 'OTH'
        uom_lower = uom_name.lower().strip()
        return UQC_MAPPING.get(uom_lower, 'OTH')

    def _categorize_tax(self, tax):
        """Categorize tax record as IGST, CGST, SGST/UTGST or Cess."""
        if not tax:
            return None
        search_text = ((tax.name or '') + ' ' + (tax.description or '')).lower()
        for tax_type, keywords in GST_TAX_KEYWORDS.items():
            if any(kw in search_text for kw in keywords):
                return tax_type
        return None

    def _get_combined_gst_rate(self, tax_ids):
        """Calculate the combined GST rate from tax records."""
        total_rate = 0.0
        for tax in tax_ids:
            if tax.amount_type == 'percent':
                tax_type = self._categorize_tax(tax)
                if tax_type in ('igst', 'cgst', 'sgst'):
                    total_rate += abs(tax.amount)
        return round(total_rate, 2)

    def _get_move_types(self):
        """Get list of move types based on selection."""
        mapping = {
            'out_invoice': ['out_invoice'],
            'out_refund': ['out_refund'],
            'in_invoice': ['in_invoice'],
            'in_refund': ['in_refund'],
            'out_all': ['out_invoice', 'out_refund'],
            'in_all': ['in_invoice', 'in_refund'],
        }
        return mapping.get(self.move_type, ['out_invoice'])

    def _get_sign(self, move_type):
        """Get sign multiplier for amounts (negative for credit/debit notes)."""
        return -1 if move_type in ('out_refund', 'in_refund') else 1

    def _compute_line_taxes(self, line, invoice):
        """Compute tax amounts for a single invoice line."""
        price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
        tax_data = line.tax_ids.compute_all(
            price_unit,
            invoice.currency_id,
            line.quantity,
            product=line.product_id,
            partner=invoice.partner_id,
        )

        result = {'igst': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'cess': 0.0}
        for tax_detail in tax_data.get('taxes', []):
            tax_id = tax_detail.get('id')
            if tax_id:
                tax_record = self.env['account.tax'].browse(tax_id)
                tax_type = self._categorize_tax(tax_record)
                if tax_type in result:
                    result[tax_type] += tax_detail.get('amount', 0.0)
        return result

    def _collect_hsn_data(self, invoices):
        """Collect and aggregate HSN data from invoices."""
        selected_rate = self.gst_rate_id.rate if self.gst_rate_id else None
        group_by_rate = self.group_by == 'hsn_rate'

        hsn_data = defaultdict(lambda: {
            'hsn': '',
            'description': '',
            'uqc': '',
            'rate': 0.0,
            'total_qty': 0.0,
            'total_value': 0.0,
            'taxable_value': 0.0,
            'igst_amount': 0.0,
            'cgst_amount': 0.0,
            'sgst_amount': 0.0,
            'cess_amount': 0.0,
        })

        for invoice in invoices:
            sign = self._get_sign(invoice.move_type)

            for line in invoice.invoice_line_ids:
                # Skip non-product lines
                if line.display_type and line.display_type != 'product':
                    continue

                # Skip lines without HSN
                hsn_code = line.product_id.l10n_in_hsn_code if line.product_id else ''
                if not hsn_code:
                    continue

                # Skip zero quantity lines if not included
                if not self.include_zero_qty and line.quantity == 0:
                    continue

                # Calculate GST rate
                line_gst_rate = self._get_combined_gst_rate(line.tax_ids)

                # Filter by selected GST rate
                if selected_rate is not None:
                    if abs(line_gst_rate - selected_rate) > 0.5:
                        continue

                # Build grouping key
                uom_name = line.product_uom_id.name if line.product_uom_id else ''
                if group_by_rate:
                    key = (hsn_code, line_gst_rate, uom_name)
                else:
                    key = (hsn_code, uom_name)

                # Compute tax amounts
                taxes = self._compute_line_taxes(line, invoice)

                # Get description (HSN description may be on product.template)
                description = ''
                if line.product_id:
                    # Try to get HSN description from product template, fallback to product name
                    product_tmpl = line.product_id.product_tmpl_id
                    if hasattr(product_tmpl, 'l10n_in_hsn_description') and product_tmpl.l10n_in_hsn_description:
                        description = product_tmpl.l10n_in_hsn_description
                    else:
                        description = line.product_id.name or ''

                # Aggregate data
                hsn_data[key]['hsn'] = hsn_code
                hsn_data[key]['description'] = description
                hsn_data[key]['uqc'] = self._get_uqc_code(uom_name)
                hsn_data[key]['rate'] = line_gst_rate
                hsn_data[key]['total_qty'] += line.quantity * sign
                hsn_data[key]['total_value'] += line.price_total * sign
                hsn_data[key]['taxable_value'] += line.price_subtotal * sign
                hsn_data[key]['igst_amount'] += taxes['igst'] * sign
                hsn_data[key]['cgst_amount'] += taxes['cgst'] * sign
                hsn_data[key]['sgst_amount'] += taxes['sgst'] * sign
                hsn_data[key]['cess_amount'] += taxes['cess'] * sign

        return hsn_data

    # ==================== EXCEL GENERATION ====================

    def _create_excel_formats(self, workbook):
        """Create and return all Excel formats."""
        return {
            'title': workbook.add_format({
                'bold': True,
                'font_size': 14,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#2F5496',
                'font_color': 'white',
                'border': 1,
            }),
            'subtitle': workbook.add_format({
                'bold': True,
                'font_size': 11,
                'align': 'left',
                'valign': 'vcenter',
            }),
            'header': workbook.add_format({
                'bold': True,
                'font_size': 10,
                'bg_color': '#D6DCE5',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
            }),
            'text': workbook.add_format({
                'border': 1,
                'align': 'left',
                'font_size': 10,
            }),
            'text_center': workbook.add_format({
                'border': 1,
                'align': 'center',
                'font_size': 10,
            }),
            'number': workbook.add_format({
                'border': 1,
                'align': 'right',
                'num_format': '#,##0.00',
                'font_size': 10,
            }),
            'qty': workbook.add_format({
                'border': 1,
                'align': 'right',
                'num_format': '#,##0.000',
                'font_size': 10,
            }),
            'rate': workbook.add_format({
                'border': 1,
                'align': 'center',
                'num_format': '0.00%',
                'font_size': 10,
            }),
            'total_text': workbook.add_format({
                'bold': True,
                'border': 2,
                'align': 'left',
                'bg_color': '#E2EFDA',
                'font_size': 10,
            }),
            'total_number': workbook.add_format({
                'bold': True,
                'border': 2,
                'align': 'right',
                'num_format': '#,##0.00',
                'bg_color': '#E2EFDA',
                'font_size': 10,
            }),
            'total_qty': workbook.add_format({
                'bold': True,
                'border': 2,
                'align': 'right',
                'num_format': '#,##0.000',
                'bg_color': '#E2EFDA',
                'font_size': 10,
            }),
            'sr_no': workbook.add_format({
                'border': 1,
                'align': 'center',
                'font_size': 10,
            }),
        }

    def _write_excel_header(self, sheet, formats):
        """Write report header section."""
        # Title
        gst_rate_label = f"{self.gst_rate_id.name}" if self.gst_rate_id else "All Rates"
        move_type_label = dict(self._fields['move_type'].selection).get(self.move_type, '')
        title = f"HSN SUMMARY SHEET - {gst_rate_label} ({move_type_label})"
        sheet.merge_range('A1:L1', title, formats['title'])
        sheet.set_row(0, 25)

        # Company and period info
        sheet.write('A2', f"Company: {self.company_id.name}", formats['subtitle'])
        sheet.write('A3', f"Period: {self.date_from.strftime('%d-%b-%Y')} to {self.date_to.strftime('%d-%b-%Y')}", formats['subtitle'])
        if self.journal_ids:
            journal_names = ', '.join(self.journal_ids.mapped('name'))
            sheet.write('A4', f"Journals: {journal_names}", formats['subtitle'])

    def _write_column_headers(self, sheet, row, formats):
        """Write column headers and set widths."""
        headers = [
            ('Sr.', 5),
            ('HSN', 12),
            ('Description', 45),
            ('UQC', 7),
            ('Rate', 8),
            ('Total Qty', 14),
            ('Total Value', 16),
            ('Taxable Value', 16),
            ('IGST Amount', 15),
            ('CGST Amount', 15),
            ('SGST/UTGST Amount', 17),
            ('Cess Amount', 14),
        ]
        for col, (header, width) in enumerate(headers):
            sheet.write(row, col, header, formats['header'])
            sheet.set_column(col, col, width)
        return row + 1

    def _write_data_rows(self, sheet, start_row, hsn_data, formats):
        """Write HSN data rows and return totals."""
        totals = {
            'total_qty': 0.0,
            'total_value': 0.0,
            'taxable_value': 0.0,
            'igst_amount': 0.0,
            'cgst_amount': 0.0,
            'sgst_amount': 0.0,
            'cess_amount': 0.0,
        }

        # Sort by HSN code, then by rate
        sorted_data = sorted(hsn_data.items(), key=lambda x: (x[1]['hsn'], x[1]['rate']))

        row = start_row
        for sr_no, (key, vals) in enumerate(sorted_data, 1):
            sheet.write(row, 0, sr_no, formats['sr_no'])
            sheet.write(row, 1, vals['hsn'], formats['text'])
            sheet.write(row, 2, vals['description'], formats['text'])
            sheet.write(row, 3, vals['uqc'], formats['text_center'])
            sheet.write(row, 4, vals['rate'] / 100 if vals['rate'] else 0, formats['rate'])
            sheet.write(row, 5, vals['total_qty'], formats['qty'])
            sheet.write(row, 6, vals['total_value'], formats['number'])
            sheet.write(row, 7, vals['taxable_value'], formats['number'])
            sheet.write(row, 8, vals['igst_amount'], formats['number'])
            sheet.write(row, 9, vals['cgst_amount'], formats['number'])
            sheet.write(row, 10, vals['sgst_amount'], formats['number'])
            sheet.write(row, 11, vals['cess_amount'], formats['number'])

            # Accumulate totals
            for total_key in totals:
                totals[total_key] += vals.get(total_key, 0.0)

            row += 1

        return row, totals

    def _write_totals_row(self, sheet, row, totals, formats):
        """Write the totals row."""
        sheet.write(row, 0, '', formats['total_text'])
        sheet.write(row, 1, 'TOTAL', formats['total_text'])
        sheet.write(row, 2, '', formats['total_text'])
        sheet.write(row, 3, '', formats['total_text'])
        sheet.write(row, 4, '', formats['total_text'])
        sheet.write(row, 5, totals['total_qty'], formats['total_qty'])
        sheet.write(row, 6, totals['total_value'], formats['total_number'])
        sheet.write(row, 7, totals['taxable_value'], formats['total_number'])
        sheet.write(row, 8, totals['igst_amount'], formats['total_number'])
        sheet.write(row, 9, totals['cgst_amount'], formats['total_number'])
        sheet.write(row, 10, totals['sgst_amount'], formats['total_number'])
        sheet.write(row, 11, totals['cess_amount'], formats['total_number'])

    def _generate_excel(self, hsn_data):
        """Generate Excel file from HSN data."""
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('HSN Summary')

        # Freeze panes for better navigation
        sheet.freeze_panes(6, 2)

        # Create formats
        formats = self._create_excel_formats(workbook)

        # Write header
        self._write_excel_header(sheet, formats)

        # Write column headers (row 5, index 5)
        data_start_row = self._write_column_headers(sheet, 5, formats)

        if hsn_data:
            # Write data rows
            next_row, totals = self._write_data_rows(sheet, data_start_row, hsn_data, formats)

            # Write totals
            self._write_totals_row(sheet, next_row, totals, formats)
        else:
            # No data message
            no_data_fmt = workbook.add_format({
                'align': 'center',
                'valign': 'vcenter',
                'italic': True,
                'font_color': '#808080',
            })
            sheet.merge_range(data_start_row, 0, data_start_row, 11,
                              'No data found for the selected criteria.', no_data_fmt)

        workbook.close()
        output.seek(0)
        return output.read()

    # ==================== MAIN ACTION ====================

    def action_print_excel(self):
        """Generate and download HSN Summary Excel report."""
        self.ensure_one()

        # Build search domain
        move_types = self._get_move_types()
        domain = [
            ('company_id', '=', self.company_id.id),
            ('move_type', 'in', move_types),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('state', '=', 'posted'),
        ]

        if self.journal_ids:
            domain.append(('journal_id', 'in', self.journal_ids.ids))

        # Search invoices
        invoices = self.env['account.move'].search(domain)

        # Filter to only those with HSN codes
        invoices = invoices.filtered(
            lambda inv: any(
                line.product_id.l10n_in_hsn_code
                for line in inv.invoice_line_ids
                if line.product_id
            )
        )

        # Collect HSN data
        hsn_data = self._collect_hsn_data(invoices)

        # Generate Excel
        excel_content = self._generate_excel(hsn_data)
        file_data = base64.b64encode(excel_content)

        # Create filename
        rate_suffix = f"_{self.gst_rate_id.rate}pct" if self.gst_rate_id else ""
        filename = f"HSN_Summary{rate_suffix}_{self.date_from}_{self.date_to}.xlsx"

        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': file_data,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }


class HSNGstRate(models.Model):
    """Model to store unique GST rates extracted from system taxes."""
    _name = 'hsn.gst.rate'
    _description = 'GST Rate for HSN Report'
    _order = 'rate'
    _rec_name = 'name'

    name = fields.Char(string="Name", compute='_compute_name', store=True)
    rate = fields.Float(string="Rate (%)", required=True)
    company_id = fields.Many2one('res.company', string="Company", required=True)

    _sql_constraints = [
        ('unique_rate_per_company', 'UNIQUE(rate, company_id)', 'GST rate must be unique per company.'),
    ]

    @api.depends('rate')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.rate}%"

    @api.model
    def sync_gst_rates(self, company_id=None):
        """Sync GST rates from account.tax records."""
        if company_id:
            companies = self.env['res.company'].browse(company_id)
        else:
            companies = self.env['res.company'].search([])

        for company in companies:
            # Get all GST taxes (IGST gives us the combined rate directly)
            taxes = self.env['account.tax'].search([
                ('company_id', '=', company.id),
                ('amount_type', '=', 'percent'),
                ('type_tax_use', 'in', ['sale', 'purchase']),
            ])

            # Extract unique rates from IGST taxes
            gst_rates = set()
            for tax in taxes:
                tax_name = (tax.name or '').lower()
                # IGST taxes give us the full rate
                if 'igst' in tax_name or 'integrated' in tax_name:
                    gst_rates.add(abs(tax.amount))
                # For CGST/SGST, double the rate to get combined rate
                elif 'cgst' in tax_name or 'central' in tax_name:
                    gst_rates.add(abs(tax.amount) * 2)

            # Also add 0% for nil/exempt
            gst_rates.add(0.0)

            # Create/update rate records
            existing_rates = self.search([('company_id', '=', company.id)])
            existing_rate_values = set(existing_rates.mapped('rate'))

            # Add new rates
            for rate in gst_rates:
                if rate not in existing_rate_values:
                    self.create({
                        'rate': rate,
                        'company_id': company.id,
                    })

            # Remove rates that no longer exist in taxes
            to_remove = existing_rates.filtered(lambda r: r.rate not in gst_rates)
            to_remove.unlink()

        return True

    @api.model
    def get_available_rates(self, company_id):
        """Get available GST rates for a company, syncing if needed."""
        rates = self.search([('company_id', '=', company_id)])
        if not rates:
            self.sync_gst_rates(company_id)
            rates = self.search([('company_id', '=', company_id)])
        return rates
