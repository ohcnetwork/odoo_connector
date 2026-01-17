# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = "account.move"

    sponsor_company_id = fields.Many2one(
        "sponsor.company",
        string="Sponsor Company",
        tracking=True,
        domain="[('active', '=', True)]",
        help="Corporate sponsor who will pay this invoice instead of the customer",
    )
    is_sponsored = fields.Boolean(
        string="Is Sponsored",
        compute="_compute_is_sponsored",
        store=True,
    )

    @api.depends("sponsor_company_id")
    def _compute_is_sponsored(self):
        for move in self:
            move.is_sponsored = bool(move.sponsor_company_id)

    @api.onchange("sponsor_company_id")
    def _onchange_sponsor_company_id(self):
        """Update receivable lines to use sponsor's account when sponsor is set."""
        if self.sponsor_company_id and self.sponsor_company_id.account_id:
            self._update_receivable_to_sponsor()

    def _update_receivable_to_sponsor(self):
        """Update receivable account lines to use sponsor's account."""
        if not self.sponsor_company_id or not self.sponsor_company_id.account_id:
            return

        sponsor_account = self.sponsor_company_id.account_id
        for line in self.line_ids:
            if line.account_id.account_type == "asset_receivable":
                line.account_id = sponsor_account

    def action_post(self):
        """Ensure sponsor account is set on receivable lines before posting."""
        for move in self:
            if move.sponsor_company_id and move.sponsor_company_id.account_id:
                move._update_receivable_to_sponsor()
        return super().action_post()

    def write(self, vals):
        """Handle sponsor changes on existing invoices."""
        res = super().write(vals)
        if "sponsor_company_id" in vals:
            for move in self:
                if move.state == "draft" and move.sponsor_company_id:
                    move._update_receivable_to_sponsor()
        return res

