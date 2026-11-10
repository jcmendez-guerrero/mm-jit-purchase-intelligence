# Feature Specification: Administration, Identity & Operations (Agent 07)

**Feature Branch**: `claude/jira-mmi-9-spec-id-98c87e`

**Created**: 2026-11-10

**Status**: Draft

**Input**: Jira MMI-9 ("AGENT 07 | Administration, Identity & Operations", epic MMI-1) and its Confluence page 3244047. Requested as "Implement Jira MMI-9 and use as spec ID next number + 1": the next free number is 009, so this spec is **010**. The Jira text names `specs/003-agent-07/`; that number is already taken, so this directory replaces it.

## Context

Feature 002 already put much of the administration surface in place: durable user roles with a mirror to procurement, a two-approver rule, MFA step-up with a 5-minute freshness window, a hash-chained audit trail, an admin status screen (source freshness, import jobs, model runs, policy history, role mirror, a static cost estimate) and runbooks for the main failure modes. What the owner needs now is the whole administration domain **proven complete and operable**: an administrator can see and trust the state of identities, approvals, data sync, background jobs, alerts, backups and cloud spend without developer help, and every sensitive action leaves a verifiable, secret-free trace.

This feature is therefore an **audit-then-close-gaps** feature. It starts with an evidence-backed inventory of what exists on the current main (complete, partial, broken, missing, unverified, each with file evidence), reuses what works, and builds only what the inventory shows missing. Siweb360 stays the source of truth for catalogue, stock, movements and ERP costs; this feature adds no ERP request of any kind.

Out of scope: any ERP write beyond the two already permitted; sending orders to suppliers; production deployment or merge to main; changes to files owned by other agents (shared contracts go through Agent 00); a general-purpose user directory (identities come from the corporate sign-in).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Roles and approver eligibility survive restarts and reach approvals (Priority: P1)

An administrator assigns the viewer, buyer, approver and admin roles to people. The assignments persist across restarts and are mirrored to purchasing so that a proposal submitted for approval always finds its eligible approvers, and approval works end to end for a person who is not the creator or last editor.

**Why this priority**: Without durable roles and a working approver pool, no purchase can be approved; this is the completion gate of the Jira task.

**Independent Test**: Assign roles, restart every service, and confirm the assignments are unchanged; submit a proposal as a buyer and approve it as a different approver with fresh MFA.

**Acceptance Scenarios**:

1. **Given** a user with the approver role, **When** all services are restarted, **Then** the user still holds the role and is still counted as an eligible approver.
2. **Given** a role change whose mirror to purchasing fails, **When** the retry runs, **Then** the change is delivered exactly once and the failure and recovery are visible to the administrator.
3. **Given** a proposal submitted by a buyer, **When** the same buyer (or its last editor) tries to approve it, **Then** the approval is refused with a stable reason; a different approver with fresh MFA succeeds.
4. **Given** only one eligible approver exists, **When** a role change would remove an admin or an approver below the required minimum, **Then** the change is refused and explained.
5. **Given** a person without a role, **When** they sign in, **Then** they get the least privilege and see no administration screens.

---

### User Story 2 - Sensitive actions require fresh MFA and are fully audited (Priority: P1)

Role changes, approvals, cost-write releases, overrides, retries and re-runs ask the person for a recent second factor, and each attempt (allowed or refused) is recorded in a tamper-evident audit trail with who, what, when (UTC) and outcome, never with secrets or free-text notes.

**Why this priority**: Separation of duties and MFA are the controls that make human-decided purchasing trustworthy and are non-negotiable project rules.

**Independent Test**: Perform each sensitive action with fresh, stale and absent MFA and verify the outcome and the audit entry; run the audit-chain verification and confirm it detects an altered entry.

**Acceptance Scenarios**:

