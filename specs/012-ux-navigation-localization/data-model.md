# Data Model: UX, Navigation & Spanish Localization

No stored business data is created or changed. The entities below are static application assets and review artifacts.

## Navigation entry (existing, `apps/web/src/app/routes.ts`)

| Field | Meaning | Rule |
|---|---|---|
| id, path | Stable identifier and address | Unique; path is Spanish |
| labelKey, descriptionKey | Catalogue keys for label and description | Must exist in the catalogue |
| group | One of seguimiento, compras, configuracion, administracion | Fixed set |
| icon | Icon name | Must exist in the icon set |
| roles | Roles allowed; empty means any signed-in role | Decides what is offered; backend stays the authority |
| feature | Optional capability the application must report | Offered only when reported |
| order | Position within its group | Unique within group |

## Translation catalogue entry (existing, `apps/web/src/i18n/es-ES.json`)

| Field | Rule |
|---|---|
| key | Dotted, area-prefixed; unique |
| value | Non-empty Spanish (es-ES); no free-text ERP note content; placeholders use named variables |

Checks: every key used in code exists; no unused keys; every stable error code has `errors.<code>` with a next step; no value contains a forbidden glossary variant.

## Glossary term (new, `apps/web/src/i18n/glossary.json`)

| Field | Rule |
|---|---|
| concept | Stable key, for example `safety_stock` |
| term | The one preferred Spanish term |
| forbidden | Variants that must not appear in catalogue values |
| definition | One or two Spanish sentences, reused by contextual help |

## Screen state (derived, per screen)

| State | Required content |
|---|---|
| loading | Placeholder matching the layout; no layout shift |
| empty | Reason (nothing loaded, filters too narrow, no permission) and the relevant action |
| error | Spanish message from the error code, retry, input preserved, no technical detail |
| success | Normal content |

## Audit inventory item (review artifact, `evidence/audit-inventory.md`)

| Field | Rule |
|---|---|
| area | Navigation, product journey, supplier journey, text, formats, states, help, accessibility, responsive |
| item | The thing checked |
| status | complete, partial, broken, missing or unverified |
| evidence | File and line, or test name |
| decision | reuse, fix or build, with the task that covers it |
| owner | The feature that owns the file (for the Agent 00 note) |

## Relationships

A navigation entry points to one screen; each screen exposes the four screen states; every user-visible text in a screen resolves to a catalogue entry; catalogue values and help text use glossary terms; each audit item references a navigation entry, screen or catalogue area.
