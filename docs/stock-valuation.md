# Care monthly stock valuation

The authenticated `POST /api/stock/period` endpoint accepts monthly summaries from
the companion Care plugin. Odoo 19's native AVCO calculates costs and values. Care
retains operational quantities and batch/location transaction evidence.

The add-on depends on `stock_account`. Upgrade `care_connector` after installing
this change. Use a service user with Inventory Administrator and vendor-bill
permissions in the intended company. Configure the matching connection in Care.

## Opening and month-end flow

The first approved opening is imported from Excel through the Care command. Care
validates the expected total, freezes the source and submits opening quantities
and allocated values once. Later months carry the previous issued close. Do not
import the same opening separately through Odoo inventory adjustments.

For `mode: monthly`, the request supplies `period_key`, `facility_uuid`, `month`
(the first opening month) and `stock_month` (the month being processed):

| Action | Purpose |
| --- | --- |
| `bill_sources` | Read final vendor-bill product lines linked to Care receipt/order IDs. |
| `prepare` | Create base-unit AVCO products and one valuation location per facility. |
| `events` | Post opening, monthly receipts, recoveries and outgoing summaries. |
| `report` | Read native quantities, average costs and values at a supplied timestamp. |
| `close` | Verify completed events and Care quantities, then freeze the native result. |
| `snapshot` | Return an issued month unchanged. |
| `status` | Recover an already committed close after a lost client response. |

Monthly products have no lots and are separate from existing pack-based billing
products. For `quantity_basis: owned`, Care supplies available and in-transit
quantities; their sum must equal native owned quantity for every item. Internal
Care transfers do not reduce the hospital's owned stock.

Posted vendor-bill balances supply receipt value after discounts, excluding GST.
Physical quantities include free units. Purchases pool before recoveries and
outgoing stock. Unmatched Care-cost inputs carry their source evidence; review
them in Care's exception export. Native negative-stock handling remains visible.

The first preparation changes Product Price precision to 12 decimals and Product
Unit precision to six. These are instance-wide Odoo settings. Monetary results
remain rounded per product to the company currency. The initial price history of
new integration products is dated before the opening to support historical AVCO.

## Frozen results and retries

Months close consecutively. Facility locks, event keys and payload hashes prevent
duplicate stock on retries. Changed retries and overallocated bill lines are
rejected. Closed Care stock moves, move lines and snapshots cannot be changed or
deleted through the ORM. Company record rules isolate ledgers and snapshots.

A close verifies its recorded events, all Care closing quantities and original
linked bill values. Linked bill changes stop a later close for review. Existing
issued snapshots remain unchanged. Automatic forward financial adjustments and
newly added bills for previously unmatched receipts require a separate workflow.

Categories use periodic valuation. The endpoint does not create an opening or
month-end general-ledger journal or enable a scheduler. Dates use Asia/Kolkata for
monthly boundaries. This is a monthly valuation mirror; Care provides daily stock.

The lower-level `prepare`, `events`, `bill_sources` and `report` actions also
support detailed batch/location replay for audit tooling. It must use a separate
facility ledger from a monthly opening, so the same opening cannot be imported twice.

## Verification

Run native Odoo post-install tests against a disposable configured database:

```sh
odoo --database <test-database> --update care_connector --test-enable \
  --test-tags /care_connector --stop-after-init --no-http
```

Tests exercise actual native stock moves and posted bills: free units, discounts,
zero-cost receipts, historical AVCO, monthly roll-forward, incoming stock splits,
retries, consecutive closes and frozen snapshots.
