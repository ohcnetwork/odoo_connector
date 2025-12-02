
class ChartOfAccountUtility:

    @classmethod
    def get_all_account_account(cls,user_env):
        try:
            account_list = []
            account_account_model = user_env["account.account"]
            accounts = account_account_model.search([])

            for acc in accounts:
                account_list.append({
                    "id": acc.id,
                    "name": acc.name,
                    "code": acc.code,
                    "display_name": f"{acc.code} - {acc.name}"
                })

            return account_list

        except Exception as e:
            raise Exception(f"{str(e)}")


    @classmethod
    def get_account_account_by_id(cls, user_env,id):
        try:
            account_account_model = user_env["account.account"]
            account = account_account_model.search([
                    ("id", "=", int(id))
                ], limit=1)

            return account
        except Exception as e:
            raise Exception(f"{str(e)}")

    @classmethod
    def get_accounts_by_name(cls, user_env, request_data):
        try:
            accounts_list = []
            search_key = request_data.search_key
            account_account_model = user_env["account.account"]

            accounts = account_account_model.search([
                ('name', '=ilike', f"{search_key}%")
            ], order="name asc")

            for acc in accounts:
                accounts_list.append({
                    "id": acc.id,
                    "name": acc.name,
                    "code": acc.code,
                })
            return accounts_list
        except Exception as e:
            raise Exception(f"{str(e)}")