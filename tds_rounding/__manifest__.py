{
    "name": "Care: TDS Rounding",
    "summary": "Round TDS amounts to the nearest rupee as per Section 288B of the Income Tax Act",
    "description": """
        Rounds the TDS (Tax Deducted at Source) amount to the nearest rupee
        in the Indian withholding tax wizard.

        As per Section 288B of the Indian Income Tax Act, the TDS amount
        shall be rounded off to the nearest rupee — any fraction of a rupee
        equal to or exceeding 50 paise is rounded up, and any fraction less
        than 50 paise is ignored.
    """,
    "version": "19.0.1.0.0",
    "category": "Accounting",
    "author": "Care",
    "license": "LGPL-3",
    "depends": ["l10n_in"],
    "installable": True,
    "auto_install": False,
}
