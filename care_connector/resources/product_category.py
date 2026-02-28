from odoo.http import request

class CategoryUtility:

    @classmethod
    def get_or_create_category(cls,user_env, category_data):
        """Retrieve or create product category"""
        try:
            product_category_model = user_env['product.category']
            category_name = category_data.category_name
            parent_x_care_id = category_data.parent_x_care_id
            x_care_id = category_data.x_care_id
            category = product_category_model.with_context(active_test=False).search([('x_care_id', '=', x_care_id)], limit=1)
            if not category:
                category = product_category_model.create({
                    'name': category_name,
                    'x_care_id': x_care_id
                })
            else:
                if category.name != category_name:
                    category.name = category_name

            if parent_x_care_id:
                parent_category = product_category_model.search([('x_care_id', '=', parent_x_care_id)], limit=1)
                if parent_category and category.parent_id.id != parent_category.id:
                    category.parent_id = parent_category.id

            return category

        except Exception as e:
            return {str(e)}