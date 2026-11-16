# Requests to service owners: show the SKU, never the Siweb variant id (feature 012, T067)

Why: project rule 5 says people see and enter the SKU, and Siweb ids stay inside the platform. Feature 012 changes only the web app (FR-016), so these four changes need the owners of the services below. Each needs its own PR with the JSON Schema first (rule 9); Agent 00 registers the matrix entries when they exist. PR 22 already did the same for the stocking, override and recommendation routes ("the ERP variant id is resolved inside procurement and never shown"), so it is the pattern to follow.

On the web side, a shrink-only test (`apps/web/tests/unit/no-variant-id-display.test.tsx`, baseline `variant-id-display.baseline.json`) lists the screens that still render the id; each request below lowers it when it lands.

## 1. Data-quality items carry the SKU (Jira [MMI-13](https://mundomascotix.atlassian.net/browse/MMI-13))

- **Where:** `GET /data-quality/import-errors` (`services/api-bff/src/routes/api.py`, line 161). The rows come from `import_errors`, written by `services/siweb-connector/src/mapping/quality.py`. Owner to confirm: the service that serves `import_errors` (inventory) and the api-bff route.
- **Change:** add `sku: string | null` to each item (null when the variant has no SKU in the synced catalogue), next to `variant_id`.
- **Web screen after it lands:** `QualityScreen.tsx` (2 places) shows the SKU instead of "Variante #id". Baseline entry removed.
- **Done when:** the schema and the contract tests include `sku`, and a row for a known variant returns its SKU.

## 2. Policy history carries the SKU (Jira [MMI-14](https://mundomascotix.atlassian.net/browse/MMI-14))

- **Where:** `policy_history` in `GET /admin/status` (`services/api-bff/src/routes/admin_status.py`, line 57), served from procurement or forecast (owner to confirm).
- **Change:** add `sku: string | null` to each history row that has a `variant_id`.
- **Web screen after it lands:** `AdminStatusScreen.tsx`, the policy history column. Baseline entry removed.
- **Done when:** schema and contract tests updated; the column shows the SKU.

## 3. Scenario changes and lines carry the SKU (Jira [MMI-15](https://mundomascotix.atlassian.net/browse/MMI-15))

- **Where:** `changes` and the result lines of a scenario (`services/procurement-service/src/scenarios/store.py`, `explain_changes`, line 100). Procurement already keeps `product_refs` (`src/db/tables.py`, line 130), which has the SKU.
- **Change:** add `sku: string | null` to each change and each line, next to `variant_id`.
- **Web screen after it lands:** `ScenariosScreen.tsx` (2 places: the change rows and the line table). Baseline entry removed.
- **Done when:** schema and contract tests updated; both places show the SKU.

## 4. A SKU route for the product-supplier overrides (Jira [MMI-16](https://mundomascotix.atlassian.net/browse/MMI-16))

- **Where:** `GET` and `PUT /product-suppliers/{variant_id}/{supplier_id}/terms` (`services/api-bff/src/routes/api.py`, lines 222 and 233), forwarded to procurement (`src/clients/procurement.py`, lines 41 and 47). The screen asks the person to type the numeric variant id.
- **Change:** take the SKU in the path (`/product-suppliers/{sku}/{supplier_id}/terms`), resolve the variant id inside procurement, and never return it. Keep the old route until the web app has moved, then remove it.
- **Web screen after it lands:** `OverrideEditor.tsx` asks for the SKU; the `KNOWN_EXCEPTIONS` entry in `apps/web/tests/unit/glossary.test.ts` goes away (T050).
- **Done when:** schema, OpenAPI and contract tests cover the SKU route; an unknown SKU returns a stable error code that has a Spanish message.

Request 4 is done in spec 014 (MMI-16): the route takes the SKU and the override screen asks for it. Opened on 2026-11-16 as tasks under the epic MMI-1, unassigned: the owners (marked "to confirm" above) still have to take them.

## Order

Requests 1 to 3 are independent. Request 4 can follow the pattern of PR 22. The web changes (T050, T054) wait for each one; none needs to wait for the others.
