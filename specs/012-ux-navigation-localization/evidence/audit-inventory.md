# Audit inventory (feature 012)

Baseline: branch `claude/speckit-specify-mmi-10-ccce8a` at the head of main (commit c6f3865), 2026-11-15. Evidence is `file:line` or a test name. Status: complete, partial, broken, missing, unverified. Decision: reuse, fix, build.

Baseline tests: `npm test` in `apps/web` passes, 46 files and 552 tests.

## Navigation (T003)

| Area | Item | Status | Evidence | Decision | Owner |
|---|---|---|---|---|---|
| Navigation | Route registry is the single source for rail, quick-jump and routes | complete | `apps/web/src/app/routes.ts:34-45`, `Navigation.tsx` | reuse | feature 003 |
| Navigation | Role filtering and capability gating (`carga-local`) | complete | `routes.ts:47-53`; `tests/unit/routes.test.ts` | reuse | feature 003 |
| Navigation | Label, description and group keys exist in the catalogue | complete | `tests/unit/routes.test.ts` (resolves every key) | reuse | feature 003 |
| Navigation | Expected routes per role pinned in one matrix (viewer, buyer, approver, admin) | missing | only partial cases in `routes.test.ts` | build (T010) | 012 |
| Navigation | Current screen indicated | complete | `Navigation.tsx` NavLink sets `aria-current="page"` | reuse | feature 003 |
| Navigation | Forbidden address shows a Spanish explanation with a way back | complete | `app/NoAccess.tsx`, `ui/ScreenState.tsx` | reuse | feature 003 |
| Navigation | Unknown address shows a Spanish not-found screen | complete | `app/NotFound.tsx`, `App.tsx:147` | reuse | feature 003 |
| Navigation | Focus lands on the page heading after a screen change | broken (found) → fixed | focus stayed on the trigger; fixed in `AppShell.tsx`, `PageHeader.tsx`; `navigation.spec.ts` last test | fixed (T012, T014) | 012 |
| Navigation | Step indicator and "back to list" in the proposal review | unverified | `ProposalsScreen.tsx` | verify (T015) | feature 002 |

## Text and formats (T004)

| Area | Item | Status | Evidence | Decision | Owner |
|---|---|---|---|---|---|
| Text | JSX text and four attribute types outside the catalogue | complete | `tests/unit/i18n-coverage.test.ts`; baseline `hardcoded-strings.baseline.json` is empty | reuse | 002 |
| Text | Sentence-like literals in `.ts` files | complete | scan of `src/**/*.ts` found none (models return catalogue keys) | reuse, add a check (T009) | 012 |
| Text | Catalogue has no empty values and no missing keys in use | complete | 1,470 entries, 0 empty; keys used in code all exist | reuse | 003 |
| Text | Unused catalogue keys | partial | 95 keys with no literal reference (many are dynamic, e.g. `proposals.why.*`); no check exists | build baseline check (T009) | 012 |
| Text | Raw technical code shown to the user when a message is missing | partial | `features/admin/AuditScreen.tsx:95` falls back to the raw `reason_code`; `actor`, `action` and `entity` columns show raw codes (lines 90-94) | keep: the audit viewer shows codes by design (its subtitle says so); the screen now has loading and retry | feature 010 |
| Text | Error code coverage | complete | `i18n-coverage.test.ts` ("code has a Spanish message") | reuse | 002 |
| Text | Vocabulary variants | partial | "plazo de reposición" in `dashboard.def.stockout_risk` vs "plazo de entrega" elsewhere | fix (T030) | 006 |
| Formats | Shared `Intl` formatters for euro, number, date, percent | complete | `src/i18n/formatters.ts` | reuse | 002 |
| Formats | Percent shown with a dot decimal | broken → fixed | `features/policies/PurchasingSection.tsx:205` builds `` `${...} %` `` by hand | fix (T031) | 011 |
| Formats | Date-only strings parsed without a fixed time of day | complete (re-checked) | `SupplierTermsEditor.tsx:58,223` read timestamps (`...T00:00:00Z`), not date-only values; the raw date was `PurchasingSection.tsx:204` (fixed) | reuse | 007 |
| Formats | Amounts computed in the browser | complete | `Number(...)` only feeds `formatCurrencyEUR`, sort keys and request bodies for percentages; no money is summed or rounded (`LinksPanel.tsx:94-99`, `CostsScreen.tsx:212`) | reuse | 007 |
| Formats | CSV export headers | partial | quarantine and template files come from the API; only `auditoria.csv` is named in the browser (`AuditScreen.tsx:50`) | verify with the API owner | 010 |

