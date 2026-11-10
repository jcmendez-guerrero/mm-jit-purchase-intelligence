# Research: Administration, Identity & Operations (010)

Feature spec: [spec.md](spec.md). Evidence inventory (FR-001) is section 1; design decisions are section 2.

## 1. Baseline inventory (latest main, file evidence)

Classes: **complete** (works, tested), **partial**, **missing**, **unverified** (code seen, behaviour not proven here).

| Capability | Class | Evidence | Gap |
|---|---|---|---|
| Durable roles (restart-safe) | complete | `services/api-bff/src/db/roles.py` (`RoleStore`, `user_roles`), migration `0001_roles.py`, `tests/test_roles_persistence.py` | none; add a full-stack restart check to the quickstart |
| Role change + audit + mirror-outbox in one transaction | complete | `db/roles.py:73-100`, `tests/test_role_mirror_outbox.py` | none |
| Mirror retry with bounded backoff, max attempts | complete | `db/roles.py:168-175` (30 s base, 1 h cap), `worker.py:19` (`MAX_ATTEMPTS = 8`) | "failed" is not yet shown as a dead-letter list with reason (FR-014) |
| Mirror status + manual retry | complete | `routes/admin_roles.py:91-100`, `db/roles.py:178-192` | retry has no fresh-MFA guard (FR-008) |
| Approver eligibility and separation of duties | complete | `procurement-service/src/approvals/workflow.py:31-69` (`no_eligible_approver`, creator and last editor excluded) | confirm minimum-approver value used by FR-006 |
| Role-change guards (invalid role, last admin, minimum approvers) | unverified | `db/roles.py:78-88` raise `RoleError(code)`; codes not inspected | test each code against FR-006 |
| Concurrent edit conflict | missing | `RoleUpdateRequest` has no expected revision | add optional `expected_revision` → 409 |
| Fresh MFA on approve, cost release, override, dataset activate/rollback | complete | `routes/api.py:315`, `costs.py:58,73`, `imports.py:70,101`, `tests/test_sensitive_fresh_mfa.py` | none |
| Fresh MFA on role change, mirror retry, re-runs | **missing** | `admin_roles.py:103-105` and `admin_status.py:66-85` use `require_roles("admin")` only | add `require_fresh_mfa()` (FR-008) |
| Hash-chained audit with verification | complete | `audit.py:40-66`, `tests/test_audit_chain.py`; procurement has its own chain `procurement-service/src/audit/chain.py` | — |
| Audit viewer, filters, verify and export | **missing** | `RoleStore.audit_view` (`db/roles.py:140`) is used by tests only; no route, no screen | FR-011 |
| Refusals audited | partial | roles and re-runs record refusals; `tests/test_rbac_refusals.py` | check every new route (FR-021) |
| Source freshness, import jobs, model runs, policy history | complete | `routes/admin_status.py:51-59`, `AdminStatusScreen.tsx`, `tests/test_admin_status.py` | staleness limit is a web constant (`STALE_AFTER_HOURS`), not configurable (FR-013) |
| Job re-run, idempotent and audited | complete | `admin_status.py:66-86`, `tests/test_admin_rerun.py` | MFA missing (above) |
| Queue / dead-letter visibility | **missing** | poison handling lives in the shared dispatcher; `docs/runbooks/poison-queue.md` is manual | FR-014 |
| In-app alerts (de-duplicated, acknowledgeable) | **missing** | only Azure Monitor e-mail rules: `infra/bicep/modules/alerts.bicep`, `budget.bicep` | FR-017 |
| Backup / restore-drill status | **missing** | `docs/runbooks/restore-drill.md` only (RPO 24 h, RTO 4 h) | FR-018 |
| Azure cost | partial | `admin_status.py:45-48` returns budget and a static `MMI_COST_ESTIMATE_EUR`; no month-to-date or projection | FR-019 |
| Override not released by the admin who set it (FR-009) | unverified | constitution v1.3.0 and `routes/costs.py:73` guard the override; the same-person release rule was not seen in the BFF | regression test (T057) |
| Bounded retry for import and forecast jobs (FR-016) | unverified | only the mirror outbox bound was seen (`worker.py:19`) | test in T058 |
| UTC plus original timestamp string on audit entries (FR-023) | unverified | `audit_events` showed no original-string column | test in T059; add a column in T004 if missing |
| Spanish UI | complete | `i18n/es-ES.json` has `admin.status.*` | extend for new screens (FR-020) |
| Sensitive-data hygiene (no tokens or notes in logs) | unverified | `routes/admin_roles.py:124` logs the exception type only | add a scan test (SC-008) |

## 2. Decisions

**D1. Alerts are stored in the BFF schema and evaluated by the existing scheduled worker, not by an always-on service.**
Rationale: scale-to-zero budget (EUR 120). The worker already runs `python -m worker`; add an `alerts` pass. The console also evaluates on read so an administrator never sees a stale list. Alternatives: Azure Monitor only (no acknowledgement, no console state); a new always-on evaluator (violates the budget rule).

