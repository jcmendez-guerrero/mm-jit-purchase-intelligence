# Mundo Mascotix Intelligence — Architecture Review & Implementation Plan

**Status:** Implemented (Phases 1–9 complete) · **Revision:** 3 (2026-11-05) · **Baseline:** Architecture Specification v1.0 + Siweb360/Sygna OpenAPI **v1.2.0** (revised 2026-11-03)

> **Public repository.** This file contains no personal data, credentials, internal resource names, network ranges, tenant/app IDs or security-posture details. Those live in the internal wiki.

---

## 0. Decisions log

| Date | Decision | Consequence |
|---|---|---|
| 2026-11-04 | **Demand comes from stock movements, not tickets** | Tickets are not synced. `sale_shipment` (minus `return_customer`) is the demand signal |
| 2026-11-04 | **Siweb issues a single API token per company with full scope**, shared by all Mundo Mascotix apps | Read-only must be enforced on our side (ADR-006). Rate limit and rotation are shared with the other app (ADR-005) |
| 2026-11-04 | **IaC: Bicep for now, Terraform preferred later** | ADR-002 accepted as "Bicep, Terraform-ready" (see §6). Deviation from spec §2 recorded |
| 2026-11-04 | **Public repository kept** | Repo hygiene rules in §3.4 are mandatory |
| 2026-11-04 | **EUR 120/month covers all Mundo Mascotix workloads**, including the existing app | Reuse shared platform resources; MMI's own spend is what is left after the existing app (ADR-003/004, §5 cost rules) |
| 2026-11-04 | **Loss reasons:** before a cutover about mid-September 2026, the loss reason was not recorded on negative adjustments. After the cutover, an empty reason means staff did not enter one. Staff can now use `expiry`, `damage` and `theft` | **Reason cutover date** (configurable; default 2026-09-19, to be confirmed) splits history (ADR-012) |
| 2026-11-04 | **Grooming supplies are ordered on demand and never enter stock** | Out of MMI scope: no grooming series, no replenishment. `sale_shipment` from any warehouse = customer demand |
| 2026-11-04 | **One narrow Siweb write is allowed: supplier cost.** When the buyer enters a missing cost or confirms an order at a different cost, the system updates the supplier cost in Siweb. Siweb stores cost **including recargo de equivalencia** (1.4 % on 10 % VAT products, 5.2 % on 21 % VAT products); buyer-entered net costs get the recargo added. Constitution v1.1.0 | ADR-006 amended: read-only everywhere except this one operation, with a separate writer identity, buyer review, audit and visible retries. Product-level write only (Siweb has no per-variant supplier cost) |
| 2026-11-05 | **MMI 002 configuration ownership** (proposed, ADR-018) | Procurement owns terms, policies and scenarios; forecast owns seed datasets and parameters; inventory owns demand rules and aggregates; the BFF owns only durable roles in its own `bff` schema |
| 2026-11-05 | **Precedence between ERP facts, local overrides and estimates** (proposed, ADR-019) | Per field: ERP facts from the ERP; the most specific approved local value for MMI-owned terms; estimates only as a labelled fallback; conflicts shown, never silent |
| 2026-11-05 | **Predictive seed datasets are never ERP movements** (proposed, ADR-020) | Versioned, origin-flagged, atomically activated and reversible; hardened upload; private container with retention |
| 2026-11-05 | **Stock is valued at lot acquisition cost; the ERP cost update is the median of lot costs** (owner decision, constitution v1.2.0 pending review) | ERP movements carry PVP, not cost, and the ERP holds one cost per supplier. Margin check blocks below 15% unless an admin overrides; the releaser must differ from the override setter |

---

## 1. Executive summary

1. **Movements endpoints are now documented** (`GET /inventory/movements`, `GET /inventory/variants/{id}/movements`, paged, `limit` ≤ 200, 15 documented reasons). This unblocks the demand design. What remains is checking real responses: history depth, timezone and which sales actually create movements.
2. **Supplier costs are partly available in Siweb.** `GET /inventory/products/{id}/suppliers` returns purchase cost, lead time, minimum order and the preferred supplier **per product** (not per variant). It has no price-validity timestamp, no pack size and no discounts. Procurement imports it as one cost source with provenance, not as a guaranteed current offer.
3. **The token is full-scope and shared.** It can adjust stock, transfer, delete purchases/invoices and now also change prices and supplier costs (`PUT /variants/{id}/pricing`, `PUT /products/{id}/suppliers/{contact_id}`). Our connector must make writes structurally impossible.
4. **The rate limit is 1,000 requests/hour, shared across apps.** The sync design must fit a fixed per-app share of that budget.
5. **Budget is tight.** EUR 120/month covers everything, so MMI must reuse the existing database server, container environment, registry, key vault and monitoring rather than create new ones.

