from odoo.http import request
from .product_category import CategoryUtility


class ProductUtility:

    @classmethod
    def get_or_create_product(cls, user_env, product_data):
        """Retrieve or create product, handle archive/unarchive logic"""
        try:
            product_product_model = user_env['product.product']
            product = product_product_model.with_context(active_test=False).search([('x_care_id', '=', product_data.x_care_id)], limit=1)
            category_data = product_data.category
            tax_list = product_data.taxes
            status = product_data.status.value if product_data.status else None
            category = CategoryUtility.get_or_create_category(user_env, category_data)
                
            categ_id = category.id if category else None

            taxes_ids = None
            if tax_list:
                taxes_ids = cls._get_or_create_taxes(user_env, tax_list)
    
            product_vals = {
                'name': product_data.product_name if product_data.product_name else 'New Product',
                'x_care_id': product_data.x_care_id,
                'list_price': product_data.mrp or 0.0,
                'standard_price': product_data.cost or 0.0,
                'categ_id': categ_id,
                'l10n_in_hsn_code': product_data.hsn,
            }

            if taxes_ids:
                product_vals.update({
                    'taxes_id': [(6, 0, taxes_ids['sale_tax'])],
                    'supplier_taxes_id': [(6, 0, taxes_ids['purchase_tax'])],
                })

            if not product:
                product = product_product_model.create(product_vals)
            else:
                product.write(product_vals)

            if product.product_tmpl_id and status:
                if status == 'retired' and product.product_tmpl_id.active:
                    product.product_tmpl_id.active = False
                elif status in ['draft', 'active'] and not product.product_tmpl_id.active:
                    product.product_tmpl_id.active = True

            return product

        except Exception as e:
            raise Exception(f"{str(e)}")

    @classmethod
    def _get_or_create_taxes(cls, user_env, tax_list):
        try:
            account_tax_model = user_env['account.tax']
            sale_tax_ids = []
            purchase_tax_ids = []
            for tax_data in tax_list:
                tax_name = f"{tax_data.tax_name} ({tax_data.tax_percentage}%)"
                for tax_type in ['sale', 'purchase']:
                    name = f"{tax_name} - {tax_type.capitalize()}"
                    existing_tax = account_tax_model.search([
                        ('name', '=', name),
                        ('amount', '=', tax_data.tax_percentage),
                        ('type_tax_use', '=', tax_type)
                    ], limit=1)
                    if not existing_tax:
                        existing_tax = account_tax_model.create({
                            'name': name,
                            'amount': tax_data.tax_percentage,
                            'type_tax_use': tax_type,
                        })

                    if tax_type == 'sale':
                        sale_tax_ids.append(existing_tax.id)
                    else:
                        purchase_tax_ids.append(existing_tax.id)

            return {
                "purchase_tax": purchase_tax_ids,
                "sale_tax": sale_tax_ids,
            }

        except Exception as e:
            raise Exception(f"{str(e)}")