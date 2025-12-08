# -*- coding: utf-8 -*-

from odoo import models, fields, api



class ProductCategory(models.Model):
    _inherit = 'product.category'

    use_different_taxes = fields.Boolean(string = "Different Taxes")

    subcategory_tax_config_ids = fields.One2many(
        'product.category.tax.config',
        'parent_category_id',
        string="Subcategory Tax Configuration",
        copy=False,store=True,
    )

    tax_id = fields.Many2one(
        'account.tax',
        string="Tax",
        domain=[('type_tax_use', '=', 'sale')]
    )
    factor = fields.Float(
        string="Factor",
    )



class ProductCategoryTaxConfig(models.Model):
    _name = 'product.category.tax.config'
    _description = 'Product Category Tax Configuration'
    _order = 'sequence, id'

    parent_category_id = fields.Many2one(
        'product.category',
        string="Parent Category",
        required=True,
        ondelete='cascade'
    )

    subcategory_id = fields.Many2one(
        'product.category',
        string="Subcategory",
        domain="[('id', 'child_of', parent_category_id), ('id', '!=', parent_category_id)]"
    )

    tax_id = fields.Many2one(
        'account.tax',
        string="Tax",
        domain=[('type_tax_use', '=', 'sale')]
    )

    factor = fields.Float(
        string="Factor",


    )

    sequence = fields.Integer(default=10)
