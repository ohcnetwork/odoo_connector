# Care monthly stock valuation

The authenticated `POST /api/stock/period` endpoint accepts monthly product
summaries from the Care plugin. Native Odoo 19 AVCO calculates the effective cost.
Each monthly report also saves Care location/batch/expiry detail for reporting.
There is one product cost across its locations and batches within a month.

Upgrade `care_connector` and configure the companion Care plugin. The service user
needs Inventory Administrator and vendor-bill access in the intended company.
Company record rules isolate ledgers, reports and report lines.

## Monthly flow

The first opening comes directly from Care's prior-day stock report, checked against
the approved financial total. No Excel import is required. Later months carry the
previous close. Do not separately import the same opening through stock adjustments.

Monthly requests supply `mode: monthly`, `period_key`, `facility_uuid`, `month`
(the first opening month) and `stock_month` (the month being processed).

| Action | Purpose |
| --- | --- |
| `bill_sources` | Read vendor-bill product lines linked to Care receipt/order IDs. |
| `prepare` | Create revision-specific base-unit AVCO products and one valuation location. |
| `events` | Post opening, monthly receipts, recoveries and outgoing summaries. |
| `report` | Read native quantities, average costs and values at a timestamp. |
| `close` | Verify events/quantities/bills and save a detailed monthly report. |
| `snapshot` | Return a saved monthly report. |
| `status` | Recover a committed close after a lost client response. |
| `current` | Identify the facility's published monthly series. |
| `publish` | Publish a complete replacement and retire/archive prior series. |

Products are separate from existing pack-based billing products. Monthly stock has
no native lots; report lines carry Care batch and location identities. Available
plus incoming internal transfers must equal owned quantity. The report dimensions
must reconcile with product quantities and native rounded product values.

Vendor-bill company-currency balances supply receipt value after discounts,
excluding GST. Quantities include free units. Purchases pool before recoveries and
issues. Unmatched Care-cost inputs remain flagged in Care's exceptions.

Preparation sets instance-wide Product Price precision to 12 decimals and Product
Unit precision to six. Native values round per product to the company currency.
New products' initial price history is dated before the opening for historical AVCO.

## Rebuild instead of locking

A source correction uses Care's `--rebuild --post` command. Care reuses the approved
financial opening, re-reads transactions and current bills, and rebuilds every month
through the latest processed month. New requests include `staged: true` and a new
period key. Products belong to their revision and remain inactive while building.

`publish` supplies `through_month` and `replaces_period_key` (null for the first
publication). It requires a complete consecutive series and checks that the current
revision has not changed. In one Odoo transaction, it retires prior native stock
balances with stock moves, deactivates old products, activates replacement products
and marks old series archived. Retrying a successful publication is harmless.
Failed earlier builds are retired at publication as well. Old issued snapshots
remain available; merely archiving report rows would double-count native stock.

There are no custom ORM freeze locks. Changed retries are rejected because event
keys identify a particular source payload. Correct the source and rebuild with a
new revision. Linked bill changes stop a following close with a rebuild instruction;
rebuilds also find newly posted bills for previously unmatched Care receipts.

The connector's current reports are the month-end reporting source. Generic queries
that include inactive products can see building or archived cost histories. Archived
products have zero current stock after publication. Source movement history remains
intact for comparison with older saved reports.

## Viewing and exporting

Open **Inventory > Reporting > Care Monthly Stock**. The default filter shows current
reports. Archived and building filters show earlier revisions and unfinished runs.
Open a month and choose **Batch and Location Report** for an exportable list of
product, location, batch, expiry, owned/available/incoming quantity, cost and value.

This is a monthly valuation mirror; Care remains the daily operational stock system.
Categories use periodic valuation. No opening or month-end general-ledger journal or
recurring schedule is created. Monthly boundaries use Asia/Kolkata.

Lower-level detailed batch/location replay remains available for audit tooling in a
separate ledger. The monthly workflow does not use it.

## Verification

```sh
odoo --database <test-database> --update care_connector --test-enable \
  --test-tags /care_connector --stop-after-init --no-http
```

Tests exercise native stock moves and posted bills, free quantities, discounts,
zero-cost receipts, historical AVCO, roll-forward, retry behavior and a two-month
replacement. Replacement checks include incomplete publication, preserved old
reports, detail totals, retirement of old stock and subsequent monthly preparation.