## States, help, accessibility, responsive (T005)

| Area | Item | Status | Evidence | Decision | Owner |
|---|---|---|---|---|---|
| States | Screens using the shared `ScreenState` (loading, empty, error, retry) | complete for 10 of 12 | `grep ScreenState` in `features/*/*Screen.tsx` | reuse | 003 |
| States | `AuditScreen` has no loading state and no retry on error | partial → fixed | `AuditScreen.tsx:17,65` plain `role="alert"` paragraph, no skeleton | fix (T035) | 010 |
| States | `LocalLoadScreen` handles state by hand | partial | `LocalLoadScreen.tsx:140-198` EmptyState only, per-kind busy and error | reuse with a note (local-only screen) | 004 |
| States | Per-screen state test with forced loading, empty and error | missing | no `screen-states` test | build (T011) | 012 |
| Help | Contextual help next to business terms | missing → built (two headings) | no help component in `src/ui` | build (T034, T036) | 012 |
| Accessibility | Axe on every route, light and dark | partial | `tests/e2e/a11y-all-routes.spec.ts`, `a11y-screens.spec.ts` | extend (T037) | 003 |
| Accessibility | Dialog, drawer and palette focus handling | partial | `ui/dialog.ts`, `ConfirmDialog.tsx`, `AppShell.tsx:37` | verify (T039) | 003 |
| Accessibility | Chart table alternative | complete | `features/dashboard/ChartWithTable.tsx` | reuse | 006 |
| Responsive | Viewports 1280, 768, 375 | partial | `tests/e2e/responsive.spec.ts` (other sizes), `touch-targets.spec.ts` | extend (T038) | 003 |
| Bundle | Budget 350 KB gzip total / 160 KB charts | unverified | `npm run check:bundle` not run yet | verify (T041, T044) | 003 |

## Journeys (T006)

| Area | Item | Status | Evidence | Decision | Owner |
|---|---|---|---|---|---|
| Product | SKU shown in drill-down and detail, never the ERP id | complete | `tests/unit/dashboard-sku-display.test.tsx` | reuse | 006 |
| Product | Product detail heading showed the Siweb variant id ("Detalle de la variante 100") | broken → fixed | `ProductDetail.tsx:62-65`; now "Detalle del producto · SKU · nombre" (`DashboardScreen.test.tsx`) | fixed | 006 |
| Product | Dashboard → product detail → supplier/proposal → back | unverified | `ProductDetail.tsx`, `SupplierPanel.tsx`; no end-to-end test | build test (T016) | 006 |
| Product | Missing or ambiguous data explained | unverified | `ProductDetail.tsx` | verify (T016-T018) | 006 |
| Supplier | Field-level validation with catalogue keys | complete | `features/suppliers/supplierModel.ts:35-40` | reuse | 007 |
| Supplier | Unsaved-change protection | complete | `ui/useUnsavedChanges.ts`, `UnsavedChangesPrompt.tsx` | reuse | 003 |
| Supplier | Focus moves to the first error | unverified | `ui/useFieldErrors.ts` | verify (T022) | 003 |
| Supplier | Import lists rejected rows with reasons | complete | `SupplierImport.tsx`, `tests/unit/SupplierImport.test.tsx`, `bulk-outcome.test.tsx` | reuse | 007 |
| Supplier | End-to-end journey | unverified | `tests/e2e/suppliers-terms-journey.spec.ts` exists for terms only | build test (T020) | 007 |
| Roles | Non-buyer actions on product and supplier screens | partial | `tests/e2e/roles.spec.ts`, `dashboard-roles.spec.ts` | extend (T021) | 003 |
| Product / supplier | Users type the Siweb variant id instead of the SKU | broken | `features/suppliers/OverrideEditor.tsx:21,31,109` ("ID de variante Siweb"), `features/policies/SafetyStockSection.tsx:19-20,52`, `features/policies/DemandSection.tsx:21,45-46`; the API client has no SKU-to-variant lookup (`src/api/client.ts`) | blocked: needs a lookup endpoint (contract change, Agent 00). Recorded as a known limitation; guarded by `KNOWN_EXCEPTIONS` in `tests/unit/glossary.test.ts` | 007, 011 |

## Re-check after the changes

Still `unverified` (not done in this pass): proposal step indicator (T015), focus on the first error in supplier forms (T022), a dedicated end-to-end product and supplier journey (T016, T020), non-buyer actions on product and supplier screens (T021). They are listed under known limitations in `pull-request.md`.
