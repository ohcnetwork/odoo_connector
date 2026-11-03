# Monthly purchase prices

`GET /api/purchases/monthly-prices?from_month=2026-04&to_month=2026-09`
returns purchase-only weighted averages for each Care item, pooled across its
batches, with a separate batch breakdown. `to_month` defaults to `from_month`;
request at most twelve consecutive months. Use the connector's Basic
authentication with an Odoo user who has vendor-bill access, including the
Accounting read-only role. Updating metadata requires bill-editing access. Optional
`company_id` selects one of that user's allowed companies; the default is the
user's default company. Company record rules and account-model permissions apply.

The endpoint reads current **posted vendor invoices**, grouped by **bill date**
(`invoice_date`). Draft/cancelled bills, vendor credit notes, sales, taxes and
cash-rounding lines do not contribute. Values are product-line balances in the
company currency, after the discounts and corrections recorded in Odoo.

For each bill line, the denominator is received quantity **including free packs**,
converted from the invoice UoM to the billing product UoM and then multiplied by
the Care pack size saved for that receipt. Free quantity is already included in
received quantity and is not added again. Manual bills with a blank/zero custom
received field use billed plus free quantity and report that inference as a flag.
Differences between received and billed-plus-free quantities, or between Odoo
and the original Care receipt, are also flagged for review.

```
item price = sum(batch net purchase values) / sum(batch received base units)
batch price = sum(batch net purchase values) / sum(batch received base units)
```

For example, batch A has 1,500 received tablets worth 9,000 and batch B has 1,000
received tablets worth 10,000. Their prices are 6 and 10; the combined item price
is **7.6**, not the arithmetic average of those two prices.

The response identifies the method, company, currency and date basis. Each month
contains control totals, `items` and `unmapped_lines`. Item rows include
`facility_uuid`, `care_item_uuid`, `item`, `base_unit`, `received_base_units`,
`free_base_units`, `net_purchase_value`, `weighted_average_price`, `flags` and
`batches`. Batch rows include **Care** `care_product_id`, `care_product_uuid`,
the batch text (preserving leading zeros), quantities/value, batch average,
source Odoo `bill_line_ids` and flags. Monetary amounts, quantities and prices
are decimal strings; zero-cost purchases return a price of `"0"`.

Missing mappings are listed with their bill/line/product IDs, Care receipt and
charge-definition UUIDs and purchase value. Their amounts remain in monthly
control totals but do not enter a guessed item average. Conflicting base units,
conflicting batch identities or invalid purchase quantities return a null average
for the affected item. `complete` is false when mappings or quantity/unit flags
need review. It describes the requested purchase data, not inventory valuation.

No purchases in a month means an empty item list. No previous/future price is
substituted. Each request re-reads bills; a later bill or corrected old bill changes
the relevant month's result. `Cache-Control: no-store` prevents stale API caching.
There are no new monthly locks or inventory postings. This rate does not include
opening stock, consumption or remaining inventory and is not inventory AVCO.

## Care item and batch mapping

Upgrade `care_connector` before updating the Care plugin. New Care vendor-bill
requests include optional `invoice_items[].care_purchase`: facility/item UUIDs,
item name, Care product integer ID and UUID, batch text, charge-definition UUID,
historical pack size, base unit and original received base quantity. This is saved
on the bill line. Existing integrations may omit it and remain compatible.
The charge-definition UUID must match the bill line's billing product. Changing
that product in Odoo makes the old mapping unusable until corrected.

For older bills, run the Care command first without `--post`, then with it:

```sh
python manage.py sync_odoo_purchase_metadata --facility <Care-facility-UUID>
python manage.py sync_odoo_purchase_metadata --facility <Care-facility-UUID> --post
```

The command sends receipt identities to `POST /api/purchases/metadata` in batches
of at most 500. The body is `{"entries": [{"care_line_uuid": "...",
"care_purchase": {...}}]}` with optional `company_id`. Only an unambiguous matching
vendor-bill line in that company receives metadata. Cancelled predecessors are
ignored. Missing/duplicate receipt links and changed billing products return
explicit statuses; no name-based batch matching occurs. Repeating a successful
backfill returns `unchanged`. The operation changes metadata only: posted bill
amounts, discounts, quantities, states and journal entries are preserved.

An Odoo line combining several Care receipts cannot establish their batch
allocation from one receipt UUID. Quantity mismatches stay flagged rather than
silently allocating the line's value across guessed batches. Unlinked legacy
lines require an explicit mapping/correction before full coverage is possible.
