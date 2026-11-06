# Accounts the hospital's stock sales post to, by code. They only seed the setting;
# accountants change the list in Accounting settings afterwards.
STOCK_SALES_ACCOUNT_CODES = ["514.10973", "514.10972", "514.10970", "517.11005"]


def set_default_stock_accounts(env):
    Account = env["account.account"]
    for company in env["res.company"].search([]):
        if not company.care_stock_sales_account_ids:
            company.care_stock_sales_account_ids = Account.with_company(company).search(
                [("company_ids", "in", company.id), ("code", "in", STOCK_SALES_ACCOUNT_CODES)]
            )


def post_init_hook(env):
    set_default_stock_accounts(env)
