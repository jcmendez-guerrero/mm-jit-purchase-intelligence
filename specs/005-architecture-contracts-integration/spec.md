# Feature Specification: Architecture, Contracts & Integration (MMI 003 / Agent 00)

**Feature Branch**: `claude/speckit-specification-ad04eb` (spec directory `005-architecture-contracts-integration`)

**Created**: 2026-11-08

**Status**: Draft

**Input**: User description: "Get the specification from <https://mundomascotix.atlassian.net/browse/MMI-2>" (Jira MMI-2, epic MMI-1, linked Confluence page "MMI 003 — Agent 00 — Architecture, Contracts & Integration")

## Clarifications

### Session 2026-11-08

- Q: Where are domain PRs integrated and verified, given Agent 00 may not merge to main? → A: Agent 00 builds a temporary integration branch from the domain PRs and runs all gates there; the maintainer merges the PRs to main in the documented order.

- Q: What happens to a domain PR that fails a release gate on the integration branch? → A: It is dropped from the integration branch together with the PRs that depend on it and reported to its owning agent; integration continues with the rest. All domain agents watch gate results and automatically attempt fixes on their own PRs, which re-enter integration once they pass.

- Q: How is a breaking change to a frozen shared interface handled? → A: A new interface version is added next to the old one; the old one is deprecated and kept until all consumers have moved.
- Q: How is the Spanish (es-ES) interface demonstrated as "API-backed"? → A: A browser journey runs against the local compose stack (real services, synthetic data) in the end-to-end gate; the fake-backend browser suite stays as a separate fast check.
- Q: Should "all domain PRs integrated" be its own release gate? → A: Yes, an `integration` gate that passes only when every PR in the integration plan is integrated, or dropped with a recorded reason.
- Q: How do domain agents get the gate results they watch for auto-fix? → A: The gate report is saved as a CI artifact and summarized as a comment on each domain PR; agents read the PR checks and the artifact. No new service.
- Q: Which FR-013 guarantees do the integration gates re-check? → A: Agent 00 maps each guarantee to an existing test, runs those in the security gate, and adds a new test only where a guarantee has none.

### Session 2026-11-09

