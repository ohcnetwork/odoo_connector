# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class SaleAchievementReport(models.Model):
    _inherit = "sale.commission.achievement.report"

    @api.model
    def _select_invoices_line_level(self):
        """Select statement for line-level commission calculation.
        
        Uses COALESCE to pick line-level commission_user_id first,
        then falls back to invoice-level invoice_user_id.
        """
        return f"""
          COALESCE(aml.commission_user_id, am.invoice_user_id) AS user_id,
          MAX(am.team_id),
          rules.plan_id,
          SUM({self._get_invoice_rates_product()}) AS achieved,
          MAX(rules.currency_id),
          MAX(am.date) AS date,
          MAX(rules.company_id),
          aml.id AS related_res_id
        """

    def _invoices_lines(self, users=None, teams=None):
        """Override to support line-level commission salesperson.
        
        Key changes:
        - Uses COALESCE(aml.commission_user_id, am.invoice_user_id) to determine
          the salesperson for each line
        - Groups by aml.id (line level) instead of am.id (invoice level)
        - Allows multiple salespeople to earn commission on the same invoice
        """
        return f"""
invoices_rules AS (
    SELECT
        COALESCE(scpu.date_from, scp.date_from) AS date_from,
        COALESCE(scpu.date_to, scp.date_to) AS date_to,
        scpu.user_id AS user_id,
        scp.team_id AS team_id,
        scp.id AS plan_id,
        scpa.product_id,
        scpa.product_categ_id,
        scp.company_id,
        scp.currency_id,
        scp.user_type = 'team' AS team_rule,
        {self._rate_to_case(self._get_invoices_rates())}
        {self._select_rules()}
    FROM sale_commission_plan_achievement scpa
    JOIN sale_commission_plan scp ON scp.id = scpa.plan_id
    JOIN sale_commission_plan_user scpu ON scpa.plan_id = scpu.plan_id
    WHERE scp.active
      AND scp.state = 'approved'
      AND scpa.type IN ({','.join("'%s'" % r for r in self._get_invoices_rates())})
    {'AND scpu.user_id in (%s)' % ','.join(str(i) for i in users.ids) if users else ''}
), invoice_commission_lines_team AS (
    SELECT
        {self._select_invoices()}
    FROM invoices_rules rules
         {self._join_invoices()}
    WHERE {self._where_invoices()}
      AND rules.team_rule
      AND am.team_id = rules.team_id
    {'AND am.team_id in (%s)' % ','.join(str(i) for i in teams.ids) if teams else ''}
      AND am.date BETWEEN rules.date_from AND rules.date_to
      AND (rules.product_id IS NULL OR rules.product_id = aml.product_id)
      AND (rules.product_categ_id IS NULL OR rules.product_categ_id = pt.categ_id)
    GROUP BY
        am.id,
        rules.plan_id,
        rules.user_id
), invoice_commission_lines_user AS (
    -- LINE LEVEL: Uses commission_user_id from line, falls back to invoice_user_id
    SELECT
        {self._select_invoices_line_level()}
    FROM invoices_rules rules
         {self._join_invoices()}
    WHERE {self._where_invoices()}
      AND NOT rules.team_rule
      -- Match line-level salesperson OR invoice-level salesperson to plan user
      AND COALESCE(aml.commission_user_id, am.invoice_user_id) = rules.user_id
    {'AND COALESCE(aml.commission_user_id, am.invoice_user_id) in (%s)' % ','.join(str(i) for i in users.ids) if users else ''}
      AND am.date BETWEEN rules.date_from AND rules.date_to
      AND (rules.product_id IS NULL OR rules.product_id = aml.product_id)
      AND (rules.product_categ_id IS NULL OR rules.product_categ_id = pt.categ_id)
    GROUP BY
        aml.id,
        rules.plan_id,
        COALESCE(aml.commission_user_id, am.invoice_user_id)
), invoice_commission_lines AS (
    (SELECT *, 'account.move' AS related_res_model FROM invoice_commission_lines_team)
    UNION ALL
    (SELECT *, 'account.move.line' AS related_res_model FROM invoice_commission_lines_user)
)""", 'invoice_commission_lines'
