# Agent 00 note: cross-feature interface changes (feature 012)

Feature 012 changes presentation, wording and accessibility only. No contract, schema, API or ERP change. Each change in a file owned by another feature, and each shared component change, is recorded here (FR-015).

| Feature | File | Change | Reason | Shared or screen-level |
|---|---|---|---|---|
| 006 | `apps/web/src/i18n/es-ES.json` | `dashboard.def.stockout_risk`: "plazo de reposición" → "plazo de entrega" | One term per concept (glossary) | catalogue |
| shared | `apps/web/src/ui/PageHeader.tsx` | `h1` gets `tabIndex={-1}` so it can take focus | Focus on the heading after a screen change | shared component |
| shared | `apps/web/src/app/AppShell.tsx` | Moves focus to the page heading after a screen change (not on load, not on the `/` redirect) | Keyboard and screen-reader users start at the top of the new screen | shared component |
| shared | `apps/web/src/i18n/formatters.ts` | `formatPercent` takes an optional `minDecimals` | Service level without trailing zero in Spanish format | shared formatter |
| shared | `apps/web/src/i18n/index.ts` | Missing-key handler shows "Texto no disponible" and respects `defaultValue` | Never show a raw key | shared i18n |
| shared | `apps/web/src/ui/HelpHint.tsx`, `src/styles/components.css`, `src/i18n/glossary.json` | New contextual-help component, styles and glossary | FR-009, FR-012 | shared component |
| 006 | `apps/web/src/features/dashboard/ProductDetail.tsx`, `i18n/es-ES.json` (`dashboard.detail.title`) | Heading "Detalle del producto · SKU · nombre" instead of "Detalle de la variante {id}" | Project rule 5: show the SKU, not the Siweb id | screen-level |
| 010 | `apps/web/src/features/admin/AuditScreen.tsx` | Loading placeholder and error state with retry | FR-011 | screen-level |
| 011 | `apps/web/src/features/policies/PurchasingSection.tsx` | History date and service level through `formatDate` and `formatPercent`; help beside the heading | FR-008, FR-012 | screen-level |
| 011 | `apps/web/src/features/policies/SafetyStockSection.tsx` | Help beside the heading | FR-012 | screen-level |
| shared | `apps/web/src/api/client.ts`, `apps/web/src/app/App.tsx` | New `onForbidden` hook: a 403 re-reads the person's roles | A role removed while a screen is open must leave the menu | shared client |
| shared | `apps/web/src/i18n/es-ES.json` | Next step added to 52 `errors.*` messages; 37 dead keys removed; new keys for help, filters and fallbacks | FR-010, FR-007 | catalogue |
| 006 | `apps/web/src/features/dashboard/DashboardScreen.tsx`, `ProductDetail.tsx`, `IndicatorCard.tsx` | Open product kept in the URL (`?producto=`), link to its proposal lines, help on coverage | US2 | screen-level |
| 002 | `apps/web/src/features/proposals/ProposalsScreen.tsx` | SKU filter (`?sku=`) with way back; no variant id fallback | US2, FR-004 | screen-level |
| 007 | `apps/web/src/features/suppliers/SupplierTermsEditor.tsx` | Help on lead time; a message clears when the value is corrected | US3, FR-012 | screen-level |
| 003, 007 | `apps/web/tests/e2e/a11y-all-routes.spec.ts`, `suppliers.spec.ts` | Wait for the supplier terms to load before typing (test timing only) | Intermittent failures that also affected the `e2e` gate | test-only |
| 010 | `apps/web/src/features/admin/AdminStatusScreen.tsx` | Loading skeleton of the dashboard shape | FR-011 | screen-level |

## Requests for Agent 00 (not changed by this feature)

- **SKU-to-variant lookup.** Three screens still ask the user for the Siweb variant id (`OverrideEditor.tsx`, `SafetyStockSection.tsx`, `DemandSection.tsx`). Project rule 5 says users see and enter the SKU. A read-only lookup in the gateway (SKU in, variant id out, from the synced catalogue) would let the screens switch. This feature adds no endpoint (FR-016); the gap is listed as a known limitation.
- **`sku` in payloads.** Quality items, the administration policy history, the safety-stock queue, demand exclusions, the policy preview and the scenario lines carry only `variant_id`, so the screens show "Variante #id". Adding a `sku` field to those payloads would let the screens drop it (guard: `no-variant-id-display.test.tsx`).
- **Audit CSV in the Spanish locale profile.** `GET /admin/audit/export` writes English field names, ISO timestamps and a comma delimiter, while the proposal exports use Spanish headers, `;`, comma decimals and `dd/mm/yyyy` (FR-008). A Spanish header row and local date format would align it; the web app only passes the file through.
- **"Variante (ID Siweb)" column in the proposal exports.** Confirm it is wanted for ERP hand-off; otherwise drop it per rule 5.

## Answer to Agent 00 on the SKU rule (T060; draft, not posted)

Compared the screens on this branch with `claude/jira-mmi-8-spec-f00d63` (PR 22, still open) and `main` (PR 18 is merged):

| Screen | Shows or asks for the variant id here | After PR 22 | What is still needed |
|---|---|---|---|
| `SafetyStockSection.tsx` | queue row; typed id | fixed (routes take the SKU) | nothing; rebase after PR 22 (T065) |
| `DemandSection.tsx` | "variante n"; typed id | fixed | nothing; rebase after PR 22 |
| `PurchasingSection.tsx` | policy preview row | fixed | nothing; rebase after PR 22 |
| `QualityScreen.tsx` | "Variante #id" (2 places) | unchanged | `sku` in the data-quality items |
| `AdminStatusScreen.tsx` | policy history column | unchanged | `sku` in the policy history |
| `ScenariosScreen.tsx` | change rows and lines (2) | unchanged | `sku` in the scenario changes and lines |
| `OverrideEditor.tsx` | typed id | unchanged | a SKU route for `product-suppliers` overrides |

So three of the nine are blocked only by PR 22 merging; four need new `sku` fields or a SKU route. This feature does not edit the three PR 22 files, to avoid conflicts.

- **Owner requests.** The four changes in services this feature does not own (data-quality items, policy history, scenario changes and lines, SKU route for overrides) are written up, schema first, in `evidence/owner-requests.md` and opened in Jira as MMI-13, MMI-14, MMI-15 and MMI-16 under MMI-1 (T067).

## After PR 22 merged (2026-11-16)

`main` (519e7c1) was merged into this branch. Conflicts: the imports of `PurchasingSection.tsx` (kept both sides) and two places in `es-ES.json` (kept the SKU queue row and the new error keys from PR 22, kept the next step added here to `errors.import_reason_invalid`, and added a next step to `errors.sku_unknown` and `errors.exclusion_reason_invalid`). PR 22 fixed `SafetyStockSection`, `DemandSection` and `PurchasingSection`, so their entries left `variant-id-display.baseline.json`; four screens remain (MMI-13 to MMI-16). `demand.variant_n` became unused and was removed; `policies.audit.refresh` and `safety.stale` (PR 22) stay in the unused-keys baseline with a reason. PR 25 is still open, so T069 stays open for `ProposalsScreen.tsx`.