**D2. Alert de-duplication: one row per (condition, subject); re-evaluation updates `last_seen_at`; closing sets `closed_at`.** External delivery reuses the existing Azure action group (e-mail): on each opening the app logs one marker `ADMIN_ALERT_OPENED condition=<code> subject=<code>` (the same stable-marker pattern as `SYNC_FAILED` and `ROLE_MIRROR_LAG`), and one new rule in `infra/bicep/modules/alerts.bicep` matches it. The app writes the state and the console shows it. `delivery_configured` is true when the deployment sets `MMI_ALERT_EMAIL_CONFIGURED=1` (set by the Bicep deployment when an alert e-mail parameter exists); otherwise `delivery_unconfigured` is raised. Alternative: send from the app (needs credentials in the app; rejected).

**D3. Backup, cost and queue figures are ingested as read-only snapshots; the app never calls Azure Cost Management or Backup APIs.** A scheduled pipeline step or operator command supplies a JSON snapshot, and the worker validates and stores it. Rationale: least privilege (constitution I), no new cloud identity, synthetic fixtures for tests. Alternative: managed identity with Cost Management Reader (adds a permission and an outbound dependency; deferred).

**D4. Dead letters are a view, not a new store.** The role-mirror outbox row in state `failed` is a dead letter. Import jobs and forecast runs already carry states. Message-bus poison counts arrive in the `queues` ops snapshot (D3) and the queue view merges the latest valid one as items of kind `message` (a stale snapshot is marked stale), until a service exposes a safe read; this avoids cross-service SQL.

**D5. Audit view reads only the BFF chain in v1.** Procurement's chain is verified by its own service; exposing it through the BFF is raised with Agent 00 as an open contract question (OQ-1), not built here.

**D6. Audit export is capped (10,000 rows) and says so; it needs fresh MFA, admin role, and writes its own audit entry.** Rows contain actor id, action, entity, outcome, UTC time; never before/after free text.

**D7. Optimistic concurrency on role change via optional `expected_revision`.** A missing value keeps today's behaviour so existing callers stay valid; the screen always sends it.

**D8. Staleness and alert thresholds are configuration with safe defaults** (source stale 36 h as in `alerts.bicep`, backup older than 26 h, budget 80 % warning and 100 % critical, mirror lag 15 min), editable only by admin with fresh MFA.

**D10. Snapshot input location (resolves OQ-2 by default).** The worker reads `ops-inputs/*.json` (a new gitignored folder; task T046 adds it to `.gitignore`), written by an operator command or a scheduled pipeline step. Real figures never enter the repository; tests use `packages/testing/fixtures/ops/`.

**D9. Sensitive-data scan is a test, not a runtime filter.** A test collects audit rows, logs and exports from the suite fixtures and fails on token, secret, e-mail-like or free-text patterns (SC-008).

## 3. Open questions (not blocking)

- **OQ-1**: Should procurement's audit chain appear in the same console? Raise with Agent 00 (shared contract).
- **OQ-2**: Resolved by D10 and D14 (operator command or input folder).
- **OQ-3**: The required minimum number of eligible approvers is read from the approval rules; confirm the value when the FR-006 tests are written.

## 4. Convergence decisions (2026-11-11)

- **D11 (T071, FR-016).** Automatic bounded exponential retry applies to the role-mirror outbox only (30 s base, 1 h cap, 8 attempts, then dead-lettered). Import and forecast failures are not retried automatically: they are manual, idempotent re-runs by an administrator (the owning service refuses a job that is not re-runnable, `import_job_not_rerunnable`). FR-016 is read that way; adding automatic retries to those jobs would be a change in forecast-service, outside this feature's owned area.
- **D12 (T072, FR-023).** Audit entries get their time from the service clock and store it as UTC (`audit_events.ts`, asserted by `test_audit_times_are_stored_in_utc`). There is no source string to preserve, so no `ts_original` column is added. The original string is kept where one exists: `ops_snapshots.captured_at_original`.
- **D13 (T069, FR-022).** `ops_snapshot.v1.schema.json` stays in this feature's `contracts/` as the documented shape. The BFF validates snapshots with its own Pydantic model (`services/api-bff/src/ops/snapshots.py`), the only consumer; the producer is a platform script that can validate against the same JSON schema. Promotion to `packages/contracts/dto/` (with generated types and the baseline) is left to Agent 00 if a second consumer appears.
- **D14 (T066, OQ-2).** Snapshots reach the BFF in one of two ways: `python -m worker snapshot <file>` (validates and stores one file; exit 1 on refusal) or the scheduled pass reading `ops-inputs/*.json`. The platform (pipeline or operator) produces the JSON; the repository never holds real figures.
- **D15 (T068, FR-017).** "Fails repeatedly" means a failed job must be seen on `job_failed_observations` consecutive evaluations (default 2, setting range 1 to 20) before an alert opens; a recovery resets the count (`alert_observations`).
- **D16 (T065, US4).** The scheduled worker now performs the complete evaluation with the BFF service identity restricted to the `viewer` role (read-only), so stale-source and failed-job alerts and their log marker no longer depend on the console being open.

