# Research: SKU in scenario changes and result lines

## R1. Where the SKU is added

- **Decision**: Add it when a scenario is read (`store.get`), not when it is computed or stored.
- **Rationale**: Lines and changes are stored as JSON, so older scenarios have no SKU. Adding it at read time makes them work with no migration and no recompute, keeps `result_hash` identical (FR-007, FR-011) and follows A3 (current catalogue SKU).
- **Alternatives**: Store the SKU at creation (needs a backfill and could change stored data; rejected). Resolve in the gateway (breaks ADR-023 and FR-006; rejected).

## R2. How it is resolved

- **Decision**: One batched query on `product_refs` for all variant ids in the scenario (changes plus lines), trimmed; empty or whitespace becomes null. Reuse the rule of `policies.service.sku_for_variant`, with a batch variant to avoid one query per row.
- **Rationale**: Same source and same normalisation as PR 22 routes; one query keeps SC-004. Surrogate ids (9,000,000 range) resolve like any other.
- **Alternatives**: Call `sku_for_variant` per row (N+1; rejected).

## R3. Contract shape and the frozen baseline

- **Finding**: `scenario_result.v1` line items allow no extra properties and have no `sku`. `scenario.v1` has no `summary`/`changes` at all, though the API returns `summary.changes`, so the changes shape is currently undocumented.
- **Decision** (clarified 2026-11-16): `sku` is required and nullable in the line and change items. If the gate refuses a required field in v1, bump to v2.
- **Rationale**: Consumers never have to tell "unknown" from "old service"; matches the PR 22 routes.
- **Open point for Agent 00**: whether the gate accepts a required field in v1; if not, v2.

## R4. Gateway

- **Decision**: No code change expected; `routes/scenarios.py` forwards the procurement body as is. Verify no response filter drops unknown fields, and that `test_routes_do_no_money_arithmetic` still passes.

## R5. Web

- **Decision**: In `ScenariosScreen.tsx`, show `sku` in the change rows (line 218-220 area) and the line table (line 259), using the existing es-ES "no SKU" marker if the catalogue has one, else add one. Remove the scenarios entry (2) from the baseline; the shrink-only test then guards it.
- **Note**: Row keys may keep using `variant_id` (the display test only flags shown text).

## Outcome (implementation, 2026-11-16)

- R3 settled without v2: `python -m gates run` accepts `sku` as required in the line and change items (the gate checks required fields only at the top level of each schema), so the schemas stay at v1 and the baseline is unchanged. Agent 00 should still confirm at review.
- Not done here: scenario list items, the "clinically critical variants" line of an infeasible scenario (`scenarios.critical` shows variant ids) and the manual checks T028 and T029. The critical line is a third place that still shows ids; it needs its own change (schema field for the SKUs, or the SKU list from procurement).

- Superseded 2026-11-17 by Agent 00 review of PR 29: `sku` is optional in the v1 schemas (ADR-021), the contracts gate only compares top-level `required`, and the baselines were refreshed. The service still always sends it.
