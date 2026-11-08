# Design Specification: MMI 003 — Modern Web Interface

Companion to [spec.md](spec.md) (what and why) and [plan.md](plan.md) (how it is built). This document fixes the **visual and interaction direction**: it is the reference for the tokens in `apps/web/src/styles/tokens.css` and for the look of every primitive in `apps/web/src/ui/`. It changes presentation only; nothing here adds a capability, API or data.

**Binding input**: the client's brand identity manual ("Manual de identidad visual — Logotipos, colores y tipografías de Mundo Mascotix"). Where this document and the manual differ, the manual wins, except for the documented accessibility adaptations in section 3.

## 1. Subject, audience, job

- **Subject**: the purchasing console of Mundo Mascotix, a veterinary pharmacy and pet shop. Siweb360 is the ERP; MMI turns its stock and movement data into a weekly purchase proposal that a human approves.
- **Audience**: a few staff. A buyer (daily), an approver (weekly), an admin (rarely), viewers. Pharmacy-trained, comfortable with tables and numbers, not software people. They work between the counter and the screen, sometimes on a tablet in the storeroom.
- **Primary job**: see at a glance what will run out before the next delivery, then review and release the weekly order with confidence. Everything else (suppliers, costs, imports, policies, admin) serves that loop.

## 2. Brand manual rules and how this design applies them

