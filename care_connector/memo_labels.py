# Part of care_connector. Maps Care Connector journal/payment codes to memo labels.

# Memo suffix labels are UPPERCASE, e.g. "INV/25-26/0008, CARD #2222", "…, BANK #435690"
CARE_REFERENCE_LABELS = {
    "card": "CARD",
    "debit": "DEBIT",
    "cash": "CASH",
    "bank": "BANK",
    "credit": "CREDIT",
}


def format_care_reference_memo(label: str, reference: str) -> str:
    """Build ``LABEL #reference`` (e.g. ``CARD #2222``, ``BANK #435690``)."""
    return f"{label} #{reference.strip()}"


def care_reference_label(*, journal_input=None, journal=None, payment_method_line=None):
    """
    Uppercase label for the payment line in memo (CARD, DEBIT, BANK, CASH, CREDIT, …).

    :param journal_input: API/UI string (card, debit, cash, bank, neft, credit, …)
    :param journal: account.journal
    :param payment_method_line: account.payment.method.line
    """
    if journal_input is not None and str(journal_input).strip():
        key = str(journal_input).lower().strip()
        return CARE_REFERENCE_LABELS.get(key, key.replace("_", " ").upper())
    if payment_method_line and payment_method_line.x_care_payment_code:
        code = payment_method_line.x_care_payment_code
        return CARE_REFERENCE_LABELS.get(code, code.upper())
    if journal and journal.x_care_journal_code:
        code = journal.x_care_journal_code
        return CARE_REFERENCE_LABELS.get(code, code.upper())
    if journal:
        if journal.type == "cash":
            return "CASH"
        if journal.type == "bank":
            return "BANK"
    return "REF"
