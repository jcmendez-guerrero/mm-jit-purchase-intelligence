# Phase 0 Research: Mundo Mascotix Intelligence

All Technical Context items are resolved below. Items that need live-system confirmation are listed in **Open verification items** and treated as explicit assumptions (constitution: Development Workflow).

## Decisions

### R1. Stack and hosting

- **Decision**: Python 3.12/FastAPI services, React/TS SPA, PostgreSQL, Azure Container Apps (Consumption) + Jobs, Blob, Storage Queues.
- **Rationale**: Matches the architecture specification and constitution; lowest idle cost; local parity via Compose/Azurite.
- **Alternatives**: AKS (cost/ops), Service Bus (not justified yet; Storage Queues behind an interface keep the option open), Functions (weaker local parity and shared-code story).

### R2. IaC

- **Decision**: Bicep, one module per resource type, `*.bicepparam.example` only, one naming module (ADR-002).
- **Rationale**: Decided 2026-11-04; Terraform-ready structure keeps migration mechanical.

### R3. Siweb access control (reader + writer)

- **Decision**: Reader client with a compiled-in closed list of (method, path-template) pairs, host allowlist, refusal before any socket is opened. Writer is a separate service/identity with a single allowed pair `PUT /inventory/products/{id}/suppliers/{contact_id}`. Both read the token from Key Vault under separate access policies; same secret value since Siweb issues one token, so separation is enforced by code path, identity and network egress rules, not by the token.
- **Rationale**: Constitution Principle I. Token scope cannot be reduced on Siweb's side.
- **Alternatives**: One client with a flag (rejected: write capability in the nightly job); a second Siweb token (not offered by Siweb).
- **Residual risk**: The writer holds a full-scope token. Mitigations: tiny codebase, egress limited to the Siweb host, request body schema-validated to the one cost field, audit log, alert on any write not tied to a buyer action. Record in internal threat model.

### R4. Siweb supplier-cost write semantics

- **Decision**: Writes are triggered only by two buyer actions: (a) buyer enters cost where Siweb has none; (b) buyer confirms an order whose cost differs from Siweb. The value is cost **including recargo de equivalencia**. Each attempt is a durable `cost_write_request` (idempotency key = pair + cost version), shown to the buyer for review before dispatch, executed by the writer, outcome recorded, retries with bounded backoff visible in the UI. Read-after-write verification via `GET .../suppliers` after each success.
- **Rationale**: FR-040 to FR-043; Siweb supplier cost is per product, so variants sharing a product share one written value.
- **Alternatives**: Fire-and-forget write (rejected: silent loss); batch nightly write (rejected: delays ERP truth and obscures who triggered it).
- **Scope decision (analysis E1)**: case (a) covers only pairs where Siweb already has a supplier record without a cost. If no product–supplier record exists, the request goes to `pending_link` and the buyer creates the link in the ERP; creating links via the PUT is out of scope until V4 proves it and the decision is recorded.
- **Open**: exact PUT body (partial vs full replace of `is_preferred`, lead time, MOQ). A full replace could overwrite other fields, so the writer MUST read-modify-write and only change `purchase_cost_cents`; validated in Phase 0 against a non-production record.

### R5. Recargo de equivalencia

- **Decision**: Decimal arithmetic. Stored per cost version: `cost_net` (excl. recargo), `recargo_rate`, `cost_with_recargo`, `entered_includes_recargo` flag, `vat_rate` snapshot. Rates: VAT 10 % → 1.4 %, VAT 21 % → 5.2 %. Costs read from Siweb are `cost_with_recargo`; `cost_net = cost_with_recargo / (1 + rate)`. Rates held in a versioned configuration table, not code. Unknown VAT rate: only "includes recargo" entry allowed; no net conversion.
- **Rationale**: Business statement 2026-11-04; auditable and changeable.
- **Open**: source of each product's VAT rate (Siweb variant/product field if present, otherwise buyer-maintained per product); handling of 4 % VAT / 0.5 % recargo and exempt items; rounding rule (default: round half-up to 4 decimals internally, 2 decimals for display and for the value written). Confirm with accountant.

