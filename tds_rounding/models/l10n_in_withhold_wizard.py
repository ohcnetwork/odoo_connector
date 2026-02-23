from odoo import models, api

import logging
_logger = logging.getLogger(__name__)


class L10nInWithholdWizard(models.TransientModel):
    _inherit = 'l10n_in.withhold.wizard'

    @api.depends('tax_id', 'base')
    def _compute_amount(self):
        """Override to round TDS amount to nearest rupee.

        As per Section 288B of the Indian Income Tax Act, the TDS amount
        shall be rounded off to the nearest rupee — any fraction of a
        rupee equal to or exceeding 50 paise is rounded up, and any
        fraction less than 50 paise is ignored.
        """
        super()._compute_amount()
        for wizard in self:
            wizard.amount = round(wizard.amount)

    def action_create_and_post_withhold(self):
        """Override to force round the TDS amount before creating journal entries."""
        for wizard in self:
            if wizard.tax_id and wizard.base:
                taxes_res = wizard.tax_id.compute_all(
                    wizard.base,
                    currency=wizard.tax_id.company_id.currency_id,
                    quantity=1.0,
                    product=False,
                    partner=False,
                    is_refund=False,
                )
                raw_amount = abs(taxes_res['total_included'] - taxes_res['total_excluded'])
                wizard.amount = round(raw_amount)
        return super().action_create_and_post_withhold()
