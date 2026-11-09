# PR draft: SKU-based predictive seed import with governed activation and rollback (MMI-7)

> Draft prepared for T048. Not opened yet: opening it needs a push, and this repository is public. Paste the body below into the pull request; attach screenshots in the PR itself (none are stored in the repository).

## What and why

Jira MMI-7 (epic MMI-1, "MMI 003 / Agent 05 — Predictive Seed Import & Dataset Governance"): <https://mundomascotix.atlassian.net/browse/MMI-7> · Scope page: <https://mundomascotix.atlassian.net/wiki/spaces/MMJDI/pages/3080433>

Feature 002 and ADR-020 already built most of the seed import. This PR audits that baseline against `specs/008-mmi-7-predictive-seed-import/spec.md`, closes the gaps and proves the acceptance criteria: an import changes the next forecast, rollback restores it, and imported data never becomes an ERP movement.

Tasks: `specs/008-mmi-7-predictive-seed-import/tasks.md` (81 of 83 done; T048 is this PR, T049 is the agreement with Agent 00). The audit table (complete, partial, broken, missing, unverified, with file evidence) is in `research.md`, section "Final audit table".

### Changes

- **Import by SKU.** Rows are matched by SKU through the inventory series export (new additive `sku` field); a variant id in the file is never trusted. A SKU shared by two products, or differing only by case or spaces, is quarantined as ambiguous. One lookup helper serves the API route and the worker, and a test shows the same file gives the same outcome in the request and in the background.
- **Safer uploads.** Files recognised as ERP exports and workbooks with external links are refused. The original date text is kept beside the normalised day.
- **Governance.** The uploader and the validator cannot activate; an owner/admin may self-activate with a listed reason (audited as `seed.self_activated`). Activation and rollback need fresh MFA. Simultaneous rollbacks end with one success and one `import_conflict` (proven on PostgreSQL, with the activation race).
- **Reasons.** A fixed pick-list plus an optional 100-character detail. The code is shown to everyone and audited; the detail is admin-only and never audited (owner decision recorded in the spec).
- **Observability.** The dry run is audited; refused governance attempts are logged as `SEED_REFUSED` (actor, action, dataset); seed rows for products that left the catalogue are reported.
- **Web.** SKU wording, reason pick-lists, validator, approver, provenance mix and rollback reason columns, guidance when a self-activation is refused.

### Migration impact

`services/forecast-service/migrations/versions/0005_seed_governance.py` adds nullable columns only (`seed_rows.sku`, `seed_rows.day_text`, and four reason columns plus `validated_by` and `mapping_chosen_by` on `seed_datasets`). Reversible (`alembic downgrade 0004`). Run on PostgreSQL 18.6; the repository pins 16, so CI is the authoritative check. No data migration; existing datasets keep working.

### Contract impact

Additive. `seed_dataset.v1` gains optional fields (the `approved` status stays as deprecated and unused); new `seed_dataset_summary.v1` for the list; eight new error keys in `packages/contracts/errors/error_codes.json`; the inventory series export gains an optional `sku`. Details: `specs/008-mmi-7-predictive-seed-import/contracts/seed-governance.delta.md`. The old free-text reason fields never shipped.

### Test evidence

| Suite | Result |
|---|---|
| Forecast service | 211 passed, 3 skipped (the 3 PostgreSQL tests were run separately and passed) |
| Gateway | 176 passed |
| Inventory service | 163 passed, 1 skipped |
| Contracts, fixtures package, infra | 515 passed, 22 skipped (one earlier run showed a single failure that did not repeat in four reruns) |
| PostgreSQL 18.6 | 9 migration tests, activation race and two-rollbacks race passed |
| Web | tsc and eslint clean; 464 unit tests passed |
| Playwright | 190 passed, 6 skipped |
| Lint and types | ruff clean; mypy unchanged at its 24 pre-existing errors |

### Merge order

This PR and PR 17 both append keys at the end of `packages/contracts/errors/error_codes.json` and `specs/002-mmi-operational-console/contracts/error-keys.md`. Whichever merges second is rebased (keep both sets of keys).

### Known limitations

- 23 web unit tests in four unrelated UI files fail under Node 26 (`localStorage.clear`); they fail on the unmodified code as well.
- The Playwright flows mock the backend, so they prove the screen behaviour; that the forecast changes and returns is proven by the service tests.
- A stale second factor shows the Spanish message; the app has no re-verification action.
- The proposal explanation names the dataset used, not a version number.
- A dataset in the `validated` state can be validated again before activation (documented in `research.md`).
- Alerts that match `UPLOAD_REJECTED` for the three governance keys need a matching rule for `SEED_REFUSED`.

## Checklist

**Data**

- [x] No real exports, raw API responses, SKUs, suppliers, prices, names or e-mails; fixtures are synthetic (fictional SKUs `EJ-9001` and so on)
- [x] Fields not needed are discarded before storage (notes, tax ids and e-mail columns are never stored, logged or audited; tested)

**Security**

- [x] No secrets, tenant/subscription/app IDs or real `.bicepparam`/`.tfvars` values (pattern scan run locally; gitleaks runs in CI)
- [x] Siweb access still limited to the allowlists; this change adds no Siweb request (`infra/tests/test_seed_erp_boundary.py`)
- [x] Authorisation and separation-of-duties rules tested (second approver, owner/admin override, viewer refusals, fresh MFA)

**Cost**

- [x] No new always-on resource; scale-to-zero, replica and job caps respected (`infra/tests/test_cost_guardrails.py`); no change to the shared EUR 120/month

**Contracts**

- [x] JSON Schemas updated first; compatibility check and contract tests pass
- [x] No breaking change (additive only)

**Quality**

- [x] Tests added or updated (including failure, duplicate and race handling)
- [x] User-facing text is in Spanish via translation keys
- [x] Constitution and applicable ADRs checked (ADR-020 amended)