---

## 2. Siweb360 API — confirmed vs assumed (OpenAPI v1.2.0)

"Documented" = present in the OpenAPI v1.2.0, whose schemas are **inferred from published examples**. Nothing below has been checked against a live response yet.

| # | Capability | Status | Note |
|---|---|---|---|
| 1 | Base URL `https://app.siweb360.com` (alias `https://sygna.es`), prefix `/api/public`, Bearer auth, envelope `{success,data}` | **Documented** | Allowlist **only** `app.siweb360.com` |
| 2 | Rate limit 1,000 req/hour | **Documented (text only)** | No `429`, `Retry-After` or rate headers documented. Shared by every app using the token |
| 3 | Token scopes | **Confirmed by business: single full-scope token** | — |
| 4 | Token lifetime / rotation | **Unknown** | Text mentions "signed JWT with expiry" |
| 5 | `GET /inventory/products` (active only), `/variants` (stock totals, `reorder_point`, `price_cents`), `/warehouses`, `/stock/low` | **Documented** | Products endpoint omits inactive → tombstoning needed |
| 6 | `GET /variants/{id}/stock` (per warehouse/location/batch/expiry), `/variants/{id}/lots` | **Documented** | Per-variant calls; expensive under the quota |
| 7 | **`GET /inventory/movements`** — filters `variant_id, warehouse_id, reason, reference_type, reference_id, date_from, date_to`; `page`, `limit` ≤ 200; newest first | **Documented** | Newest-first paging can shift while new rows arrive → freeze `date_to` at run start and dedupe by `id` |
| 8 | Movement fields: `id, created_at, variant_id, sku, product_id, warehouse_id, location_id, quantity (signed), movement_type, reason, reference_type, reference_id, reference_number, batch_number, expiry_date, unit_cost_cents, notes` | **Documented** | `unit_cost_cents` can be fractional → Decimal |
| 9 | Reason enum: `purchase_receipt, sale_shipment, adjustment_positive, adjustment_negative, transfer_out, transfer_in, production_consumption, production_output, return_customer, return_supplier, damage, theft, expiry, count_adjustment, initial_stock` | **Documented** | Basis of the demand mapping (ADR-012) |
| 10 | `created_at` timezone | **Partly verified** | The UI export shows local business hours (08–19 h, Mon–Sat), so the UI shows local time. The API example has **no offset**. Still to check: match one movement between API and UI |
| 11 | `reference_type` values / POS sales → `sale_shipment` | **Very likely (UI export)** | Almost all sale movements reference a ticket-numbered document (`SERIES-YYYY-NNNNNN`) with a "Venta" note. Confirm the API `reference_type` value for tickets in the spike |
| 12 | Movement history depth | **Unknown** | The export covers one month only; the API backfill will show the real depth |
| 13 | `GET /inventory/products/{id}/suppliers` — `contact_id, supplier_name, supplier_cif, supplier_reference, purchase_cost_cents, currency, lead_time_days, min_order_qty, is_preferred` | **Documented** | Per product, not per variant. No `updated_at`, no pack size, no discounts. `supplier_cif` may identify a natural person → do not store |
| 14 | Writes reachable with the token: stock adjustments/transfers/infinite, `PUT` pricing, `PUT` supplier cost, `POST/PUT/DELETE` purchases, invoices, tickets, contacts… | **Documented** | All blocked by ADR-006 **except** `PUT /products/{id}/suppliers/{contact_id}` (buyer-initiated supplier-cost update, decision 2026-11-04) |
| 15 | Tickets/purchases lines with variant IDs | **Not documented** | Not needed any more (decision: movements) |
| 16 | Purchase orders / confirmed inbound | **Not documented** | Inbound stays in procurement-service |
| 17 | Webhooks / change feeds | **Not documented** | Incremental sync by `date_from` + id checkpoint |
| 18 | Pagination shapes | **Inconsistent** | `pagination{page,limit,total,pages}` (inventory), top-level `page/limit/totalPages` (purchases), `total` only (tickets) |

---

## 2b. Evidence from a one-month UI movements export (2026-11-03)

The real export stays on the owner's machine (never in this repo or any cloud service). Only patterns and ratios are recorded here.

