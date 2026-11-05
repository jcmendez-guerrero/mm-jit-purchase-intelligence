# Quickstart: Validation Scenarios

Runs entirely locally with synthetic data and no cloud credentials. Details of tables and interfaces: [data-model.md](data-model.md), [contracts/](contracts/). Commands below describe the intended interface; they become real as the foundation phase lands.

## Prerequisites

- Docker with Compose; Python 3.12; Node 20+
- No Azure, Siweb or Entra credentials needed (local dev issuer and Siweb mock are included)

## 1. Start the whole system

```bash
docker compose -f infra/compose.yaml up --build
```

Expected: PostgreSQL (per-service schemas/roles), Azurite, Siweb mock (seeded synthetic catalogue ~1,000 variants, 3 warehouses + unassigned, ~9 months of movements), dev token issuer, all services and the SPA are healthy. UI is Spanish.

## 2. Collection and reconciliation (Story 1)

```bash
docker compose -f infra/compose.yaml run --rm siweb-connector sync --kind all
```

Expected: stored counts equal the mock's reported totals; quarantined records (malformed expiry, unreferenced sale, missing warehouse) appear in the review list; no fields `supplier_cif`/`notes` in stored data; run stays within the request budget.

Negative check:

```bash
pytest services/siweb-connector/tests/contract -k allowlist
```

Expected: every method/path outside the allowlist, any other host, and any redirect are refused before sending; the writer's single `PUT` is refused when called from the reader.

## 3. Demand and classification (Stories 2–3)

```bash
pytest services/inventory-service/tests -k "demand or losses or censoring or classification"
pytest services/forecast-service/tests -k backtest
```

Expected: demand = sale shipments − customer returns; pre-cutover negative adjustments are "unclassified loss", post-cutover are classified; zero-stock days are censored; products with sparse/ambiguous history are not forecast-eligible.

## 4. Costs, recargo and cost write-back (Stories 4–5)

1. In the UI as `buyer`, open a product-supplier pair that has no cost in the mock Siweb.
2. Enter a cost with "incluye recargo" **unchecked**: the screen shows the cost with recargo (VAT 10 % → +1.4 %, VAT 21 % → +5.2 %).
3. Review and release the pending Siweb cost update (step-up MFA prompt).
4. Expected: mock Siweb receives exactly one allowed `PUT` containing only the changed cost; outcome and audit record visible; force a mock failure and confirm the write stays visible and retries.

5. Enter a cost for a pair the mock Siweb has no supplier record for: expected status "pendiente de alta en Siweb", zero requests to the mock, cost kept locally; add the record in the mock and re-release: one `PUT` is sent.

## 5. Weekly proposal, approval and ordering (Story 5)

1. As `buyer`, generate the proposal; open it grouped by supplier.
2. Check a supplier whose minimum is unmet: top-up/reallocation/shortfall options with cost impact are shown.
3. Edit a line; submit; as the same user try to approve → refused; as another `approver` with fresh MFA → approved.
4. Confirm the order with a supplier at a different cost → cost write created for review.
5. Export CSV and Excel (Spanish locale formats).
6. Regenerate with identical inputs → identical proposal (reproducibility).

## 6. Localisation, roles, resilience (Stories 6–7)

```bash
npm --prefix apps/web test            # fails on untranslated or hard-coded strings
npm --prefix apps/web run e2e         # role matrix, es-ES formats
pytest packages/contracts             # schema compatibility
pytest services -k "idempotent or poison or replay"
```

Expected: viewer read-only, buyer edits, approver approves, admin manages; duplicate/forged/replayed messages processed at most once or rejected; poison queue alert raised.

## 7. Security and repository hygiene

```bash
gitleaks detect --no-banner
```

Expected: no findings; CI also runs Trivy, pip-audit and the contract tests on changed paths.

## Gate 0 checklist (before relying on live data)

Record outcomes in the internal wiki, not in this repository: movement timezone, ticket `reference_type`, history depth, page sizes, 429 behaviour, exact supplier-cost `PUT` semantics, VAT-rate source, rate-limit split, loss-reason cutover date. See [research.md](research.md) open items V1–V7.
