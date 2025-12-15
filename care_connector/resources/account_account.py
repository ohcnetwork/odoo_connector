
class ChartOfAccountUtility:

    @classmethod
    def get_all_account_payment_method(cls,user_env):
        try:
            account_payment_method_list = []
            account_payment_method_line_model = user_env["account.payment.method.line"]
            account_payment_method_lines = account_payment_method_line_model.search([])

            for line in account_payment_method_lines:
                account_payment_method_list.append({
                    "id": line.id,
                    "name": line.name,
                    "code": line.code,
                    "payment_method": line.payment_method_id.name,
                    "journal_id": line.journal_id.id,
                    "journal_name": line.journal_id.name
                })
            return account_payment_method_list

        except Exception as e:
            raise Exception(f"{str(e)}")


    @classmethod
    def get_account_payment_method_by_id(cls, user_env,id):
        try:
            account_payment_method_line_model = user_env["account.payment.method.line"]
            payment_method_line = account_payment_method_line_model.search([
                    ("id", "=", int(id))
                ], limit=1)

            return payment_method_line
        except Exception as e:
            raise Exception(f"{str(e)}")



    @classmethod
    def get_account_payment_method_by_name(cls, user_env, request_data):
        try:
            payment_method_list = []
            search_key = request_data.search_key
            account_payment_method_line_model = user_env["account.payment.method.line"]

            payment_method_line = account_payment_method_line_model.search([
                ('name', '=ilike', f"{search_key}%")
            ], order="name asc")

            for acc in payment_method_line:
                payment_method_list.append({
                    "id": acc.id,
                    "name": acc.name,
                    "code": acc.code,
                })
            return payment_method_list
        except Exception as e:
            raise Exception(f"{str(e)}")