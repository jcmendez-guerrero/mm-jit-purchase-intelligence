<!--
Sync Impact Report
Version change: 1.1.0 -> 1.2.0 (MINOR: materially expanded guidance in Principle I, plus a
  matching clarification in Principle III)
Modified principles:
  - I. Least-Privilege Integrations (conditions and value of the single permitted Siweb write:
    created at receipt matching or at buyer entry for a pair with no Siweb cost; value is the
    median of Recargo-inclusive lot acquisition costs; margin check; admin override; fresh
    second factor and writer checks always apply)
  - III. Explainable and Human-Controlled Purchasing (refers to the human-initiated,
    buyer-reviewed update, including its median value and admin override)
Added sections: none
Removed sections: none
Modified sections: Additional Constraints (states that the value rules do not widen the
  outbound allowlist)
Rationale: feature MMI 002 (specs/002-mmi-operational-console, FR-040 to FR-044, Jira KAN-34).
  The ERP holds one unit cost per supplier while lots can differ in acquisition cost, and ERP
  stock movements carry the retail price (PVP), not cost. MMI keeps its own per-lot acquisition
  cost record, and the value sent to the ERP is the median of those lot costs.
Follow-up TODOs:
  - TODO(RATIFICATION_DATE): confirm formal adoption date (still open)
  - Resolved 2026-11-05 (owner): the admin who sets an override MUST NOT release it
  - Update ADR-006 and docs/architecture/implementation-plan.md to describe the median value,
    margin check and admin override
  - Note in specs/002-mmi-operational-console that scenarios 4c and 4d of
    specs/001-mmi-purchase-intelligence are superseded for the cost value and timing
  - Close task T064 in specs/002-mmi-operational-console/tasks.md after this amendment is
    reviewed and merged
-->
<!--
Sync Impact Report
Version change: 1.0.0 -> 1.1.0 (MINOR: materially expanded guidance in two principles)
Modified principles:
  - I. Least-Privilege Integrations (adds one narrowly scoped, human-initiated Siweb write)
  - III. Explainable and Human-Controlled Purchasing (clarifies the permitted write)
Added sections: none
Removed sections: none
Modified sections: Additional Constraints (outbound allowlist now includes the single write)
Rationale: user decision 2026-11-04 during clarification of
  specs/001-mmi-purchase-intelligence (FR-040 to FR-043): the buyer enters or confirms
  supplier costs and the ERP must reflect them.
Follow-up TODOs:
  - TODO(RATIFICATION_DATE): confirm formal adoption date
  - Update ADR-006 and the decisions log in docs/architecture/implementation-plan.md
    (they still state that all Siweb writes are blocked)
-->
# Mundo Mascotix Intelligence Constitution

## Core Principles

### I. Least-Privilege Integrations
External integrations MUST enforce host, path, and HTTP-method allowlists before sending
requests. The Siweb connector MUST be read-only and refuse every method or path outside its
documented GET allowlist, with exactly one exception: updating a supplier's cost on a product
(the Siweb `PUT /inventory/products/{id}/suppliers/{contact_id}` operation). That write is
human-initiated and buyer-reviewed. An update request MUST be created only:
- when goods are received and matched to a confirmed supplier order; or
- when the buyer enters a cost for a product-supplier pair that has no cost in Siweb.

The value sent MUST be the median of the Recargo-inclusive acquisition costs of that pair's
lot entries with remaining stock: a plain (unweighted) median, the mean of the two middle
values when the count is even, computed with exact decimals and rounded half-up to whole
cents. When Siweb has no cost and no lot exists, the cost entered by the buyer is the value.
When no entry has remaining stock, no request MUST be created.

Before release, a margin check MUST be computed as margin = 1 - (Recargo-inclusive cost / PVP).
A margin below 15% MUST block the release unless an admin overrides it; other margin limits
only flag and explain. An admin MAY replace the median with a value of their own judgement
only for a flagged or blocked update, with a mandatory written reason and explanatory tips
shown, and the audit record MUST hold the median, the chosen value, the margins before and
after, who, and when.
The admin who sets an override MUST NOT be the person who releases it; a different buyer MUST
release it.

Every such write, including an override, MUST:
- use an identity and permissions separate from the read-only collection;
- pass through a closed allowlist containing only that operation;
- be shown to the buyer for review before it is sent;
- require a second factor authenticated recently, and pass the writer's own pre-write checks;
- leave an audit record of who, when, previous value, new value, and outcome;
- be retried visibly on failure and never silently dropped.

No other Siweb write is permitted. Secrets MUST be stored in Azure Key Vault and accessed only
by the identity that needs them; credentials, tokens, and environment-specific identifiers
MUST NOT be committed to the repository. This limits the impact of the shared full-scope
Siweb token.