1. **Given** a session whose MFA is older than the freshness window, **When** a sensitive action is attempted, **Then** it is refused with a "sign in again" prompt and the refusal is audited.
2. **Given** an administrator, **When** they open the audit log, **Then** they can filter by person, action, outcome and date range, see the chain verification result, and export the visible rows.
3. **Given** any audit entry, **When** it is displayed or exported, **Then** it contains no token, secret, supplier note or other free text, and identifies the actor only by the stable user identifier (no e-mail address or display name).
4. **Given** a tampered audit row in a test database, **When** verification runs, **Then** it reports the first broken link.

---

### User Story 3 - Siweb sync health, jobs, queues and retries are visible and safely recoverable (Priority: P2)

An administrator sees, per data source, when the last successful sync happened, how many rows were loaded or quarantined and whether it is stale; sees running, failed and waiting background jobs and queued messages (including poisoned ones); and can safely retry a failed job without creating duplicates or exposing sensitive data.

**Why this priority**: It lets the owner detect stalled data before it corrupts a purchasing decision, without reading logs.

**Independent Test**: Seed a stale source, a failed job and a poisoned message; confirm each shows in the screen with a Spanish explanation; retry them and confirm a single effect and a record in the audit trail.

**Acceptance Scenarios**:

1. **Given** a source not synced within its freshness limit, **When** the administrator opens the status screen, **Then** it is flagged stale with the last success time and the number of quarantined rows.
2. **Given** a failed job, **When** the administrator retries it twice in a row, **Then** only one run takes effect (idempotent) and both requests are audited.
3. **Given** a message that keeps failing, **When** it exceeds the retry limit, **Then** it moves to a visible dead-letter list with its reason code and can be requeued by an administrator only.
4. **Given** any job or retry output, **When** logs and screens are inspected, **Then** they contain no secret, token, raw ERP payload or free-text note.

---

### User Story 4 - Alerts reach the administrator before the buyer notices (Priority: P2)

The system raises an alert when a source goes stale, a job or queue message fails repeatedly, the role mirror lags, a backup is missing or old, or spend approaches the budget. Alerts are shown in the console, and each time one opens a stable, secret-free log marker is written so the platform's existing e-mail alert rules can notify the administrator; an administrator can acknowledge them in the console.

**Why this priority**: Visibility is only useful if someone is told; but the console surfaces from Stories 1 to 3 deliver value first.

**Independent Test**: Trigger each alert condition with synthetic state and confirm one alert per condition (no storm), its Spanish text, acknowledgement and clearing when the condition ends.

**Acceptance Scenarios**:

1. **Given** a condition that persists, **When** it is re-evaluated repeatedly, **Then** a single open alert exists, not a new one per check.
2. **Given** an open alert, **When** an administrator acknowledges it, **Then** it is marked acknowledged with who and when, and it closes automatically when the condition clears.
3. **Given** no delivery channel is configured (the deployment states whether an e-mail channel exists), **When** an alert opens, **Then** it still appears in the console and the missing channel is itself reported.
4. **Given** an alert opens, **When** the log is inspected, **Then** exactly one marker line for that opening exists, carrying only the condition code and subject code, and a platform e-mail rule matches it.

---

### User Story 5 - Backup status and Azure cost are visible against the budget (Priority: P3)

The administrator sees when the last successful backup completed and when the last restore drill was recorded, and sees month-to-date and projected Azure spend against the shared EUR 120 per month budget, with the scale-to-zero and replica limits in force.

**Why this priority**: These protect the owner from data loss and overspend but do not block daily purchasing.

**Independent Test**: Provide synthetic backup and cost figures (fresh, old, over budget) and confirm the screen and the alerts of Story 4 react accordingly.

**Acceptance Scenarios**:

1. **Given** the latest backup is older than the agreed limit, **When** the screen is opened, **Then** it is flagged and an alert is raised.
2. **Given** projected spend above 80 % of the budget, **When** the screen is opened, **Then** a warning shows the figure, the budget and the month's remaining days; above 100 % it is flagged critical.
3. **Given** the cost source is unavailable, **When** the screen is opened, **Then** it says the figure is unavailable and never shows a stale number as current.