### R6. Demand and loss classification

- **Decision**: ADR-012 as written: `demand = −Σ sale_shipment − Σ return_customer`; losses split by configurable cutover date (default 2026-09-19); sale movements without ticket/invoice-like reference quarantined; stock history rebuilt backwards from the current snapshot; days ≤ 0 censored.
- **Rationale**: Already accepted; only `reference_type` details wait for live checks.

### R7. Forecasting / stocking policy

- **Decision**: Policy ladder by segment: (1) min/max with Poisson/negative-binomial safety stock for intermittent items; (2) moving average / seasonal-naive where data qualify; (3) Croston/TSB/ADIDA only where rolling-origin backtests beat baselines on economic cost (stockout + holding + expiry). LightGBM deferred. Ineligible items fall back to conservative min/max.
- **Rationale**: Sparse demand (~70 % of sold SKUs sold once); economic objective over accuracy metrics.
- **Alternatives**: Per-SKU ML (not viable on data volume), global ML (deferred until more history).

### R8. Service levels (spec FR-039)

- **Decision**: Defaults, stored in an editable configuration table with history: clinical-critical 99 %, ABC-A 97 %, ABC-B 95 %, ABC-C 90 %, sparse/slow items 85 % (applied when lower than the ABC value). Per-product override allowed. Changes apply to later proposals only.
- **Rationale**: Reasonable starting points; buyer can adjust any time. Validated in shadow period.

### R9. Supplier allocation (spec FR-038)

- **Decision**: Two stages: (1) per-line eligible supplier set with landed unit cost (cost with recargo + pro-rata delivery) from verified, non-stale costs, lead time ≤ protection horizon; (2) OR-Tools CP-SAT over integer cents/units choosing supplier and pack-multiple quantity per line, with supplier fixed-charge variables for minimum order value, minimum quantity, free-delivery threshold and delivery charge, budget cap and overrides. Objective: minimise total landed cost plus penalties for risk (late delivery against horizon, shortfall). A greedy cheapest-supplier plan is produced first as baseline, explanation comparator and solver-timeout fallback. Solver time-boxed (default 30 s), deterministic seed, inputs hashed for reproducibility.
- **Rationale**: Minimums and thresholds are discrete effects a greedy rule cannot capture; integer modelling avoids float money.
- **Alternatives**: MILP via PuLP/HiGHS (also fine; CP-SAT chosen for integer cost modelling and time-boxing), manual-only allocation.
- **Top-up logic**: When a supplier minimum is unmet, the model may add items from the "needed within next review" set, move lines, or emit a flagged shortfall; each option's cost delta is reported (spec 4b).

### R10. Supplier terms and price-list data

- **Decision**: Supplier-level terms (minimum order value, minimum quantity for delivery, free-delivery threshold, delivery charge, order days, delivery schedule) are buyer-maintained in the app. Price lists loaded by CSV/Excel with a fixed per-supplier template (validation, error list) and manual editing. Cost source priority for a pair: latest verified of `siweb_product_supplier`, `csv_price_list`, `manual`; buyer override by marking verified. Staleness default 30 days since `verified_at`; abnormal jump default ±25 % versus the prior version blocks proposal use until confirmed. All thresholds configurable.
- **Rationale**: ERP lacks these terms; provenance per ADR-015.

### R11. Messaging

- **Decision**: Storage Queues behind a `MessageBus` interface; outbox relay writes one message per subscribed queue; inbox dedup table; envelope `event_id,type,schema_version,occurred_at,correlation_id,resource_id,payload_ref`; `payload_ref` checksum + schema validation; bounded exponential backoff; poison queue with alert; per-identity Sender/Processor RBAC.
- **Events**: the five in the architecture spec plus `procurement.order.confirmed.v1`, `procurement.cost.write_requested.v1`, `siweb.cost.write_completed.v1`.