### II. Privacy and Synthetic Data
Local development, tests, and CI MUST use synthetic data only. Real Siweb exports, raw API
responses, personal data, supplier tax identifiers, free-text notes, and real commercial
records MUST NOT be committed or used as fixtures. Collection and retention MUST be limited
to documented business needs; fields not required for those needs MUST be discarded before
storage. Sanitized contract examples and aggregate patterns MAY inform synthetic fixtures,
but real rows and identifiers MUST never be copied.

### III. Explainable and Human-Controlled Purchasing
Purchasing recommendations MUST be reproducible from identified inputs, rules, and data
provenance. Monetary values MUST use decimal arithmetic, and supplier costs MUST retain
their source, verification time, and version. Free-text notes MUST NOT drive automated
business decisions. The system MUST explain recommendations and require human approval for
purchase actions. It MUST NOT autonomously write to Siweb, approve its own proposals, or
perform any Siweb write other than the human-initiated, buyer-reviewed supplier-cost update
defined in Principle I (including its median value and admin override). Approval controls
MUST separate proposal creation from approval.

### IV. Contract-First Service Boundaries
Services MUST communicate through explicit, versioned contracts. Shared JSON Schema
contracts MUST be the source for generated Python/Pydantic and TypeScript types where
applicable. Each service MUST own its database schema, role, and migrations; service-to-
service access MUST use authenticated, audience-scoped identities. Asynchronous message
processing MUST be idempotent and validate message schema and integrity. These boundaries
allow services to evolve independently without hiding incompatible changes.

### V. Testable, Observable, and Cost-Bounded Delivery
Changes MUST include automated tests for their behavior and affected contracts. Tests MUST
cover security boundaries, data-quality failures, and retry or duplicate handling where
applicable. Services and jobs MUST emit operational signals sufficient to detect failures,
quota use, and budget impact without logging secrets or unnecessary personal data. Workloads
MUST respect the shared monthly budget, scale-to-zero and replica/job caps; new shared
infrastructure requires a documented decision and cost justification.

## Additional Constraints

- The planned application is a monorepo with Python services, a React/TypeScript SPA,
  PostgreSQL, and Azure hosting. Infrastructure as Code uses Bicep unless an amended
  architecture decision adopts another tool.
- The Siweb integration MUST restrict outbound traffic to the approved Siweb host, the
  allowlisted read-only API paths, and the single permitted supplier-cost update operation.
  The value rules in Principle I (median, margin check, admin override) do not widen this
  allowlist.
  Tests MUST prove that every other method and path is refused before a request is sent.
  Rate use MUST remain within the agreed per-application share of the shared limit.
- PostgreSQL data MUST be isolated by service schema and role. Database migrations MUST be
  versioned and attributable to the owning service.
- Azure resources MUST reuse the existing database server, container environment, registry,
  Key Vault, and monitoring resources when feasible and within their approved capacity.
  Exceptions require a documented architecture decision and cost review.
- Public repository content MUST be limited to code, generic documentation, templates,
  and synthetic fixtures. Real product, supplier, price, quantity, tenant, subscription,
  resource, or network details MUST NOT be committed.
- Forecasting and procurement recommendations MUST preserve data-quality errors for review;
  malformed or ambiguous source data MUST NOT be silently normalized into trusted input.

## Development Workflow

- Before implementation, resolve applicable Gate 0 prerequisites and record material
  architecture decisions. Unverified external API behavior MUST be represented as an
  explicit assumption and validated before production use.
- Changes to shared schemas or service interfaces MUST include contract tests and a
  compatibility review. Breaking changes MUST define a migration or coordinated rollout.
- Tests and local development MUST run with synthetic fixtures and without Azure credentials.
  CI MUST run relevant tests, contract validation, secret scanning, and dependency or
  container security checks for the changed components.
- Production deployment MUST use pinned dependencies or artifacts, OIDC-based deployment
  identity, and manual approval. A backup restore drill and operational runbooks are
  required before production operation.
- Pull requests MUST explain relevant data, security, cost, and contract impacts. Reviewers
  MUST verify conformance to this constitution and the applicable architecture decisions.

## Governance

This constitution governs project design and delivery and takes precedence over conflicting
repository practices. Repository maintainers may amend it through a reviewed pull request
that records the rationale, affected principles, compatibility or migration impact, and
required follow-up work. Material changes to accepted architecture decisions MUST also be
recorded in the architecture decision log.

The constitution uses semantic versioning. A MAJOR increment denotes a backward-incompatible
change to governance or a redefinition/removal of a principle; a MINOR increment denotes a
new principle, section, or materially expanded requirement; a PATCH increment denotes
clarification or non-semantic wording changes. Pull request authors and reviewers MUST
assess compliance during planning and review; unresolved violations require an explicit
exception documented with rationale, owner, and review date.

**Version**: 1.2.0 | **Ratified**: TODO(RATIFICATION_DATE): confirm formal adoption date | **Last Amended**: 2026-11-05
