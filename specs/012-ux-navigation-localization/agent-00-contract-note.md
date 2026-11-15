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

## Requests for Agent 00 (not changed by this feature)

- **SKU-to-variant lookup.** Three screens still ask the user for the Siweb variant id (`OverrideEditor.tsx`, `SafetyStockSection.tsx`, `DemandSection.tsx`). Project rule 5 says users see and enter the SKU. A read-only lookup in the gateway (SKU in, variant id out, from the synced catalogue) would let the screens switch. This feature adds no endpoint (FR-016); the gap is listed as a known limitation.
