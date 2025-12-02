from odoo import models, fields
from datetime import date

class TDSVendorReportWizard(models.TransientModel):
    _name = "tds.vendor.report.wizard"
    _description = "TDS Vendor Excel Report Wizard"

    date_from = fields.Date(string="Date From", required=True, default=lambda self: date.today())
    date_to = fields.Date(string="Date To", required=True, default=lambda self: date.today())
    vendor_ids = fields.Many2many("res.partner", string="Vendor")

    def action_export_excel(self):
        data = {
            "date_from": self.date_from.strftime("%Y-%m-%d"),
            "date_to": self.date_to.strftime("%Y-%m-%d"),
            "vendor_ids": self.vendor_ids.ids,
        }
        return self.env.ref("vendor_tds_auto_apply.action_tds_vendor_excel_report").report_action(self, data=data)
