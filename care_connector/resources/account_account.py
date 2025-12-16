
class ChartOfAccountUtility:

    @classmethod
    def get_payment_method_by_id(cls, user_env, id):
        try:
            payment_method_list = []
            account_payment_method_line_model = user_env["account.payment.method.line"]
            payment_method_line = account_payment_method_line_model.search([
                ("id", "=", int(id))
            ], limit=1)
            if payment_method_line:
                payment_method_list.append({
                    "id": payment_method_line.id,
                    "name": payment_method_line.name,
                    "code": payment_method_line.code,
                    "payment_method": payment_method_line.payment_method_id.name,
                    "journal_id": payment_method_line.journal_id.id,
                    "journal_name": payment_method_line.journal_id.name
                })
            return payment_method_list
        except Exception as e:
            raise Exception(f"{str(e)}")

    @classmethod
    def get_account_payment_method_by_name(cls, user_env, request_data):
        try:
            payment_method_list = []
            search_key = (request_data.search_key or "").strip()

            account_payment_method_line_model = user_env["account.payment.method.line"]

            domain = []
            if search_key:
                domain = [('name', '=ilike', f"{search_key}%")]

            payment_method_lines = account_payment_method_line_model.search(
                domain,
                order="name asc"
            )

            for line in payment_method_lines:
                payment_method_list.append({
                    "id": line.id,
                    "name": line.name,
                    "code": line.code,
                    "payment_method": line.payment_method_id.name,
                    "journal_id": line.journal_id.id,
                    "journal_name": line.journal_id.name
                })

            return payment_method_list

        except Exception as e:
            raise Exception(str(e))