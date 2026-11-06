from odoo import fields, models


class SalesRegisterWizard(models.TransientModel):
    _name = "care.sales.register.wizard"
    _inherit = ["care.sales.register.base"]
    _description = "Sales Register Wizard"

    include_refunds = fields.Boolean(
        string="Include Credit Notes",
        help="Include customer credit notes (refunds) in the export.",
    )

    _SHEET_NAME = "Sales Register"
    _FILE_PREFIX = "sales_register"

    def _move_types(self):
        move_types = ["out_invoice", "out_receipt"]
        if self.include_refunds:
            move_types.append("out_refund")
        return move_types
