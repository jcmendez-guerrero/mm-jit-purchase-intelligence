# Quickstart: validating MMI 003 — Modern Web Interface

All scenarios use synthetic data and mocked or local backends. Never point the app at a real Siweb host.

## Prerequisites

- Node ≥ 20, dependencies installed in `apps/web` (`npm ci`).
- Playwright browsers installed once (`npx playwright install`).
- Run from `apps/web`.

## 1. Fast checks (every change)

```bash
npm run typecheck
```

```bash
npm run lint
```

```bash
npm test
```

Expected: all pass, including the i18n coverage, hard-coded-string baseline and the new unit tests for the route/navigation registry, status vocabulary, preferences and primitives.

## 2. Build and budgets

```bash
npm run build && npm run check:bundle
```

Expected: build succeeds; JS stays within the budgets in `package.json` (total ≤ 350 kB gzip, charts ≤ 160 kB gzip); fonts are emitted as same-origin files under `dist/assets`; `dist/index.html` contains no `fonts.googleapis.com` or `fonts.gstatic.com`.

## 3. End-to-end and accessibility

```bash
npm run e2e
```

Expected, per success criterion:

| Check | Criterion |
|---|---|
| Each role reaches every permitted screen within 2 interactions; restricted section shows no-access on direct address | SC-001, FR-001, FR-020 |
| Reload, bookmark and back/forward return to the same screen; `?almacen=` reproduces the dashboard view | FR-002 |
| axe (WCAG 2.2 A/AA) has no serious or critical violations on every screen, light then dark once shipped; keyboard-only run of the three reference tasks completes | SC-003, FR-026 |
| No horizontal page scroll at 768×1024, 1024×768, 1280×800 and 1920×1080; 200 % zoom has no clipped content | SC-004, FR-021, FR-025 |
| Zero cross-origin requests during a full page load | SC-006, FR-009 |
| Every data screen shows loading, empty and error states with retry | SC-008, FR-013 |
| Existing flows (proposals export, suppliers, policies, imports, scenarios, roles, admin) pass unchanged | SC-007, FR-027 |
| Dashboard first meaningful view within 2 s (existing perf spec, throttled profile) | SC-005 |

## 4. Manual review with synthetic data (before each phase release)

1. Start the dev server (`npm run dev`) with the mocked backend used by the e2e helpers.
2. Sign in with each development role (viewer, buyer, approver, admin) and walk the nav groups; confirm the current screen is always highlighted.
3. Press `Ctrl/Cmd+K`, type part of a screen name (with and without accents), press Enter.
4. On the dashboard, click a ruler segment to filter the risk table to that severity and click it again to clear; with a category filter active, confirm the ruler shows only the total. Then on the proposals and dashboard tables: sort a column, switch density, scroll to confirm the sticky header and first column.
5. Edit a supplier term with an invalid value: message appears beside the field and focus lands on it; try to navigate away with unsaved changes; save and confirm the notice.
6. Trigger approval or cost release on a synthetic record: confirmation names the object and effect; safeguards (separation of duties, fresh authentication) behave as before.
7. Switch appearance to dark and back, reload, and set the device preference to confirm "system" follows it. Enable "reduce motion" in the OS and confirm transitions stop.
8. Print preview a proposal: navigation is hidden, content is legible.
9. Narrow the window below 1024 px: the rail becomes a menu button and a drawer with the same destinations; the header shows the isotipo. Check a tablet width (768 px) on every screen for horizontal page scroll.
10. On a proposal with many lines, page through the lines: each supplier's header repeats (marked as continued) when it spans pages, and its subtotal appears on the page where its lines end.
11. Make a screen refuse a load with HTTP 403 (for example by removing the role in the mock): the screen explains the refusal with the no-permission sentence and a link to the dashboard, with no retry.
12. Go through every confirmation and check that it names the object and effect, that cancel sends nothing, and that confirm sends the request the screen always sent: approve and submit a proposal, release a cost, set an admin cost value, release and ignore a quarantined movement, reject an upload, activate and roll back an import, promote a scenario, change a role.
13. On proposals, scenarios, suppliers, imports, costs and the purchasing policy, confirm the primary action sits in the page header and still works from the keyboard.
14. Open each of the nine screens in the dark appearance and look for unreadable text, invisible borders or chart colours that do not follow the theme.

## 5. Team clarity check (SC-002)

Run a 15-minute moderated session with the purchasing team on the three reference tasks (find a product at risk, review and submit the weekly proposal, edit one supplier term). Record each participant's rating of the new interface versus the old as clearer / same / worse, and any task that felt harder. Target: ≥ 80 % "clearer" or "much clearer", none "harder". Record the outcome in the pull request, without screenshots of real data.

## 6. Container configuration check

Build the web image and request `/` and a deep link such as `/costes`; the response must be the SPA shell, and the `Content-Security-Policy` header must not list third-party font hosts.