| Manual rule | Application |
|---|---|
| Five colours: Azul petróleo `#016581` (principal: titles, buttons, key elements), Azul medio `#2F8198` (links, icons, lines, gradients), Turquesa `#60ABB8` (accents, charts, details), Azul noche `#002028` (body text, dark backgrounds), Blanco hielo `#F2F8F9` (light backgrounds, support blocks) | These are the whole palette. Page background is Blanco hielo; working surfaces are white; text is Azul noche; titles and primary actions are Petróleo |
| Proportion: Petróleo predominates; Azul medio and Turquesa support; Azul noche and Blanco hielo for text and backgrounds | Primary buttons, current navigation item, titles and the main data colour are Petróleo; Azul medio for links, icons and rules; Turquesa for chart series, the ruler's accents and small details |
| Typefaces: Bricolage Grotesque Bold for titles, Inter for running text | Exactly these two, self-hosted (the manual's Google Fonts are free OFL fonts; self-hosting keeps the licence and removes the third-party request) |
| Hierarchy: main title Bricolage Bold in Petróleo; subtitles Bricolage Bold in Azul medio; body Inter Regular in Azul noche; details and notes Inter Regular, smaller, in Azul medio | Followed (with the contrast adaptation below) |
| Logo on white or Blanco hielo; free margin around it at least the height of the "M"; never deformed, rotated, recoloured, shadowed or given effects; use the isotipo (paw) alone when the full logo is too small | The logo always sits on a white plate in its original colours with the clear-space margin; the isotipo is used where the horizontal logo would be too small (narrow header, favicon). No recoloured or reversed logo is created |

### Accessibility adaptations (flag to the client)

Contrast was computed for the manual's colours:

| Pair | Ratio | Decision |
|---|---|---|
| Petróleo on white / on Blanco hielo | 6.6 / 6.2 | Fine for all text and for buttons with white text |
| Azul noche on Blanco hielo | 15.8 | Fine |
| Azul medio `#2F8198` on white / on Blanco hielo | 4.45 / 4.15 | Below 4.5 for small text. Used as is for icons, rules, links in large or bold sizes (≥ 19 px bold) and graphics (≥ 3:1). For small text (notes, details, links at body size) use the slightly darker `#2A778D` (5.1 on white, 4.75 on Blanco hielo), the value the app already uses today |
| White text on Azul medio | 4.45 | Buttons and fills with white text use Petróleo, not Azul medio |
| Turquesa `#60ABB8` on white / on Blanco hielo | 2.6 / 2.4 | Never for text or for meaningful graphics on light surfaces. Allowed for decorative fills and, together with a Petróleo outline or label, in charts. On Azul noche it is 6.5 and fine |

The automated contrast test (T063) is the standing guard for these pairs.

## 3. Analysis of the current app

Evidence: the code in `apps/web/src` and a live view of the dashboard shell at 800 px (the backend was not running, so data-heavy states were reviewed from code only).

| Finding | Evidence | Consequence |
|---|---|---|
| Nine tabs in a petróleo bar wrap onto two rows at 800 px; the active tab is only slightly lighter | Live view; `Navigation.tsx` | Navigation costs vertical space and does not show structure or location |
| Development sign-in buttons ("Lector", "Comprador", "Aprobador", "Admin") sit in the header and look like navigation | Live view; `Navigation.tsx` | Confusing; must be unmistakably development-only |
| A hard-coded greeting ("Hola, Equipo Mundo Mascotix") and a subtitle joined by a middle dot take the top of every screen; no screen has its own title | `App.tsx`, live view | The page does not say where you are |
| Every screen is a white rounded card on the ice-blue page, with one radius and one shadow on everything | `index.css` | Nothing signals what matters; reads as a template |
| Five identical stat cards (inventory value, coverage days, stockout risk, expiring value, proposed spend) sit above a flat risk table; the severity of stockout risk (no stock, imminent, below reorder point) is only visible by reading table rows | `DashboardScreen.tsx`, `risk.stockout.*` keys in `es-ES.json` | No sense of proportion or urgency for the one thing the buyer must act on |
| Native-looking selects and inputs; filters as loose label-over-select pairs | Live view | Dated look, weak grouping, small targets |
| Loading is plain text ("Cargando indicadores…") and never resolves when data does not arrive | Live view | No skeleton, timeout or retry |
| Brand fonts are right (Bricolage Grotesque, Inter) but loaded from a third-party host; an emoji is the user icon | `index.html`, `index.css`, `Navigation.tsx` | Privacy, flash of unstyled text, inconsistent icon |
| Colours and spacing defined per screen, inline styles in `App.tsx` | `index.css`, `App.tsx` | The "built screen by screen" feel |
| Brand colours and logo already in use but applied loosely: white-on-azul-medio buttons, Azul medio small text near the contrast limit | `index.css` | Apply the manual's hierarchy consistently with the accessibility adaptations above |

Working-tree note: `node_modules` was incomplete (`recharts` missing); `npm ci` in `apps/web` fixes it.

## 4. Design plan

### Color tokens

| Token | Hex | Use |
|---|---|---|
| `petroleo` | `#016581` | Titles, primary buttons, current navigation item, main data colour, focus ring |
| `azul-medio` | `#2F8198` | Icons, rules, large/bold links, secondary chart series |
| `azul-medio-texto` | `#2A778D` | Small text in Azul medio's role (notes, details, body-size links) |
| `turquesa` | `#60ABB8` | Accents, chart series, the ruler's detail marks; on dark surfaces also text |
| `azul-noche` | `#002028` | Body text; dark theme background |
| `blanco-hielo` | `#F2F8F9` | Page background, table header, support blocks |
| `blanco` | `#FFFFFF` | Working surfaces (tables, forms, dialogs, the logo plate) |
| `borde` | `#D3E4E7` | Hairlines (already in the app); control borders `#6B8288` (≥ 3:1) |

Status tones are functional additions the manual does not cover (stock risk needs them). Each is a text/tint pair, always with an icon and a word: danger `#B3261E` on `#FBE9E7` (5.6:1), warning `#8A4B00` on `#FFF1D6` (6.1:1), success `#0D7849` on `#E3F4EA` (4.8:1), info Petróleo on `#E1EFF3`. They appear only when someone should act.

Dark theme ("storeroom at night"), within the manual's "Azul noche for dark backgrounds": background `#002028`, raised surface `#012B36`, text Blanco hielo (15.8:1), titles white (as the manual says for dark backgrounds), accent Turquesa, notes `#9CD3DD`. The logo stays on its white plate.

### Type

- **Bricolage Grotesque Bold** for page titles, section titles (Azul medio for subtitles, per the manual) and the large figures on the dashboard. Its width and optical-size axes are used when the self-hosted variable file provides them (verify at implementation): large titles at a high optical size for character, small headings at a low one for legibility.
- **Inter** (regular, semibold for emphasis) for body, tables, forms and notes, with `font-variant-numeric: tabular-nums` so euros and quantities align in columns.
- **Scale** (ratio 1.2, 15 px base): 12.5 · 15 · 18 · 21.5 · 26 · 31 · 37; tables 14 px (compact 13 px). Titles tight tracking (−0.01em) above 26 px; body line height 1.5; prose limited to 70 characters. Subtitles in Azul medio are 19 px or larger (bold, so they pass as large text); anything smaller uses `azul-medio-texto`.
- Numbers right-aligned in tables, euro sign and Spanish separators from the existing formatters, units in a lighter weight right after the figure.
- Because the typefaces are brand-fixed, the interface's own character comes from the layout, the proportions, the optical sizing of Bricolage and the ruler, not from font choice.

### Layout concept

A **left rail** replaces the top tabs: white, with a hairline on its right edge, the full-colour logo on top (on its white plate, with the clear-space margin), then grouped destinations. The content area is Blanco hielo with a page header and ruled sections; white is used only where people read or edit data (tables, forms, dialogs). Fewer boxes, more alignment and rules. Left-aligned everywhere; numbers right-aligned in tables; nothing centred except empty states.

```text
≥1024 px                                                          <1024 px
┌─────────┬──────────────────────────────────────────────┐      ┌──────────────────────────────┐
│ ✚ Mundo │ Panel de control                [⌘K] [☾] [JM]│      │ ☰  (isotipo)  [⌘K]  [☾] [JM] │
│ Mascotix│ Riesgos de inventario y alertas              │      ├──────────────────────────────┤
│         │──────────────────────────────────────────────│      │ Panel de control             │
│Seguim.  │ Riesgo de rotura de stock                    │      │ ▓▓▓░▒▒▒▒ ruler (stacked)     │
│ ▌Panel  │ ▓▓▓▓▓░░░░░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒  ← ruler           │      │ table (scrolls inside)       │
│  Calid. │ sin existencias 4│inminente 9│bajo pto. pedido 21│      └──────────────────────────────┘
│Compras  │──────────────────────────────────────────────│      drawer opens from the left with the
│  Prop.  │ Filtros: Almacén ▾ Categoría ▾ Proveedor ▾   │      same grouped list; closes on choice
│  Esc.   │ ┌ table (white) ───────────────────────────┐ │
│  Cost.  │ │ Producto      Cobertura  Stock   Prop.   │ │
│Config.  │ │▌Producto A    3 días     12      24      │ │   ▌ = risk band on the row edge
└─────────┴──────────────────────────────────────────────┘
```

### Principles

1. **One memorable thing**: the stockout-severity ruler on the dashboard (section 6). Everything else is quiet and disciplined.
2. **Structure is information**: a coloured band on a row's leading edge means risk level; a rule separates sections because they are different questions; the rail's group labels mirror the weekly workflow. No decoration without meaning.
3. **Soft where it touches people, square where it holds data**: pills for status, 8 px controls, 12 px panels and dialogs, square table rows. The softness comes from the wordmark and its rounded cross; tables stay exact.
4. **Pharmacy vocabulary, not software vocabulary**: "Cobertura" (days of stock), "Pedido", "Proveedor", "Lote"; actions named by their effect.
5. **Calm by default, loud only for risk**: Petróleo and Blanco hielo carry the interface; amber and red appear only when someone should act, always with icon and word.

### Review of the plan against the brief

What changed after reading the brand manual and the first review:

- *First draft*: Rubik plus Source Sans 3 — **dropped**: the manual fixes Bricolage Grotesque and Inter. Distinctiveness now comes from Bricolage's optical sizing, the layout and the ruler.
- *First draft*: dark Night-Petrol rail with a light logo variant — **dropped**: the manual forbids recolouring the logo and requires it on white or Blanco hielo. The rail is white and the logo sits on it unchanged.
- *First draft*: a cooler grey page background — **dropped**: the manual's Blanco hielo `#F2F8F9` is the background.
- *First draft*: extra neutral muted-grey text — **replaced** by the manual's Azul medio for notes (darkened for small sizes, section 2).
- *After the consistency analysis*: the ruler's first version used "critical / low / correct / excess" categories that the dashboard data does not have, and replaced cards that carry other figures. It is now built from the real stockout severity keys, replaces only the stockout card, and keeps the other four figures.
- *Kept*: cream/clay, stat-card gradients, label-style skeuomorphism and monospace codes stay rejected as generic or density-costly; the pharmacy idea lives in the ruler (a graduated cylinder) and the vocabulary.
- *Kept on purpose*: Petróleo-led palette, rounded corners echoing the wordmark, a left rail suited to nine screens and tablets.

## 5. Shell and navigation

- **Rail** (≥ 1024 px, 232 px wide, white): the horizontal logo at the top in original colours with free margin at least the height of the "M" on every side; then four groups with a sentence-case group label in `azul-medio-texto`, each item an icon plus text. The current item has a Petróleo fill, white text and `aria-current="page"`; hover is Blanco hielo. Groups: *Seguimiento* (Panel de control, Calidad y datos), *Compras semanales* (Propuestas de compra, Escenarios, Costes y proveedores), *Configuración* (Proveedores, Datos predictivos, Configuración), *Administración* (admin only). Labels stay the current screen names so the team does not relearn them.
- **Header** (Blanco hielo, no box): page title at the left; at the right the quick-jump button (shows the shortcut), the appearance toggle and the user menu (name, roles, sign out). The menu replaces the emoji and the loose sign-out button.
- **Development sign-in**: moved out of the header into a labelled "Entorno de desarrollo" strip at the foot of the rail, shown only where development sign-in is enabled (as today), in an amber tone so nobody mistakes it for navigation.
- **Below 1024 px**: the rail becomes a drawer opened from a menu button (native `<dialog>`), same grouped list, closing after a choice. The header shows the isotipo (the manual's rule for small sizes) instead of the horizontal logo; the full logo appears at the top of the drawer.
- **Quick-jump**: a centred dialog of 560 px, one input, up to eight screens with icon, name and group. The shortcut is on the button, not in a tooltip.
- **Skip link**: first focus stop, visible on focus at the top left, Petróleo on white.

## 6. The memorable element: the stockout-severity ruler

Built only from data the dashboard already loads; no new metric and no new endpoint.

- **Data**: the existing risk list (`risks`, items with `risk_type: "stockout"`) grouped by the existing severity keys — `risk.stockout.out_of_stock` ("Sin existencias"), `risk.stockout.imminent` ("Rotura inminente") and `risk.stockout.below_reorder_point` ("Stock por debajo del punto de pedido"). Its total must equal the existing `stockout_risk` count in the summary; verified in the backend: the risk list is not capped but is filtered by warehouse only, while the summary count also respects category and family. So the severity split is shown only when the list's stockout total equals the summary count; otherwise the ruler shows the summary count alone (T080).
- **Form**: one horizontal bar across the section, divided into proportional segments in order of severity (most severe first), with fine tick marks like a graduated cylinder. Fills: danger tone for no stock, warning tone for imminent, Petróleo for below reorder point. Small cross mark from the logo on the no-stock segment. Colour is never the only cue: each segment has its label, count and an icon.
- **Under each segment**: the count (Bricolage Grotesque Bold, large) and the label. Segments are buttons that filter the risk table below to that severity (client-side only, no request); activating the same segment again clears the filter. The existing "Ver productos" drill-down for stockout risk stays as a quiet button beside the ruler.
- **Empty state**: when there is no stockout risk, the bar is replaced by one calm line, "Sin riesgo de rotura de stock.", with the check icon.
- **Other figures**: inventory value, coverage days, expiring value and proposed spend stay, with the same data and the same drill-downs, as a quieter row of figures (Bricolage figure, Inter label and basis line, no card box) beneath the ruler.
- **Accessibility**: segments are real buttons with an accessible name from count and label and `aria-pressed` for the active filter; the table below is the full alternative and a text summary precedes the bar (FR-014).
- **Motion**: on first load only, segments grow from the left over about 600 ms, once. Nothing else animates by itself. Under reduced motion the ruler simply appears.
- Narrow screens: the ruler stays horizontal; labels wrap beneath it in a two-column grid.

## 7. Components (look and behaviour)

| Component | Direction |
|---|---|
| Page header | Title (Bricolage Bold, 26, Petróleo), one context line in `azul-medio-texto` (no middle-dot strings), primary action at the right. No greeting. |
| Section | A rule above, a section title (Bricolage Bold 19, Azul medio), content below on Blanco hielo, or on a white panel if it is a table or form |
| Button | Primary: Petróleo fill, white text, 8 px radius, 40 px high (44 on touch). Secondary: white with Petróleo outline. Quiet: text only. Verbs only, sentence case, no arrows. Loading shows a spinner and keeps the label. |
| Inputs and selects | White fill, 1 px `#6B8288` border (3.8:1 on Blanco hielo), label above, 40 px high, custom caret; focus is a 2 px Petróleo ring with 2 px offset, same ring on every focusable element |
| Filters | One bar grouping the filter controls with a "Quitar filtros" quiet button; active filters appear as removable chips |
| Table | White panel, square rows, sticky header in Blanco hielo with Bricolage Bold 14 in Petróleo, hairline row rules, 4 px leading band for risk, right-aligned tabular numbers, hover tint, selected row with a light Petróleo tint; density toggle in the toolbar |
| Status badge | Pill, tint fill, status text colour, 16 px icon plus word |
| Dialog | Native `<dialog>`, 12 px radius, title, one sentence naming object and effect, two buttons; the risky action is not the default focus |
| Notice | Bottom-left on desktop, full width at the bottom on tablets; icon plus sentence; dismiss button; never covers primary actions |
| Skeleton | Blanco-hielo shapes matching the final layout (ruler as a bar, table as rows); slow shimmer only if motion is allowed |
| Empty / error | Left-aligned block: icon, one sentence on what happened, one on what to do, one button |
| Logo plate | White, fixed clear-space, never scaled below the size where "Mundo" stays legible; isotipo below that |

## 8. Screens

| Screen | Specific direction |
|---|---|
| Panel de control | Filters bar → stockout ruler → row of figures (value, coverage, expiring, spend) → forecast/trend chart with table alternative → supplier panel → risk table (filtered by the ruler). Warehouse in the address (`?almacen=`). |
| Calidad y datos | Quarantine list as a table with a "motivo" badge column; header line states how many records need review |
| Propuestas de compra | Proposal header strip (week, status badge, total in Bricolage) then lines grouped by supplier in one table with a body per supplier (a header row, its lines, and the server's subtotal at its foot; the table name stays stable, and money is never summed in the browser); lines are paged, 50 per page, and a supplier that spans pages repeats its header marked as continued; submit, approve and the exports are in the page header, and submit and approve confirm first, naming the week and the number of lines |
| Escenarios | Parameter form at the left (360 px), comparison at the right; stacked below 1024 px. Differences to the baseline are shown in words and numbers, not only colour |
| Costes y proveedores | Table with freshness badges; the cost-release action opens a confirmation naming product, supplier, old and new value |
| Proveedores | Master list at the left, term editor at the right; unsaved-change guard; field-level errors |
| Datos predictivos | Dataset table, then a stepped import flow where the steps really are a sequence (select file, review validation, activate) and are numbered for that reason only |
| Configuración | Section list as in-page navigation at the left, forms at the right |
| Administración | Status as a plain definition list with status badges; roles as a table with an inline change control |

## 9. Motion

- Only one motion on its own: the ruler growth on first load of the dashboard.
- Motion that answers an action is allowed and short (120–200 ms): drawer and dialog opening, row selection fill, notice entering, button loading.
- No entrance animations on sections, no hover lift on cards. All respects `prefers-reduced-motion`.

## 10. Content and microcopy (es-ES)

Sentence case; plain verbs; one name per action throughout (the button "Aprobar propuesta" produces the notice "Propuesta aprobada"). Errors say what happened and what to do and never apologise; empty states invite the next step.

| Situation | Copy direction |
|---|---|
| Loading | Skeleton, no text; screen readers get "Cargando datos" |
| Empty table | "No hay productos que coincidan con los filtros." + "Quitar filtros" |
| Request failed | "No se han podido cargar los indicadores. Comprueba la conexión e inténtalo de nuevo." + "Reintentar" |
| No access | "Tu rol no permite ver esta sección." + "Ir al panel de control" |
| Session expired | "La sesión ha caducado. Inicia sesión de nuevo para continuar." + "Iniciar sesión" |
| Unsaved changes | "Tienes cambios sin guardar. ¿Quieres descartarlos?" + "Seguir editando" / "Descartar cambios" |
| Cost release | "Vas a enviar al ERP el coste de {producto} con {proveedor}: de {anterior} a {nuevo}. Se registrará en la auditoría." + "Enviar coste" / "Cancelar" |

Direction only; final wording lives in `es-ES.json` (no hard-coded strings) and is reviewed with the team.

## 11. Accessibility, responsiveness and quality floor

- WCAG 2.2 AA in light and dark; focus ring on every interactive element; targets ≥ 24 px (44 px on coarse pointers); status never by colour alone; contrast adaptations in section 2.
- Reflow from 768 px with no horizontal page scroll; tables scroll inside their region with the first column fixed; 200 % zoom and larger text tested.
- Reduced motion and print rules per spec FR-025 and the print edge case.

## 12. Traceability

| Design element | Spec requirements |
|---|---|
| Rail, header, drawer, quick-jump, skip link | FR-001–005, 021–023 |
| Brand tokens, type, components, logo rules | FR-006–009, 015 |
| Ruler, tables, badges, states, charts | FR-008, 010–014 |
| Forms, notices, dialogs, microcopy | FR-016–020 |
| Dark theme | FR-024, 026 |
| Self-hosted fonts and icons | FR-009, SC-006 |
