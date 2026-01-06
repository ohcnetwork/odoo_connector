from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date


class TDSVendorReportWizard(models.TransientModel):
    _name = "tds.vendor.report.wizard"
    _description = "TDS Vendor Excel Report Wizard"

    date_from = fields.Date(string="Date From", required=True, default=lambda self: date.today())
    date_to = fields.Date(string="Date To", required=True, default=lambda self: date.today())
    vendor_ids = fields.Many2many("res.partner", string="Vendor")

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_("Date From cannot be greater than Date To"))

    def action_export_excel(self):
        data = {
            "date_from": self.date_from.strftime("%Y-%m-%d"),
            "date_to": self.date_to.strftime("%Y-%m-%d"),
            "vendor_ids": self.vendor_ids.ids,
        }
        return self.env.ref("vendor_tds_auto_apply.action_tds_vendor_excel_report").report_action(self, data=data)
