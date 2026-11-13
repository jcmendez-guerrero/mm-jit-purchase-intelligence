# Gateway review (`services/api-bff`, ADR-023)

Review of the gateway for business-rule logic, done at commit `9d11abb`. Findings that belong to other agents are reported here, not changed.

## Scope and method

11 route files, 1,439 lines. A text search (not a full read) for aggregation and arithmetic (`sum(`, `sorted(`, `max(`, `min(`, percentage maths, `strptime`, loops) covered `api.py`, `costs.py`, `suppliers.py`, `policies.py`, `scenarios.py`, `imports.py` and `rbac.py`. `dashboard.py`, `admin_roles.py`, `admin_status.py` and `local_load.py` were checked only for money arithmetic (test `test_gateway_composition.py`) and, for `local_load.py`, read for the idempotency cache. This is **not** a full code review.

## Findings

| # | Finding | Severity | Owner / action |
|---|---|---|---|
| G1 | No money arithmetic in any route except `admin_status.py`, which reads a configured budget estimate from the environment (`float(os.environ…)`) and computes nothing. Pinned by `test_routes_do_no_money_arithmetic`. | none | none |
| G2 | The only business-looking check found is input hygiene in `suppliers.py` (SKU length and control characters). This is boundary validation, acceptable at the gateway. | low | none |
| G3 | 54 mutating endpoints (POST, PUT, PATCH, DELETE); `POST /api/scenarios` and, since MMI-6 (spec 007), the two terms saves `PUT /api/suppliers/{supplier_id}/terms` and `PUT /api/product-suppliers/{variant_id}/{supplier_id}/terms` declare an `Idempotency-Key`. The other mutations rely on the owning domain's state rules (for example approve, submit and activate refuse repeats). Not verified here that every one of them is safe to repeat. | medium | Domain owners: confirm repeat safety per endpoint, or add a key. Pinned by `test_only_the_recorded_routes_declare_an_idempotency_key`. |
| G4 | `local_load.py` keeps a process-local, in-memory idempotency cache (`_idempotent`, 900 s). It is lost on restart and not shared between replicas. The loader is local-only by the constitution, so this is acceptable there. | low | api-bff owner: keep it out of any cloud configuration (already required). |
| G5 | `dashboard.py`, `admin_roles.py` and `admin_status.py` were not read for rule logic beyond money arithmetic. | open | Review in a later pass. |
| G6 | Feature 011 (MMI-8): `GET /api/policy-audit` in `routes/policies.py` merges the audit of procurement, inventory and forecast with the gateway's own refusals, converts timestamps to Europe/Madrid days, filters by scope, outcome and dates, and pages at 50 rows. The services apply the filters and the 500-row limit (`prefix`, `outcome`, `since`, `until`); the gateway only merges, sorts and pages. No rule or money logic is involved, so this is presentation logic that no domain service could own (the refusals exist only at the gateway). Accepted here; raised by Agent 00 in the review of PR 22. | low | api-bff owner: keep it to merge, sort and page. |

## What the tests now guarantee

- `services/api-bff/tests/test_gateway_composition.py`: routes contain no money arithmetic; the dashboard overview returns domain values verbatim and sends each domain only its own paths.
- `services/api-bff/tests/test_gateway_idempotency.py`: the set of keyed mutations is pinned; a repeated key is forwarded unchanged on every attempt.

These sit in the gateway's own test folder, not `infra/tests` as planned, because they need that package's fixtures.
