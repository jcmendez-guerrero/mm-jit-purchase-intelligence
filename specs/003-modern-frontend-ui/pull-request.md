## What and why

MMI 003 — Modern web interface. Presentation and interaction only: a brand-faithful design system, grouped navigation with shareable addresses, consistent tables, statuses and states, responsive layouts, consistent forms with confirmations, and a dark appearance. Tasks: `specs/003-modern-frontend-ui/tasks.md` (spec, plan, design and contracts in the same folder).

Also adds a sign-in page: a role chooser locally and Microsoft Entra ID (authorization code with PKCE, run by the BFF) on Azure. Business rules, schemas, role rules and audit behaviour are unchanged.

## Checklist

**Data**

- [x] No real exports, raw API responses, SKUs, suppliers, prices, names or e-mails; fixtures are synthetic
- [x] Fields not needed are discarded before storage (`supplier_cif`, free-text notes) — not touched
- Browser storage holds two UI preferences (appearance, table density) and nothing else; no personal or business data.

**Security**

- [x] No secrets, tenant/subscription/app IDs or real `.bicepparam`/`.tfvars` values
- [x] Siweb access untouched; the single permitted write still happens only after buyer review with fresh MFA, server side
- [x] Authorisation and separation-of-duties rules unchanged: the new confirmation dialogs only wrap the existing calls, and the end-to-end suite asserts the same requests are sent
- Content security policy tightened: `fonts.googleapis.com` and `fonts.gstatic.com` removed; fonts are self-hosted (OFL: Bricolage Grotesque, Inter) and the app makes no cross-origin request (end-to-end test). Scripts remain same-origin only (`theme-init.js`).
- New public endpoints `/api/auth/config`, `/api/auth/login`, `/api/auth/callback`. State, nonce and PKCE verifier live in a signed, short-lived HttpOnly cookie; the id_token is checked for signature, issuer, audience, nonce and expiry. Without MFA evidence the session has no fresh MFA, so approvals stay refused. The dev login guard is unchanged and the Entra routes are off while it is enabled.
- `MMI_COOKIE_SECURE` now accepts `1` as well as `true` (Bicep sent `1`, which the code ignored).
- New Bicep parameters `entraClientId`, `publicBaseUrl`, `entraClientSecretName`; the client secret is a Key Vault reference. Deployers must create the app registration (see the azure-bootstrap runbook) — not tested against a real tenant.

**Cost**

- [x] No new always-on resource; no infrastructure change. Static assets grow by about 240 kB of font files (cached); JS stays within the budgets (total 248 of 350 kB gzip).

**Contracts**

- [x] No JSON Schema, OpenAPI or event change. UI-internal contracts (routes, navigation registry, storage keys, component behaviour) are in `specs/003-modern-frontend-ui/contracts/ui-contracts.md`.
- Visible change: screens now have their own addresses (`/panel`, `/propuestas`, …); the old tab state is gone. The web container already falls back to `index.html` for unknown paths.

**Quality**

- [x] Tests added or updated: unit (primitives, registry, palette, status vocabulary, contrast of both themes, forms, dialogs, notices) and end-to-end (navigation, states, responsive, touch targets, forms and confirmations, appearance, axe in both themes on all routes, dashboard timing)
- [x] User-facing text is in Spanish via translation keys; the hard-coded-string baseline is now empty
- [x] Constitution and design document checked
- Existing end-to-end specs changed only in how they navigate (links instead of tab buttons) and in confirming the new dialogs; their assertions are unchanged.

Not done by this PR (people needed): the manual review with all four roles (quickstart §4) and the team clarity check (quickstart §5, SC-002).