---

### Edge Cases

- A role change arrives while the purchasing service is down: it is stored, queued and delivered later in order; the screen shows the lag.
- Two administrators change the same person at once: the second sees a conflict and must reload (no silent overwrite).
- The last administrator tries to remove their own admin role: refused.
- Unknown role names in the corporate sign-in claims are ignored, never granted.
- An audit export is requested for a very large range: it is capped and says so, never silently truncated.
- Clock skew or a naive timestamp in a source row: shown with the original string and flagged, never dropped.
- A retry is requested for a job that already succeeded: no effect, clear message.
- An alert condition flaps: alerts are de-duplicated and not re-sent more than once per condition per agreed interval.
- Cost data covers a partial month: the projection is labelled as an estimate.

## Requirements *(mandatory)*

### Functional Requirements

**Audit of the baseline**

- **FR-001**: The deliverable MUST include an evidence inventory of every capability in this domain on the latest main, each classed as complete, partial, broken, missing or unverified with file references, and MUST reuse working code rather than rebuild it.

**Identity, roles and approvers**

- **FR-002**: Role assignments MUST persist across restarts of every service and MUST be changed only by an administrator.
- **FR-003**: Each role change MUST be mirrored to purchasing exactly once, with ordered retry and a visible lag and failure state.
- **FR-004**: The system MUST determine approver eligibility from the mirrored roles and MUST refuse submission for approval when fewer than the required number of eligible approvers exist, explaining why.
- **FR-005**: The approver MUST NOT be the creator or last editor of the proposal; this MUST be enforced in the service, not only in the screen.
- **FR-006**: A role change MUST be refused if it would remove the last administrator or leave fewer than the required eligible approvers.
- **FR-007**: A person with no recognised role MUST receive least privilege; unknown role names MUST be ignored.

**MFA and separation of duties**

- **FR-008**: Sensitive actions (role change, approval, cost release, override, job retry or re-run, alert configuration, audit export) MUST require MFA no older than the freshness window and MUST refuse and audit the attempt otherwise.
- **FR-009**: An override MUST NOT be released by the administrator who set it (constitution v1.3.0).

**Audit**

- **FR-010**: Every sensitive action and every refusal of an authenticated request MUST append a tamper-evident audit entry with actor, action, subject, outcome and UTC time.
- **FR-011**: Administrators MUST be able to view, filter (person, action, outcome, date range), verify and export the audit trail from the console.
- **FR-012**: Audit entries, logs, screens and exports MUST NOT contain secrets, tokens, raw ERP payloads, supplier tax identifiers or free-text notes (only a has-note flag).

**Operations visibility and recovery**

- **FR-013**: The console MUST show, per data source, the last successful sync, rows loaded, rows quarantined and staleness against a configurable limit.
- **FR-014**: The console MUST list jobs and queued messages by state (waiting, running, succeeded, failed, dead-lettered) with a stable reason code and the retry count.
- **FR-015**: An administrator MUST be able to retry a failed job or requeue a dead-lettered message; the operation MUST be idempotent and audited.
- **FR-016**: Retries MUST use bounded exponential backoff and MUST stop at a maximum, moving the item to the dead-letter list.

**Alerts, backup and cost**

- **FR-017**: The system MUST raise de-duplicated alerts for stale sources, repeated job or message failures, role-mirror lag, missing or old backups, and budget thresholds; each alert MUST be acknowledgeable and auto-close when its condition clears. Each opening MUST also write one stable, secret-free log marker so the platform's e-mail alert rules can notify; the application itself sends no e-mail.
- **FR-018**: The console MUST show the latest successful backup and the latest recorded restore drill, and MUST flag a backup older than the agreed limit.
- **FR-019**: The console MUST show month-to-date and projected Azure spend against the EUR 120 monthly budget with the scale-to-zero and replica limits in force, and MUST say when the figure is unavailable.

