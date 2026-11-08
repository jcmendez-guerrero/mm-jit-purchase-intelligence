# Data Model: MMI 003 — Modern Web Interface

No server-side data, schema or migration is added. These are the client-side structures the interface depends on. Business entities (products, suppliers, proposals, etc.) are unchanged and owned by features 001 and 002.

## Navigation item (static registry)

Single source for the sidebar/drawer, the quick-jump palette, the route table and not-found handling.

| Field | Type | Rules |
|---|---|---|
| `id` | string | Unique, stable (`panel`, `calidad`, `proveedores`, `costes`, `propuestas`, `escenarios`, `importaciones`, `configuracion`, `administracion`) |
| `path` | string | Unique, starts with `/`, Spanish slug equal to `id` |
| `labelKey` | string | Translation key; must exist in `es-ES.json` |
| `descriptionKey` | string | Translation key for the page header context line and palette hint |
| `group` | enum | `seguimiento` \| `compras` \| `configuracion` \| `administracion` |
| `groupLabelKey` | string | Derived from `group` |
| `icon` | icon id | Must exist in the icon set |
| `roles` | list of role ids | Empty = any signed-in role; `administracion` requires `admin` |
| `order` | integer | Order within group |

Validation (unit-tested): ids and paths unique; every key resolves; every `icon` exists; every group has at least one item; roles reference known role ids.

## User interface preference (browser-local)

| Field | Type | Values / default |
|---|---|---|
| `appearance` | enum | `system` (default) \| `light` \| `dark` |
| `density` | enum | `comfortable` (default) \| `compact` |

Stored in `localStorage` under the keys in [contracts/ui-contracts.md](contracts/ui-contracts.md). Invalid or missing values fall back to defaults. No identifiers, no business data, no server sync.

## Status vocabulary

| Field | Type | Rules |
|---|---|---|
| `domain` | enum | `risk` \| `cost_write` \| `quarantine` \| `approval` \| `import` \| `scenario` \| `tag` |
| `code` | string | Value as returned by the existing APIs; unknown codes render a neutral "unknown" badge and are logged in tests |
| `labelKey` | string | Translation key |
| `tone` | enum | `neutral` \| `info` \| `success` \| `warning` \| `danger` (mapped to colour tokens per theme) |
| `icon` | icon id | Always present (status is never colour-only) |

The `tag` domain holds labels that are not workflow statuses but still need an icon and a word: supplier flags (preferred, disabled), where a value comes from, the forecast-estimate caveat, a changed recommendation and the required-column marker. Validation (unit-tested): every known code of every domain has label, tone and icon; text/background token pairs meet 4.5:1 in both themes.

## Screen state

A data screen is always in exactly one of these states; a shared `ScreenState` wrapper renders the non-ready ones.

| State | Trigger | Presentation |
|---|---|---|
| `loading` | First request in flight | Skeleton matching final layout; `aria-busy` |
| `ready` | Data available | Screen content |
| `empty` | Request succeeded, no rows | Explanation, next step (clear filters / import data) |
| `error` | Request failed | Message in Spanish, retry action; rest of screen remains usable |
| `no_access` | Role not permitted for the route, or the server refuses a load with HTTP 403 | "Sin acceso" explanation (the no-permission sentence), link to the dashboard; no retry |
| `session_expired` | 401 from the API, confirmed by the session probe | Banner with route to sign in again |

Transitions: `loading → ready | empty | error`; `error → loading` (retry); `ready → loading` on refetch keeps current rows visible (stale-while-revalidate) and shows a subtle busy indicator, never replacing data with a skeleton.

## Notice (transient)

`id`, `tone` (`success` | `info` | `warning` | `error`), `messageKey` + params, `createdAt`, `autoDismissMs` (≥ 6000, paused on hover/focus). Errors that block progress are not notices; they stay inline.

## Confirmation request

`titleKey`, `objectLabel` (e.g. supplier, item, amount, already formatted for es-ES), `effectKey`, `confirmLabelKey`, `tone` (`default` | `danger`). It is a presentation wrapper: confirming calls the existing handler with the original arguments.
