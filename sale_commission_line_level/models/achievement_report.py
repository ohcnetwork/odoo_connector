# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class SaleAchievementReport(models.Model):
    _inherit = "sale.commission.achievement.report"

    @api.model
    def _join_invoices(self, join_type=None):
        """Override to support line-level commission_user_id.
        
        For user-type commission, we can't use invoice_user_id in JOIN
        because we need to check line-level commission_user_id.
        """
        if join_type == 'team':
            jointure = "fm.team_id = rules.team_id"
        else:
            # For user commission, don't filter in JOIN - let WHERE clause handle it
            jointure = "1=1"
        return f"""
          JOIN filtered_moves fm ON {jointure}
          JOIN account_move_line aml
            ON aml.move_id = fm.id
          LEFT JOIN product_product pp
            ON aml.product_id = pp.id
          LEFT JOIN product_template pt
            ON pp.product_tmpl_id = pt.id
        """

    @api.model
    def _select_invoices_line_level(self):
        """Select statement for line-level commission calculation.
        
        Uses COALESCE to pick line-level commission_user_id first,
        then falls back to invoice-level invoice_user_id.
        """
        return f"""
          COALESCE(aml.commission_user_id, fm.invoice_user_id) AS user_id,
          MAX(fm.team_id) AS team_id,
          rules.plan_id,
          SUM({self._get_invoice_rates_product()}) AS achieved,
          MAX(fm.currency_id) AS currency_id,
          MAX(fm.date) AS date,
          MAX(rules.company_id) AS plan_company_id,
          MAX(fm.company_id) AS achievement_company_id,
          aml.id AS related_res_id,
          MAX(fm.partner_id) AS partner_id,
          MAX(fm.write_date) AS entropy_date
        """

    def _invoices_lines(self, users=None, teams=None):
        """Override to support line-level commission salesperson.
        
        Key changes for Odoo 19:
        - Includes filtered_moves CTE at the start (required by Odoo 19)
        - Uses fm (filtered_moves) alias instead of am (account_move)
        - Uses COALESCE(aml.commission_user_id, fm.invoice_user_id) to determine
          the salesperson for each line
        - Groups by aml.id (line level) instead of fm.id (invoice level)
        - Allows multiple salespeople to earn commission on the same invoice
        """
        return f"""
{self._get_filtered_moves_cte(users=users, teams=teams)},
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
        scp.currency_id AS currency_id,
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
         {self._join_invoices(join_type='team')}
    WHERE {self._where_invoices()}
      AND rules.team_rule
      AND fm.team_id = rules.team_id
    {'AND fm.team_id in (%s)' % ','.join(str(i) for i in teams.ids) if teams else ''}
      AND fm.date BETWEEN rules.date_from AND rules.date_to
      AND (rules.product_id IS NULL OR rules.product_id = aml.product_id)
      AND (rules.product_categ_id IS NULL OR rules.product_categ_id = pt.categ_id)
    GROUP BY
        fm.id,
        rules.plan_id,
        rules.user_id
), invoice_commission_lines_user AS (
    -- LINE LEVEL: Uses commission_user_id from line, falls back to invoice_user_id
    SELECT
        {self._select_invoices_line_level()}
    FROM invoices_rules rules
         {self._join_invoices(join_type='user')}
    WHERE {self._where_invoices()}
      AND NOT rules.team_rule
      -- Match line-level salesperson OR invoice-level salesperson to plan user
      AND COALESCE(aml.commission_user_id, fm.invoice_user_id) = rules.user_id
    {'AND COALESCE(aml.commission_user_id, fm.invoice_user_id) in (%s)' % ','.join(str(i) for i in users.ids) if users else ''}
      AND fm.date BETWEEN rules.date_from AND rules.date_to
      AND (rules.product_id IS NULL OR rules.product_id = aml.product_id)
      AND (rules.product_categ_id IS NULL OR rules.product_categ_id = pt.categ_id)
    GROUP BY
        aml.id,
        rules.plan_id,
        COALESCE(aml.commission_user_id, fm.invoice_user_id)
), invoice_commission_lines AS (
    (SELECT *, 'account.move' AS related_res_model FROM invoice_commission_lines_team)
    UNION ALL
    (SELECT *, 'account.move.line' AS related_res_model FROM invoice_commission_lines_user)
)""", 'invoice_commission_lines'
