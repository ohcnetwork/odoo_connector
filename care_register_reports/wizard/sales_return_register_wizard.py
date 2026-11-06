from odoo import models


class SalesReturnRegisterWizard(models.TransientModel):
    _name = "care.sales.return.register.wizard"
    _inherit = ["care.sales.register.base"]
    _description = "Sales Return Register Wizard"

    _SHEET_NAME = "Sales Return Register"
    _FILE_PREFIX = "sales_return_register"

    def _move_types(self):
        return ["out_refund"]