- Q: Where does Agent 00 get the sibling domain PRs, their agents and owned files for the integration plan? → A: The maintainer supplies PR numbers, agents and owned paths; Agent 00 records them in the integration plan.
- Q: What does the integration plan contain when no sibling domain PRs are open yet? → A: This feature's own PR (Agent 00, its own paths) is listed as the first step; siblings are added later by the maintainer, and plan validation keeps path ownership unique. An empty plan keeps the integration gate `not_run`.
- Q: How is SC-007 (finding an interface's owner, version and consumers) verified? → A: A `python -m gates lookup NAME` command prints them and a test covers it; the "under 2 minutes" human trial is dropped.
- Q: How do the full gates run on the integration branch in CI, given the branch is temporary and never pushed? → A: A manually started workflow checks out main, builds the integration branch inside the CI run from each PR's head, runs all six gates and discards the branch. Nothing is pushed.
- Q: What is the longest the full gate run should take? → A: No limit for now; the first full run is timed and a limit is set from it.
- Q: Which gates are required checks, and where? → A: Contracts and isolation are required on every PR; all six gates are required on the integration branch.

## User Scenarios & Testing *(mandatory)*

Agent 00 is the coordinating unit of the MMI-1 parallel-agent product-completion effort. Its "users" are the other domain agents, the maintainer who reviews and merges their PRs, and, indirectly, the buyers and admins who will use the integrated Spanish (es-ES) product.

### User Story 1 - Evidence-based audit of the current main branch (Priority: P1)

The maintainer needs to know what actually works today before parallel work starts. The audit inspects the latest main branch and classifies every feature as complete, partial, broken, missing or unverified, with file and line evidence. It also inventories endpoints, schemas, service ownership, CI workflows, existing tests and merged PRs.

**Why this priority**: Every later decision (contract freeze, sequencing, gates) depends on a trustworthy baseline. Without it, agents re-implement working code or build on broken foundations.

**Independent Test**: Review the published audit and spot-check any 10 randomly chosen rows against the repository; each status claim must be backed by a reachable file/line reference.

**Acceptance Scenarios**:

1. **Given** the latest main branch, **When** the audit is produced, **Then** every feature has exactly one status (complete, partial, broken, missing, unverified) and at least one file/line evidence reference.
2. **Given** the audit, **When** a domain agent starts work, **Then** it can identify which existing code to reuse and which gaps it owns.
3. **Given** a feature whose behaviour cannot be demonstrated, **When** it is audited, **Then** it is marked unverified rather than complete.

---

### User Story 2 - Contract matrix and frozen shared interfaces (Priority: P1)

Domain agents need one authoritative, versioned description of every shared interface (the contracts the gateway layer exposes and the services exchange) and of who owns each service and its data. Agent 00 publishes a contract matrix and freezes the shared interfaces at a named version; any later change goes through Agent 00.

**Why this priority**: Parallel agents can only work without collisions if interfaces are fixed and ownership is explicit. This is the core coordination deliverable.

**Independent Test**: Take any shared interface, change a field in a domain agent's branch without updating the contract; the contract checks fail. Update the contract first with a version bump; the checks pass.

**Acceptance Scenarios**:

1. **Given** the contract matrix, **When** an agent looks up an endpoint, event or schema, **Then** it finds its owner, version, consumers and status.
2. **Given** a frozen shared interface, **When** a domain agent needs a change, **Then** it requests it from Agent 00 and the change is versioned and recorded before implementation.
3. **Given** any service, **When** its data access is inspected, **Then** it reads only its own data; no service reads another service's schema directly.

---

### User Story 3 - Architecture decisions and integration sequencing (Priority: P2)

The maintainer needs the key architecture decisions recorded (ADRs) and a defined order in which the domain agents' PRs are integrated, so that dependent work lands after the work it relies on and each integration step can be verified.

**Why this priority**: Prevents merge conflicts and rework, but only matters once the audit and contracts exist.

**Independent Test**: Follow the sequencing document with the domain PRs in a test integration; each step names its prerequisites and its verification, and the final state passes the end-to-end checks.

**Acceptance Scenarios**:

1. **Given** the list of domain PRs, **When** the integration plan is read, **Then** each PR has a position, prerequisites and a verification step.
2. **Given** a significant architectural decision, **When** it is made, **Then** an ADR records context, decision and consequences.
3. **Given** two agents needing the same shared file, **When** conflicts arise, **Then** the plan states which agent owns it.

---

### User Story 4 - Release gates and integrated verification (Priority: P2)

Before the integrated product can be considered complete, the maintainer needs automatic gates: contracts versioned, no cross-schema reads, all domain PRs integrated, end-to-end journeys passing in the Spanish UI, security checks passing and monthly cost within budget.

**Why this priority**: Proves the whole is complete, not just the parts; depends on the other stories.

**Independent Test**: Run the full gate suite against the integrated branch with synthetic data; every gate reports pass/fail with evidence and a failing gate blocks the release.

**Acceptance Scenarios**:

1. **Given** the integrated branch, **When** the gates run, **Then** contract-version, schema-isolation, end-to-end, security and cost gates each report a clear result.
2. **Given** any failing gate, **When** release is attempted, **Then** it is blocked and the failure names the gate and cause.
3. **Given** the end-to-end run, **When** it completes, **Then** it demonstrates the API-backed Spanish UI using synthetic fixtures only.

---

### User Story 5 - Shared gateway contracts and integration tests (Priority: P3)

Agent 00 owns the shared gateway-layer contracts and the cross-domain integration tests. "Gateway" means the existing gateway service (`services/api-bff`) throughout this spec. The gateway orchestrates calls between domains but contains no business rules.

**Why this priority**: Important for long-term maintainability; the first four stories already deliver a usable coordination baseline.

**Independent Test**: Inspect the gateway for business-rule logic (none expected) and run the cross-domain integration tests against synthetic data.

**Acceptance Scenarios**:

1. **Given** a request spanning two domains, **When** it passes through the gateway, **Then** each domain applies its own rules and the gateway only composes the results.
2. **Given** a mutation request repeated with the same idempotency key, **When** it is processed, **Then** it takes effect once.

---

### Edge Cases

- A domain agent changes a shared interface without going through Agent 00: the contract gate fails and blocks integration.
- A feature appears complete but has no test or demonstration: it is classified unverified.
- Two domain PRs modify the same shared file: ownership rules decide the order; the later PR rebases.
- A domain PR adds a query touching another service's data: the schema-isolation gate fails.
- A gate cannot run (e.g., missing fixtures): it reports "not run", which blocks release the same as a failure.
- Projected monthly cost exceeds the shared budget: the cost gate fails and names the contributing resources.
- Integration requires any real ERP write, production deployment or merge to main: it is out of scope and requires explicit user authorization.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The audit MUST classify every product feature on the latest main as complete, partial, broken, missing or unverified, with file and line evidence for each classification.
- **FR-002**: The audit MUST inventory endpoints, schemas, service and data ownership, CI workflows, existing tests and merged PRs.
- **FR-003**: Working existing code MUST be identified for reuse by domain agents; the audit MUST NOT recommend rebuilding what already works.
- **FR-004**: A contract matrix MUST list every shared interface with owner, version, consumers and status.
- **FR-005**: Shared interfaces MUST be versioned and frozen at a named version; changes MUST be made contract-first through Agent 00 and recorded. A breaking change MUST be introduced as a new interface version alongside the old one; the old version is marked deprecated and kept until all consumers listed in the contract matrix have moved.
- **FR-006**: Each service MUST access only its own data; cross-schema reads MUST be detected and blocked automatically.
- **FR-007**: Architecture decisions affecting more than one domain MUST be recorded as ADRs.
- **FR-008**: An integration plan MUST define the order, prerequisites and verification of each domain PR. Agent 00 MUST combine the domain PRs on a temporary integration branch and run all release gates there; the maintainer, not Agent 00, merges the PRs to main in the documented order. In CI the integration branch MUST be built inside a manually started workflow run from main and each PR's head, and discarded afterwards; it MUST NOT be pushed.
- **FR-009**: Release gates MUST cover contract versioning, schema isolation, integration status, end-to-end journeys, security and cost, each with an explicit pass/fail/not-run result. The integration gate passes only when every PR in the integration plan is integrated, or dropped with a recorded reason.
- **FR-010**: A failing or not-run gate MUST block release. The contracts and isolation gates MUST be required checks on every PR; all six gates MUST be required checks on the integration branch. A domain PR that fails a gate MUST be dropped from the integration branch together with the PRs that depend on it, and reported to its owning agent; integration MUST continue with the remaining PRs.
- **FR-010a**: The gate report MUST be saved as a CI artifact and summarized as a comment on each domain PR, with no new service. Every domain agent MUST watch the gate results of its own PR and automatically attempt fixes within its owned files; a fixed PR re-enters the integration branch only after it passes the gates. Automatic fixes MUST NOT merge to main, edit another agent's files or perform ERP writes.
- **FR-011**: The end-to-end gate MUST include a browser journey in the Spanish (es-ES) UI run against the local stack of real services with synthetic fixtures only; the fake-backend browser suite is a separate fast check and does not satisfy this requirement on its own.
- **FR-012**: The gateway layer MUST orchestrate across domains without implementing business rules.
- **FR-013**: The system MUST preserve existing platform guarantees across integration: role-based access, multi-factor authentication for sensitive operations, audit trail, provenance, idempotent mutations, UTC timestamps and decimal monetary values. Each guarantee MUST be mapped to an existing test that runs in the security gate; a new test is added only for a guarantee with no covering test.
- **FR-014**: The ERP MUST remain the source of truth for catalogue, stock, movements and ERP costs; MMI owns only versioned supplier conditions, policies, predictive datasets and scenarios. No fabricated ERP transactions and no ERP writes beyond those already authorized by the constitution.
- **FR-015**: Monthly cloud cost MUST stay within the shared budget of about EUR 120; no always-on analytics services may be added.
- **FR-016**: The work MUST be delivered as one reviewable PR containing a change summary, migration impact, screenshots, test evidence, known limitations and links to the Confluence page and the Jira task MMI-2.
- **FR-017**: No production deployment, merge to main, destructive operation or real ERP write may occur without explicit user authorization.
- **FR-018**: All user-facing text produced MUST be es-ES; engineering documentation MUST be English.

### Key Entities

- **Feature Status Record**: A feature, its status (complete/partial/broken/missing/unverified), and evidence references.
- **Contract Entry**: A shared interface with owner, version, consumers and lifecycle status (draft, frozen, deprecated).
- **Architecture Decision Record**: Context, decision and consequences for a cross-domain decision.
- **Integration Step**: A domain PR with its position, prerequisites and verification.
- **Release Gate**: A named check with result (pass/fail/not run) and evidence.
- **Domain Agent Assignment**: An agent, its owned files/domain and its Jira task (MMI-1 children).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of features on main have a status and at least one evidence reference in the audit.
- **SC-002**: 100% of shared interfaces appear in the contract matrix with an owner and version.
- **SC-003**: 0 cross-service data reads exist at the end of integration, as reported by the automated gate.
- **SC-004**: 100% of domain PRs are integrated in the documented order with their verification step passing.
- **SC-005**: All end-to-end, security and cost gates pass on the integrated branch with synthetic data only.
- **SC-006**: Projected monthly cost stays at or below about EUR 120.
- **SC-007**: The owner, version, consumers and status of any shared interface come from one documented command (`python -m gates lookup NAME`), which exits non-zero for an unknown name; the criterion is checked by a test, not by a timed human trial.
- **SC-008**: The first full gate run on the integration branch is timed and recorded in the PR, and a maximum duration for later runs is set from that measurement.

## Assumptions

- The Confluence page is the full scope; Jira MMI-2 is the single-agent assignment and carries no additional criteria.
- Jira and Confluence text name the artifacts directory `specs/003-agent-00/`, but `003` is already used by `003-modern-frontend-ui`; this feature uses the next sequential number, `005-architecture-contracts-integration`. The Jira "MMI 003" label refers to the product-completion epic, not the spec number.
- Existing repository rules (constitution v1.3.0, `AGENTS.md`) apply: synthetic data only, no secrets, ERP read-only except the two permitted writes, humans decide purchases.
- Other domain agents' tasks (siblings under epic MMI-1) exist or will exist; their scopes are not specified here. The maintainer supplies their PR numbers, agent names and owned paths for the integration plan (PR numbers and paths only, no private data). Until siblings exist, the plan lists this feature's own PR as its first step, so its number is known only once that PR is opened.
- Implementation happens in a dedicated worktree and feature branch, without editing another agent's owned files.
- Existing contracts, CI and tests (`packages/contracts`, specs 001–004) are the baseline to audit and extend.
