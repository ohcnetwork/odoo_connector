# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields


class SaleAchievementReport(models.Model):
    _inherit = "sale.commission.achievement.report"

    # New field to show the original line/invoice amount
    line_amount = fields.Monetary(
        "Line Amount", 
        readonly=True, 
        currency_field='currency_id',
        help="Original invoice line amount (price_subtotal) before commission calculation"
    )
    product_id = fields.Many2one(
        'product.product',
        "Product",
        readonly=True,
        help="Product from the invoice line"
    )

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
        Also includes line_amount to show the original invoice line amount.
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
          SUM(CASE 
              WHEN fm.move_type = 'out_invoice' THEN aml.price_subtotal / fm.invoice_currency_rate
              WHEN fm.move_type = 'out_refund' THEN -aml.price_subtotal / fm.invoice_currency_rate
              ELSE 0
          END) AS line_amount,
          MAX(aml.product_id) AS product_id
        """
    
    @api.model
    def _select_invoices(self):
        """Override to include line_amount for invoice-level (team) commission."""
        return f"""
          rules.user_id AS user_id,
          MAX(fm.team_id) AS team_id,
          rules.plan_id,
          SUM({self._get_invoice_rates_product()}) AS achieved,
          MAX(fm.currency_id) AS currency_id,
          MAX(fm.date) AS date,
          MAX(rules.company_id) AS plan_company_id,
          MAX(fm.company_id) AS achievement_company_id,
          fm.id AS related_res_id,
          MAX(fm.partner_id) AS partner_id,
          SUM(CASE 
              WHEN fm.move_type = 'out_invoice' THEN aml.price_subtotal / fm.invoice_currency_rate
              WHEN fm.move_type = 'out_refund' THEN -aml.price_subtotal / fm.invoice_currency_rate
              ELSE 0
          END) AS line_amount,
          NULL::integer AS product_id
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
        # Filter the effective line salesperson below, not the invoice header.
        return f"""
{self._get_filtered_moves_cte(users=None, teams=teams)},
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

    def _with_adjustment_columns(self, query, table_name):
        """Normalize upstream rows without depending on their IDs or column order."""
        extended_table = f"{table_name}_line_level"
        return f"""
{query},
{extended_table} AS (
    SELECT user_id,
           team_id,
           plan_id,
           achieved,
           currency_id,
           date,
           plan_company_id,
           achievement_company_id,
           related_res_id,
           partner_id,
           0::numeric AS line_amount,
           NULL::integer AS product_id,
           related_res_model
      FROM {table_name}
)
""", extended_table

    def _achievement_lines_add(self, users=None, teams=None):
        return self._with_adjustment_columns(
            *super()._achievement_lines_add(users, teams)
        )

    def _achievement_lines_rem(self, users=None, teams=None):
        return self._with_adjustment_columns(
            *super()._achievement_lines_rem(users, teams)
        )

    @api.model
    def _select_sales(self):
        """Override to add line_amount and product_id columns for sales.
        
        This adds the line amount (sum of sale order line subtotals) to
        the inner CTEs where sol and fo tables are accessible.
        """
        return f"""
          {super()._select_sales()},
          MAX(fo.team_id) AS line_level_team_id,
          SUM(sol.price_subtotal / fo.currency_rate) AS line_amount,
          NULL::integer AS product_id
        """

    def _sale_lines(self, users=None, teams=None):
        query, _table_name = super()._sale_lines(users, teams)
        # Newer Odoo builds explicitly project the final sales CTE, dropping
        # extension columns. Normalize the inner rows where our fields exist.
        projections = []
        for source in ("sale_commission_lines_team", "sale_commission_lines_user"):
            projections.append(f"""
                SELECT user_id,
                       line_level_team_id AS team_id,
                       plan_id,
                       achieved,
                       currency_id,
                       date,
                       plan_company_id,
                       achievement_company_id,
                       related_res_id,
                       partner_id,
                       line_amount,
                       product_id,
                       'sale.order'::text AS related_res_model
                  FROM {source}
            """)
        return f"""
{query},
sale_commission_lines_line_level AS (
    {' UNION ALL '.join(projections)}
)
""", 'sale_commission_lines_line_level'

    def _get_report_view(self, users=None, teams=None):
        """Override to include line_amount and product_id in the report view."""
        # Check if view already exists
        self.env.cr.execute("""
            SELECT 1 FROM pg_catalog.pg_class AS c
                WHERE c.relname = 'sale_commission_achievement_report_view'
                AND c.relkind = 'v'::"char"
                AND pg_catalog.pg_table_is_visible(c.oid)
        """)
        res = self.env.cr.fetchone()
        if res:
            return
        
        # The view is reused by queries with different user/team contexts.
        # Build it unfiltered and let the parent table query apply those filters.
        query = f"""
            CREATE {self._get_view_parameters()} VIEW sale_commission_achievement_report_view AS
              WITH {self._commission_lines_query(users=None, teams=None)}
            SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY cl.plan_id, cl.related_res_model,
                                 cl.related_res_id, cl.user_id, era.id, cl.achieved
                    ) AS id,
                    era.id AS target_id,
                    cl.user_id AS user_id,
                    cl.team_id AS team_id,
                    cl.achieved AS achieved,
                    cl.currency_id AS currency_id,
                    cl.plan_company_id AS plan_company_id,
                    cl.achievement_company_id as achievement_company_id,
                    cl.plan_id,
                    cl.related_res_model,
                    cl.related_res_id::INTEGER AS related_res_id,
                    cl.date::date AS date,
                    cl.partner_id::INTEGER AS partner_id,
                    COALESCE(cl.line_amount, 0) AS line_amount,
                    cl.product_id::INTEGER AS product_id
              FROM commission_lines cl
              JOIN sale_commission_plan_target era
                ON cl.plan_id = era.plan_id
               AND cl.date::date >= era.date_from
               AND cl.date::date <= era.date_to;
            {self._view_post_creation()}
        """
        return query

    @property
    def _table_query(self):
        """Keep upstream filtering and currency conversion for standard fields."""
        query = super()._table_query
        return f"""
        WITH {self._get_currency_rate()}
        SELECT report_rows.*,
               cl.line_amount * cr.rate AS line_amount,
               cl.product_id
          FROM ({query}) report_rows
          JOIN sale_commission_achievement_report_view cl ON cl.id = report_rows.id
          JOIN currency_rate cr ON cr.company_id = cl.achievement_company_id
        """
