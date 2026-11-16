# SKU route for the product-supplier terms (MMI-16, spec 014)

Jira: [MMI-16](https://mundomascotix.atlassian.net/browse/MMI-16). Spec: `specs/014-sku-override-terms-route/`. Request 4 of `specs/012-ux-navigation-localization/evidence/owner-requests.md`.

## What and why

Project rule 5: people see and enter the SKU; Siweb ids stay inside the platform. The override screen asked for the numeric variant id. The two routes now take the SKU, as PR 22 did for stocking and recommendations.

- `GET` and `PUT /api/product-suppliers/{sku}/{supplier_id}/terms` replace the `{variant_id}` routes (gateway and procurement). The old routes are deleted in the same change (the app has no production data).
- Procurement resolves the variant id with `variant_for_sku`: unknown or empty SKU gives 422 `sku_unknown`, several products give 422 `sku_ambiguous` (both already have Spanish text).
- The answer has `sku` and no `variant_id` (new schema `override_terms_view.v1`).
- Stored versions, idempotency scope and target, and the change-event key stay keyed by variant id internally; terms saved before stay reachable by SKU.
- The `terms.override_saved` and `terms.refused` audit entries show `<sku>:<supplier_id>`.
- Web: `OverrideEditor` asks for the SKU (`SKU del producto`), `client.ts` calls the SKU route, the glossary exception for `suppliers.override.variant` is gone.

## Checklist

**Data**

- [X] Fixtures are synthetic (`SYN-0001`, supplier names from the test helpers)
- [X] Nothing new is stored; no free text

**Security**

- [X] No secrets; no ERP request; Siweb allowlists untouched
- [X] Roles unchanged (all roles read, only buyer saves); `If-Match` and `Idempotency-Key` behave as before
- [X] A NUL byte in the SKU is refused by the shared guard (`invalid_input`)

**Cost**

- [X] No new resource; no cost change

**Contracts**

- [X] Schema, baseline, generated Python and TypeScript, and matrix entries first; `python -m gates run --gate contracts` passes
- [X] Breaking rename of two gateway paths; the only consumer (web) changes in this PR. Details in `agent-00-contract-note.md`

**Quality**

- [X] New tests: `services/procurement-service/tests/test_terms_sku_014.py`, `services/api-bff/tests/test_terms_sku_014.py`, `packages/contracts/tests/test_override_terms_view.py`, web unit tests; older tests moved to the SKU path
- [X] Spanish text via translation keys

## Not covered here

- Browser: the two supplier specs (`suppliers-terms-journey`, `suppliers-manage`) pass, 17 tests, on a local dev server including a new SKU journey test. The rest of the e2e suite was not run.
- The security gate fails here only for a missing `siweb_mock` module (environment).
- Overlap with feature 012 T050 / PR 24: only the override screen is changed here.
