# Data Model: Architecture, Contracts & Integration

All entities are JSON files in the repository, validated by the schemas in [contracts/](contracts/). None is stored in a database.

## FeatureStatusRecord

| Field | Type | Rule |
|-------|------|------|
| id | string | Unique, kebab-case |
| title | string | Required |
| status | enum | `complete`, `partial`, `broken`, `missing`, `unverified` |
| evidence | list of `path:line` | At least one; each path must exist at audit commit |
| owner | string | Agent or service owning the gap |
| reuse | boolean | True when existing code should be reused |
| notes | string | Plain text, no real data |

Rule: `complete` requires at least one evidence entry pointing to a test or demonstration; otherwise the record must be `unverified`.

## ContractEntry

| Field | Type | Rule |
|-------|------|------|
| name | string | Matches schema file stem without version |
| kind | enum | `dto`, `event`, `error`, `endpoint` |
| version | integer | From the `vN` suffix |
| schema_path | string | Must exist (not for `endpoint`) |
| owner | string | A service or agent |
| consumers | list of string | Services that read it |
| status | enum | `draft`, `frozen`, `deprecated` |
| supersedes / superseded_by | string | Links `v1`↔`v2` |

State transitions: `draft → frozen → deprecated`. A `frozen` entry's schema may change only compatibly (checked against the baseline); a breaking change creates a new entry and moves the old one to `deprecated`. A `deprecated` entry is removable only when `consumers` is empty or all consumers list the successor.

## SchemaOwnership

`service` → `db_schema` (one to one). The isolation gate fails when a service references any other `db_schema`.

## ArchitectureDecisionRecord

`number`, `title`, `status` (`proposed`, `accepted`, `superseded`), `context`, `decision`, `consequences`, `supersedes?`. One Markdown file each.

## IntegrationStep

| Field | Type | Rule |
|-------|------|------|
| pr | integer | Domain PR number |
| agent | string | Owning agent |
| owned_paths | list of glob | A PR diff outside these paths is rejected; two different agents may not claim overlapping paths |
| depends_on | list of pr | Acyclic |
| verification | list of gate names | Gates that must pass after this step |
| state | enum | `pending`, `integrated`, `dropped`, `fixed_reentered` |
| drop_reason | string, optional | Required for the integration gate when `state` is `dropped` (for example `gate_failed: cost`) |

## ReleaseGate result

`gate` (`contracts`, `isolation`, `integration`, `e2e`, `security`, `cost`), `result` (`pass`, `fail`, `not_run`), `evidence` (list of messages or file refs), `started_at` / `finished_at` (UTC ISO-8601 with the original string kept), `dropped_prs` and `integrated` (the PR numbers that stayed in) on the aggregate report of `integrate`. Aggregate passes only if every gate passes.

## Relationships

`ContractEntry.owner` and `consumers` reference services in `SchemaOwnership`; `IntegrationStep.verification` references gate names; `FeatureStatusRecord.owner` references an agent in `IntegrationStep.agent`.