### R12. Identity, sessions, roles

- **Decision**: Entra ID OIDC with MFA for humans; SPA served same-site as BFF; BFF issues Secure/HttpOnly/SameSite=Lax cookie session, CSRF token on mutations; roles viewer/buyer/approver/admin as app roles; fresh-MFA step-up (auth_time within 5 minutes) enforced on approve and on cost-write confirmation; service-to-service via managed identities with per-service audience/app roles; dev issuer in Compose.
- **Separation of duties** (clarified): approver ≠ creator and ≠ last editor of the proposal; edits after submission reset eligibility; admin cannot approve unless holding the approver role and satisfying the same rule.

### R13. Localisation

- **Decision**: es-ES default; i18next resource files; lint/test that fails on literal user-facing strings and missing keys; `Intl` formatting for EUR/dates; UTC and ISO codes in storage; Excel/CSV headers and number formats in Spanish locale (semicolon CSV, comma decimal) with a documented export profile.

### R14. Contracts and codegen

- **Decision**: JSON Schema (draft 2020-12) in `packages/contracts`, versioned per file; Pydantic via datamodel-code-generator, TS via json-schema-to-typescript; BFF OpenAPI validated by schemathesis; compatibility tests on schema diffs; consumer-driven contract tests from sanitised samples kept outside the repo.

### R15. Observability and cost

- **Decision**: OpenTelemetry-style structured logs with correlation IDs and redaction; metrics: sync freshness, queue age, quota use/denials, backtest error, proposal duration, cost-write outcomes, auth denials; log ingestion cap; alerts for failed syncs, poison messages, cost, suspicious approvals, any write outside a buyer action; budget alerts at 50/80/100 % of the shared total; jobs parallelism 1; replica caps; scale to zero.

### R16. Test data and Siweb mock

- **Decision**: Seeded generator in `packages/testing` calibrated only with aggregate ratios from the implementation plan §2b; mock implements three pagination shapes, newest-first paging with inserts mid-run, 429/401/missing pages, timezone-less timestamps, and the supplier-cost PUT (with read-modify-write pitfalls and failure injection). No real rows, names, SKUs or references.

## Open verification items (Gate 0)

| ID | Item | Treated as assumption until checked |
|----|------|-------------------------------------|
| V1 | Movement `created_at` timezone | **Verified 2026-11-04:** two movements matched the Siweb UI to the second (UI shows CET); the API returns the same wall-clock time with no offset, so it is Europe/Madrid local time. Store UTC + original string. Ambiguous (autumn repeated hour) and non-existent (spring skipped hour) local times go to the review list, not guessed |
| V2 | `reference_type` for ticket sales; POS tickets → `sale_shipment` | Quarantine unreferenced sales |
| V3 | History depth, `/variants` max page size, 429/`Retry-After` behaviour | Conservative bucket, adaptive backoff |
| V4 | Exact `PUT .../suppliers/{contact_id}` body and merge semantics, and whether it can create a link | **Verified 2026-11-04/05 on a test product (T135), corrected on 05-11:** the PUT upserts (a missing link is created, 200) and returns the record. It **merges**: a cost-only body left `supplier_reference` and `is_preferred` unchanged. `lead_time_days` and `min_order_qty` are **not writable** through it (sent as 3 and 2, stored as null; an earlier reading of this as a "replace" was wrong). Unknown fields are ignored (200). Negative or non-numeric cost returns 400 (Spanish message); fractional cents are accepted, so the writer validates integer cents itself. The writer still resends `supplier_reference` and `is_preferred` read just before the call, which is safe under either semantic. Link creation stays out of scope (`pending_link`) until a decision is recorded |
| V5 | VAT-rate source per product; 4 % VAT/exempt handling; rounding | Buyer-maintained VAT rate per product |
| V6 | Rate split with the other app | MMI ≤ 500 req/h, night window |
| V7 | Exact loss-reason cutover date | 2026-09-19 default |
