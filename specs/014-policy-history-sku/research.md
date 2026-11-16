# Research: SKU in the policy history

## R1. Which service owns the history rows?

- **Decision**: Procurement. `GET /admin/status` forwards `GET /policy-overrides?status=all` to procurement (`services/api-bff/src/routes/admin_status.py`); procurement builds the rows in `override_json` (`services/procurement-service/src/api/policies.py`).
- **Rationale**: Resolves Jira's "procurement or forecast (owner to confirm)". Forecast is not involved.
- **Alternatives**: Forecast (holds no override data); resolving in the gateway (breaks ADR-023 and rule 9).

## R2. Does the SKU already exist in the payload?

- **Decision**: Yes. `override_json` adds `"sku": sku_for_variant(conn, variant_id)` (feature 011). `sku_for_variant` reads `product_refs.sku`, trims it, and returns null only when the product is absent. The gateway card returns the downstream list unchanged.
- **Rationale**: The work is not a new service feature; it is making the contract and the web screen match what the service already sends, and pinning it with tests.
- **Alternatives**: A second lookup in the gateway (duplicate, wrong layer); storing the SKU on the override row (a snapshot; spec A3 chooses the current catalogue SKU).

## R3. Contract state

- **Decision**: Add `sku` (string or null) to `policy_override_request.v1.schema.json`. The schema has `additionalProperties: false`, so a real list row would fail validation today; it also lacks `requested_at`, which the service sends. Add `sku` now; add `requested_at` only if the contract gate flags it.
- **Rationale**: Contract-first (rule 9). Additive, so the schema stays v1 with a matrix note; Agent 00 decides whether a version bump is needed.
- **Alternatives**: A v2 schema (unneeded for an additive nullable field); relaxing `additionalProperties` (hides drift).

## R4. Null SKU cases

- **Decision**: `sku` is null when the product is missing from `product_refs` or its SKU is empty or whitespace; the row is still returned. The web shows a Spanish "not applicable" marker.
- **Rationale**: Rule 6 (never drop data silently). Today a whitespace-only SKU would come back as an empty string after `strip()`; the small fix in `sku_for_variant` returns null, covered by a test.
- **Alternatives**: Hide rows with no SKU (loses audit history); fall back to the variant id (violates rule 5).

## R5. Web display and the baseline

- **Decision**: The column in `AdminStatusScreen.tsx` shows `sku`, sorts by it, and the `AdminStatusScreen.tsx` entry is removed from `apps/web/tests/unit/variant-id-display.baseline.json`. The header and marker go into `es-ES.json`; the i18n coverage test stays green.
- **Rationale**: Satisfies FR-003, FR-007 and FR-010.
- **Alternatives**: Keep `variant_id` as a hidden column (still an exposure risk in the page).

## R6. Performance

- **Decision**: No change. `sku_for_variant` is already called per row, and the screen shows at most 20 rows.
- **Rationale**: SC-004 holds by not adding work. A batched lookup is out of scope unless measured slow.
- **Alternatives**: Join in the queue query (premature).