| Observation | Consequence |
|---|---|
| UI export uses Spanish labels (`Envío de venta`, `Recepción de compra`…) and `dd/mm/yyyy, HH:MM` | The UI export is **not** the integration contract. The connector uses the API; a label ↔ `reason` mapping table is kept only for manual reconciliation |
| Reasons seen: sales ≈ ½, purchase receipts ≈ 40 %, adjustments ≈ 10 %, few customer returns, rare transfers, one initial stock | Matches the documented enum. Demand formula (ADR-012) holds |
| **Expiry write-offs are recorded as negative adjustments with a "caducidad" note**, not as reason `expiry` | Expiry/waste analytics cannot rely on `reason` **before the cutover date**. Never parse notes for decisions. Staff now record `expiry`/`damage`/`theft` correctly (decision 2026-11-04). Before the cutover, expiry loss is shown as "unclassified loss" in the UI |
| One sale-reason movement has a non-ticket reference and a "reduction" note | Quarantine rule: `sale_shipment` without a ticket/invoice-like reference → flagged for review, excluded from demand until confirmed |
| Purchase receipts use two reference styles (plain id and "Compra #n") | Reconciliation must accept both |
| Several warehouses plus an **"unassigned"** bucket; some SKUs move in more than one warehouse; transfers are rare | `warehouse_id` can be null → map to an explicit "unassigned" warehouse; ADR-012b (per-warehouse vs central proposals) is a real decision |
| Lot missing on ~8 % of movements; ~¼ have no expiry; a few expiry dates are malformed (3-digit year) | Data-quality gate: malformed dates → `import_errors`, never silently parsed |
| SKU formats are mixed (EAN-13 and internal codes) | Use `variant_id` as the key; SKU is an attribute only |
| **Demand is very sparse:** about ¼ of the catalogue moved in the month; among SKUs with sales, ~70 % sold once; ~85 % of sale lines are quantity 1 | Time-series forecasting per SKU is not viable at first. Start with **intermittent-demand policies**: reorder point / min-max with Poisson or negative-binomial safety stock, plus TSB/Croston only where backtests show a gain. ABC/XYZ drives the policy per segment |
| Volume is low (a few pages of 200 per month) | Movements backfill and daily sync use very little of the rate limit; the quota mainly limits per-variant calls (lots, suppliers) |
| Notes are always filled, sometimes with free text | Confirms: drop `notes` before storage; keep only a `has_note` flag |

## 3. Gaps and risks

### 3.1 Data and domain

| ID | Gap | Proposal |
|---|---|---|
| G1 | Do POS tickets produce `sale_shipment` movements? (row 11) | Gate 0 check: for a sample week, compare `sale_shipment` totals with tickets + invoices totals (aggregate only, read once, not stored) |
| G2 | Timezone of movement `created_at` (row 10) | Gate 0 check with a movement created at a known local time. Store UTC + original string |
| G3 | Stockout-censored demand | Rebuild daily on-hand history **backwards** from today's snapshot and the movements; days at ≤ 0 are censored. Validate against forward daily snapshots |
| G4 | Supplier data granularity | Siweb supplier cost is per product; variants of one product can differ in pack/size. Procurement keeps per-variant override + pack size |
| G5 | Cost freshness | Siweb supplier rows have no timestamp → `verified_at` = our import time, `source = siweb_product_supplier`; buyer can mark as verified. Staleness rule (ADR-015) |
| G6 | Inbound orders | Not in Siweb → created from approved proposals; receipts matched later to `purchase_receipt` movements |
| G7 | Multi-warehouse policy | ADR-012b: per-warehouse or central proposals |
| G8 | Money/units | Decimal EUR everywhere; cents may be fractional; explicit pack/UoM table |
| G9 | Tax (IVA / *recargo de equivalencia*) in landed cost | Siweb cost includes recargo (1.4 % at 10 % VAT, 5.2 % at 21 % VAT). Open: other VAT rates (e.g. 4 %), source of each product's VAT rate, remaining landed-cost tax treatment → confirm with the accountant |
| G10 | Discontinued products | Tombstone after N missed syncs |
| G11 | Recurrence (P2) data source and lawful basis | Deferred, needs a DPIA |

### 3.2 Architecture