**Cross-cutting**

- **FR-020**: All administration screens, errors, alerts and exports MUST be in Spanish (es-ES) with EUR amounts and Spanish date and number formats, with no hard-coded user-facing text.
- **FR-021**: Administration screens and endpoints MUST be reachable only by the roles allowed to use them; everyone else MUST get a refusal that is audited when the caller is authenticated.
- **FR-022**: Every new interface MUST start as a contract in the shared contracts package, negotiated with Agent 00 where it is shared; no change may touch another agent's owned files or another service's database schema.
- **FR-023**: Timestamps MUST be stored in UTC with the original string retained; money MUST use exact decimal values.
- **FR-024**: This feature MUST add no ERP request and MUST NOT run any production deployment, merge to main or real ERP write.

### Key Entities *(include if feature involves data)*

- **User role assignment**: a person, their roles, active flag, revision, who changed it and when.
- **Role mirror item**: a queued change to deliver to purchasing, with attempt count, next attempt time, state and reason code.
- **Audit entry**: an append-only, chain-linked record of an action (actor, action, subject, outcome, UTC time, previous-entry link).
- **Source freshness record**: per data source, last success time, rows loaded, rows quarantined, staleness limit.
- **Job / queue item**: a background job or message with state, retry count, reason code and idempotency key.
- **Alert**: a condition, severity, open/acknowledged/closed state, who acknowledged and when, last evaluated.
- **Backup record**: completion time and result of a backup, and the time of the last restore drill.
- **Cost snapshot**: month-to-date and projected spend, budget, capture time and source status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % of role assignments present before a full restart are present and effective after it, verified by an automated test.
- **SC-002**: A proposal submitted by one buyer can be approved by a different approver with fresh MFA in one session, and 100 % of self-approval attempts are refused.
- **SC-003**: 100 % of sensitive actions attempted with stale or absent MFA are refused, and every attempt (allowed or refused) appears in the audit trail.
- **SC-004**: An altered audit entry is detected by verification in 100 % of the tested tamper cases.
- **SC-005**: On the synthetic dataset, the console shows which data source is stale, which jobs have failed and whether a backup is current within 30 seconds of opening it, checked by a scripted browser test.
- **SC-006**: Retrying any failed job twice produces exactly one effect in 100 % of tested cases.
- **SC-007**: A persistent alert condition produces one open alert, not repeated ones, across at least 20 consecutive evaluations.
- **SC-008**: A scan of logs, audit entries, screens and exports produced by the test suite finds zero secrets, tokens, raw ERP payloads or free-text notes.
- **SC-009**: The month's projected spend and the budget status are visible, and an over-80 % projection raises a warning in 100 % of tested cases.
- **SC-010**: Every administration screen and message appears in Spanish with Spanish formats; an automated check finds no untranslated or hard-coded user-facing text.

## Assumptions

- Identities and base role names come from the corporate sign-in; this feature does not manage passwords.
- The existing durable role store, mirror, audit chain, MFA step-up and admin status screen are the starting point; the inventory (FR-001) decides which parts need work, and the gaps listed in the stories are hypotheses until verified.
- The MFA freshness window stays at the current 5 minutes unless the audit shows a reason to change it.
- The required minimum number of eligible approvers is the value already used by the approval rules.
- Delivery beyond the console reuses the platform's existing e-mail alert rules, which match the log marker written when an alert opens; the application holds no mail credentials. Whether an e-mail channel is deployed is a deployment setting; if none is, console-only alerts apply and that is reported.
- Cost and backup figures come from the platform's own reporting and are supplied to the application read-only; this feature does not create or change cloud resources outside its own infrastructure templates.
- Data and tests use only synthetic fixtures; no real identities, e-mail addresses or tenant identifiers are committed.
- Features 002 and 006 own the shared dashboard and policy areas; this feature touches only the administration domain.
