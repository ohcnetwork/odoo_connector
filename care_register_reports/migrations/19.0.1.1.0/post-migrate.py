from odoo import SUPERUSER_ID, api

from odoo.addons.care_register_reports.hooks import set_default_stock_accounts


def migrate(cr, version):
    set_default_stock_accounts(api.Environment(cr, SUPERUSER_ID, {}))