| ID | Gap | Proposal |
|---|---|---|
| A1 | Bicep now, Terraform later | ADR-002 (§6) |
| A2 | Database | Reuse the existing PostgreSQL Flexible Server; dedicated `mmi` database; one schema + role + migration identity per service |
| A3 | Compute | Reuse the existing Container Apps environment if capacity allows; otherwise a new environment in the same network. Scale to zero, capped replicas |
| A4 | Service-to-service auth | Managed-identity tokens with per-service audience/app roles; dev issuer in Compose (ADR-007) |
| A5 | Queue message authenticity | Per-identity Sender/Processor RBAC; `payload_ref` checksum + schema validation (ADR-008) |
| A6 | Fan-out | Outbox relay writes one message per subscribed queue (ADR-008) |
| A7 | Blob ownership | Per-producer containers, read grants per consumer (ADR-009) |
| A8 | SPA + cookie BFF | Same-site hosting (ADR-010) |
| A9 | Shared rate limit | Per-app request budget, night window, central token bucket (ADR-005) |
| A10 | Contracts | JSON Schema → Pydantic + TS codegen (ADR-011) |
| A11 | i18n | es-ES default, no literal UI strings (ADR-013) |
| A12 | Delivery load for a small team | Keep microservices; recurrence-service P2; forecast as a Job only |

### 3.3 Security risks

| # | Risk | Mitigation |
|---|---|---|
| S1 | **Full-scope shared token** leaks or is misused: stock, price, supplier cost or document changes in the ERP | Connector client with a **closed GET allowlist** of paths (§4.3) plus the single supplier-cost `PUT` through a separate writer identity; unit tests that every other method/path is refused; outbound traffic only to the Siweb host; token only in Key Vault, read only by the connector identity; rotation runbook coordinated with the other app; ask the other app to apply the same allowlist |
| S2 | Leaks via the public repo | §3.4 rules + secret scanning, push protection, Gitleaks in pre-commit and CI |
| S3 | Shared quota exhaustion breaks the other app (or vice versa) | Hard per-app budget (ADR-005) and alerting on 429/denials |
| S4 | Unauthorised or self-approved proposals | Creator ≠ approver, fresh MFA for approval, hash-chained audit |
| S5 | Tampered supplier costs (in Siweb or our DB) | Versioned immutable cost rows; jump detection blocks a proposal until confirmed |
| S6 | Forged/replayed messages | RBAC per queue, inbox dedup, freshness window |
| S7 | Personal data in raw payloads (supplier tax IDs of sole traders, notes) | Drop `supplier_cif` and free-text `notes` before storage; no contacts/employees/time-tracking/tickets sync |
| S8 | Cost abuse | Replica caps, job parallelism 1, budget alerts, log ingestion cap |
| S9 | Supply chain | Pinned digests, hashed lockfiles, Trivy, pip-audit, SBOM, OIDC deploys, manual prod approval |
| S10 | Prompt injection via product names/notes | Data, never instructions (spec §8) |

### 3.4 Public repository rules (mandatory)

