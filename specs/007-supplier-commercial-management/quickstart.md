# Quickstart: validating Supplier Commercial Management

All checks use synthetic fixtures from `packages/testing`; never a real ERP host or real export.

## Prerequisites

- Local environment as in `specs/004-local-test-data-suppliers/quickstart.md` (local issuer, local database).
- Procurement-service dev dependencies installed.

## 1. Baseline (before any change): turn the audit into verified

There is no lockfile, so create the environment first (task T001 records the final working commands here):

```bash
uv sync --all-packages
```

Always sync all packages at once: `uv sync --package <one>` is exact and removes what the other packages need (it broke the procurement environment once).

`uv` writes an untracked `uv.lock` (the repository does not commit one); do not stage it. Run the tests in the prepared environment:

```bash
uv run --no-sync python -m pytest services/procurement-service/tests -k "terms or supplier or allocation_terms or bulk_assign or no_erp or refuse_local or abuse_ids or preferred or scenarios_infeasible or input_versions" -q -p no:cacheprovider
```

Install `mmi-testing` too: `test_refuse_local_ids.py` imports `export_loader` from it.

Expected: all pass. Record the result next to each "complete" row in [research.md](research.md); a failure reclassifies the row as broken.

## 2. Gap tests (written first, fail until implemented)

```bash
cd services/procurement-service && python -m pytest tests/test_terms_idempotency.py tests/test_terms_refusal_audit.py tests/test_terms_delivery_date.py -q
```

Expected after implementation: same key + body creates one version; different body is `idempotency_key_reuse`; each refusal class leaves a `*.refused` audit entry without a body; delivery date follows schedule, cutoff and lead time.

## 3. Conflict and effective-date scenario (API)

1. Create a synthetic supplier; `PUT terms` (no header) -> version 1.
2. `PUT terms` with `If-Match: 1` and `valid_from` next month -> version 2; proposals dated today still cite version 1.
3. Two clients `PUT` with `If-Match: 2`; the second receives 412 with the current version.

Expected: SC-003 and SC-004 hold; no ERP request is recorded (`test_terms_no_erp.py`).

## 3b. Exchange rates (fake transport, no network)

```bash
uv run --no-sync python -m pytest services/procurement-service/tests/test_fx_rates.py services/procurement-service/tests/test_non_eur_supplier.py services/procurement-service/tests/test_worker_fx.py -q -p no:cacheprovider
```

Expected: only the approved host, path and GET are allowed; a fresh rate converts; a missing, unsupported or over-7-day rate excludes the supplier with a review item; proposal generation makes no rate call.

## 4. UI journey (Playwright, Spanish)

Use **Node 20** (what CI uses; `engines` is `>=20`). Under Node 26 on this machine 23 jsdom unit tests fail (`localStorage.clear`, `AbortSignal`), which is the environment, not the code. One-time setup:

```bash
cd apps/web && npm ci
```

```bash
cd apps/web && PATH="$HOME/.nvm/versions/node/v20.19.5/bin:$PATH" npx vitest run
```

```bash
cd apps/web && npx playwright test tests/e2e/suppliers-terms-journey.spec.ts
```

Covers: create supplier, set terms, link three SKUs, future-dated version, stale-save conflict message, deactivate with affected-lines preview, viewer read-only, no ERP id visible, no untranslated text. Screenshots are attached to the PR.

## 5. Safety checks

```bash
cd services/procurement-service && python -m pytest tests/test_terms_no_erp.py tests/test_refuse_local_ids.py tests/test_abuse_ids.py -q
```

Expected: ERP-owned data identical before and after; zero ERP requests.

## 6. Review hardening (FR-038 to FR-043)

```bash
uv run --no-sync python -m pytest services/procurement-service/tests/test_refusal_volume.py services/procurement-service/tests/test_terms_abuse.py services/procurement-service/tests/perf/test_refusal_burst.py services/procurement-service/tests/test_worker_fx.py -q -p no:cacheprovider
```

Expected: 50 simultaneous identical refusals leave one audit entry with an accurate skipped count; a body over the limit is refused under any content type; a forced failure of the rate storage step does not stop event relay, and the pass reports it.
