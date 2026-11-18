## What and why

Jira [MMI-12](https://mundomascotix.atlassian.net/browse/MMI-12): the e2e check "reference task 3 by keyboard: edit one supplier term and save it" saved lead time `3` instead of `7` and was quarantined with `test.fixme`, so the `e2e` gate could not prove that a keyboard-only buyer can edit a supplier term. Spec: `specs/017-fix-supplier-terms-keyboard-edit`. Tasks T001–T019.

**Root cause (screen, already fixed):** the terms form was editable before the saved terms arrived, and the late response replaced what had been typed. `e0e8b18` locks the form until the terms load and keeps the loader independent of `t`; it reached `origin/main` but not the MMI-5 branch where the check was quarantined. Removing the lock and the test's load wait brought the failure back (`Expected: 7, Received: 3`, 1 of 10 runs). See `research.md`.

**This change is tests and spec documents only; no application code changed.**

- **Check active again:** `test.fixme` removed; the load wait now waits for the field to be enabled instead of for a value.
- **Second race, test only:** the first Tab was pressed before the supplier list rendered, which failed 2–5 of 80 runs under 7 workers ("element not reachable with the keyboard"). The test now waits for the supplier button first.
- **New regression cases:** money term "Pedido mínimo (€)" by keyboard (decimal comma) and by mouse, saving the same value; a delayed-terms case (fields disabled until the terms load, then a keyboard edit is kept) that fails if the lock is removed; unit cases for the payload, invalid lead time and an untouched form; a unit case that the fields stay locked until the terms load (fails without the lock).
- **Docs:** spec, plan, research (root cause), tasks, quickstart results; the 013 PR note now says MMI-12 is resolved.

**Evidence:** keyboard check 20 of 20; the four supplier-terms cases 4 × 80 runs, 320 of 320; `npm test` passes; full Playwright run 273 passed, 14 skipped (env-gated, none for this check); `tsc` and `eslint` clean. `python -m gates run --gate e2e` shows no failure but reports `not_run`, because its last step needs the live compose stack (`PLAYWRIGHT_BASE_URL`), which was not started.

**Not done:** SC-003 (a person timing the edit) and the live-stack Playwright step. `feature-status.*`, `verification.md` and the 012 evidence still describe the 2026-11-15 failure; they are dated records and `feature-status.*` looks generated, so they were not edited by hand.

## Checklist

**Data**

- [X] No real exports, raw API responses, SKUs, suppliers, prices, names or e-mails; fixtures are synthetic ("Proveedor Sintético A")
- [X] Fields not needed are discarded before storage (`supplier_cif`, free-text notes): no change

**Security**

- [X] No secrets, tenant/subscription/app IDs or real `.bicepparam`/`.tfvars` values
- [X] Siweb access still limited to the allowlists; this change adds no ERP request (the terms API is mocked in the tests)
- [X] Authorisation and separation-of-duties rules unchanged; the existing viewer read-only test still passes

**Cost**

- [X] No new always-on resource; no impact on the shared EUR 120/month

**Contracts**

- [X] No JSON Schema, OpenAPI or service change; nothing to version

**Quality**

- [X] Tests added or updated (including the failure race and the delayed load)
- [X] User-facing text is in Spanish via translation keys; no new text
- [X] Constitution and applicable ADRs checked