- **Never commit:** tokens, keys, connection strings, `.bicepparam`/`.tfvars` with real values, tenant/subscription/app IDs, internal resource names, IP ranges, real SKUs/products/suppliers/prices/quantities, raw Siweb responses, email addresses or names.
- **Commit only:** templates (`*.example`), synthetic fixtures, code, ADRs, generic docs.
- Security posture (what is or isn't enabled, findings) goes to the internal wiki, not to `security/` in the repo. The repo's `security/` folder holds the method (threat-model template, data classification scheme), not findings.
- Enforcement: `.gitignore` for param files and samples, Gitleaks + custom rules (Siweb host + `Bearer`, Azure IDs pattern), GitHub secret scanning push protection, PR template checklist.

---

## 4. Phase 1 data strategy

### 4.1 Local development and CI — synthetic only

- Generated by `packages/testing`: a fictional pet-shop / veterinary-pharmacy catalogue (~1,000 variants, fictional brands and suppliers), 3 fictional warehouses + an "unassigned" bucket, lots with expiry, ~9 months of movements across all 15 reasons. Demand profiles: smooth, intermittent, lumpy, seasonal, new products, discontinued, with stockout periods.
- **Calibrated only with the aggregate ratios in §2b** (reason mix, sparsity, quantity-1 dominance, Mon–Sat business hours, mixed SKU formats, missing lots, malformed expiry dates, expiry booked as negative adjustment). No real row, name, SKU, lot, reference or quantity is copied.
- Real exports are never used as fixtures; `.gitignore` blocks `*.csv`, `*.xlsx`, `*.har`, `/data/` and environment parameter files (synthetic CSV fixtures allowed under `packages/testing/**/fixtures/`).
- Shapes taken from the OpenAPI v1.2.0 examples. A seeded generator, so tests are reproducible.
- The Siweb mock serves it with real behaviours: three pagination shapes, newest-first paging with inserts mid-run, 429s, 401s, missing pages, timezone-less timestamps.

### 4.2 Azure — real data, collected early, stored only in Azure

| Data | Endpoint | Frequency | Approx. requests |
|---|---|---|---|
| Warehouses | `/inventory/warehouses` | daily | 1 |
| Products | `/inventory/products` | daily | pages of products |
| Variants + stock totals (snapshot) | `/inventory/variants` | daily | ~1,000 ÷ page size |
| **Movements — one-off backfill** | `/inventory/movements` (`limit=200`, `date_to` frozen) | once, spread over several nights | total movements ÷ 200 |
| Movements — incremental | `/inventory/movements?date_from=<checkpoint>` | daily | a few pages |
| Product suppliers (cost, lead time, MOQ) | `/inventory/products/{id}/suppliers` | weekly, rotating ~1/7 of products per night | ~products ÷ 7 per night |
| Lot/expiry levels | `/inventory/variants/{id}/stock` | rotating subset, medicines / expiry-tracked first | capped per night |

**Not collected:** tickets, invoices, budgets, delivery notes, contacts, employees, time tracking, accounting, auctions.
**Minimisation:** drop `supplier_cif` and `notes`; keep raw payloads (after dropping those fields) in an immutable container with bounded retention.
All of this fits in a nightly window under an MMI budget of ~500 requests/hour (ADR-005, to agree with the other app).

### 4.3 Siweb allowlist (connector)

`/inventory/warehouses`, `/inventory/products`, `/inventory/products/{id}`, `/inventory/products/{id}/suppliers`, `/inventory/variants`, `/inventory/variants/{id}`, `/inventory/variants/{id}/stock`, `/inventory/variants/{id}/lots`, `/inventory/movements`, `/inventory/variants/{id}/movements`, `/purchases` + `/purchases/{id}` (reconciliation only, if needed later). Everything else is refused before the request is sent.

**Single permitted write (separate writer identity):** `PUT /inventory/products/{id}/suppliers/{contact_id}`, supplier cost including recargo, only after buyer review. Every other method and path stays refused.

---

## 5. Prerequisites (Gate 0)

| # | Prerequisite | Status |
|---|---|---|
| P0.1 | OpenAPI with movements endpoints | **Done** (v1.2.0) |
| P0.2 | Token model | **Done** (single full-scope token) |
| P0.3 | Live-response checks: movement timezone, `reference_type` values, POS tickets → `sale_shipment`, history depth, max page size of `/variants`, 429 behaviour | Open — one small spike, results recorded in the internal wiki |
| P0.4 | Agree the rate-limit split with the other app (proposal: MMI ≤ 500 req/h, night window) | Open |
| P0.5 | Repo protection: protected `main`, required checks, secret scanning push protection, Dependabot | Open |
| P0.6 | Budget: current monthly spend of the existing app → remaining room for MMI. Region-specific prices for the delta only (extra DB storage, ACA apps/jobs, Blob/Queues, log ingestion) | Open |
| P0.7 | Supplier data beyond Siweb: pack sizes, discounts, price lists | Open |
| P0.8 | Tax regime for landed cost | Open |

**Cost rules (because EUR 120 is shared):** no new database server, registry, key vault or monitoring workspace unless an ADR justifies it; no Private Endpoints beyond those already in place without pricing; scale to zero; one job execution at a time; log ingestion cap; budget alerts at 50/80/100 % of the shared total.

---

## 6. ADRs

| ADR | Title | Status / recommendation |
|---|---|---|
| 001 | Record decisions (MADR) | Proposed |
| 002 | IaC: **Bicep now, Terraform-ready** | **Accepted.** One Bicep module per resource type, parameters in `*.bicepparam.example` only, no logic in params, resource names from one naming module, so a later `terraform import`/rewrite is mechanical. Revisit when the shared estate moves to Terraform |
| 003 | PostgreSQL: reuse server, `mmi` database, per-service schema/role/migrations | Proposed |
| 004 | Compute: reuse Container Apps environment, scale-to-zero, caps | Proposed (capacity check internal) |
| 005 | Siweb shared rate-limit budget and schedule | Proposed: token bucket ≤ 500 req/h, night window, backfill over several nights |
| 006 | Siweb access control on our side: GET allowlist, host allowlist, KV-only token, rotation. **Amended 2026-11-04:** one permitted write, `PUT /inventory/products/{id}/suppliers/{contact_id}`, only on buyer action (missing cost entered, or order confirmed at a different cost); separate writer identity and permissions, closed allowlist of that operation only, buyer review before sending, audit (who/when/old/new/outcome), visible retries, product-level (warn when variant costs differ) | Proposed — **highest priority** |
| 007 | Service-to-service authentication | Proposed |
| 008 | Messaging: Storage Queues, outbox, fan-out, dedup, poison queue | Proposed |
| 009 | Blob layout, ownership, retention, minimisation | Proposed |
| 010 | BFF session and same-site SPA hosting | Proposed |
| 011 | Contract format and versioning | Proposed |
| 012 | **Demand from movements**: `demand = −Σ sale_shipment − Σ return_customer` (per variant, day, warehouse); transfers, adjustments, damage, theft, expiry, counts, initial stock, production and supplier flows excluded and kept as separate series. Loss classification by **reason cutover date** (configurable, default 2026-09-19): **before** → every `adjustment_negative` = `unclassified_loss` (reason not captured by the system); **after** → `expiry`/`damage`/`theft` are trusted, and `adjustment_negative` without a reason = `unspecified_loss` (staff omitted it). Loss is never demand. Free-text notes are not parsed or stored; only a `has_note` flag is kept. Data-quality metric: share of post-cutover negative adjustments without a structured reason, shown to the buyer as a staff-training signal | **Accepted**, `reference_type` details after P0.3 |
| 012b | Warehouse granularity of proposals | Open |
| 013 | Localisation es-ES | Proposed |
| 014 | Recurrence data source and lawful basis | Deferred (P2) |
| 015 | Supplier cost provenance: sources (`siweb_product_supplier`, `csv_price_list`, `manual`), versioned rows, `verified_at`, staleness | Proposed |
| 016 | Approval workflow and separation of duties | Proposed |
| 017 | Public-repository data policy (§3.4) | Proposed |

---

## 7. Prioritised plan

| Phase | Content | Gate |
|---|---|---|
| **0 — Verify & decide** (1 wk) | P0.3–P0.8; ADR-001/002/005/006/012/017 accepted; threat model (internal) | Spike results recorded; demand formula confirmed |
| **1a — Foundation** (2 wk) | Monorepo, `AGENTS.md`/`CLAUDE.md`, contracts + codegen, **synthetic data generator + Siweb mock**, Compose (Postgres per-service schemas, Azurite, mock, dev JWT issuer), service skeletons, CI with path filters and security scans, Bicep skeleton | `docker compose up --build` with zero Azure credentials; CI green |
| **1b — Early capture** (1 wk, parallel) | Minimal connector job in Azure: §4.2 datasets, GET allowlist, rate budget, raw → Blob, snapshots + movements → `integration`/`inventory` | 7 clean nights; backfill complete; counts reconcile with `pagination.total` |
| **2 — Integration** (2–3 wk) | Full typed client, checkpoints, mappings, import errors, outbox events, contract tests from sanitised samples (kept outside the repo) | 2 weeks clean reconciliation |
| **3 — Demand** (3 wk) | `DemandProvider` (movements), backward stock reconstruction + censoring, data-quality gates, ABC/XYZ, baselines, rolling backtests | Per-SKU "forecast eligible" flag |
| **4 — Procurement MVP** (4 wk) | Supplier costs (Siweb + CSV + manual), constraints, periodic-review engine, proposal lifecycle, explanations, approval, export, es-ES UI | Buyer approves and exports a weekly proposal unaided (shadow mode) |
| **5 — Production** (2 wk + 4–8 wk shadow) | Entra roles, MFA, network review, backup restore drill, alerts, runbooks | Shadow results reviewed |
| **6 — P2** | OR-Tools, recurrence (after DPIA), optional purchase drafts with human approval | — |

---

## 8. Open questions

1. Which API `reference_type` do ticket sales carry? (The UI export indicates tickets do create sale movements.)
2. How far back does movement history go?
2b. Loss reasons — answered (cutover ≈ mid-September 2026). Confirm the exact date to replace the 2026-09-19 default.
2c. Grooming — answered: ordered on demand, never in stock → out of scope.
3. One warehouse or several — and do orders go per warehouse?
4. Can the other app accept a fixed share of the 1,000 req/h (e.g. MMI ≤ 500 at night)?
5. Where do pack sizes, discounts and current price lists live today?
6. Tax regime for purchases?
7. Who approves proposals, and must it be a different person from the buyer?
