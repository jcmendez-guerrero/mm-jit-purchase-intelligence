# ADR-002: Infrastructure as Code: Bicep now, Terraform-ready

- Status: accepted
- Date: 2026-11-04

## Context and problem statement
The platform runs on Azure and shares an estate that may later move to Terraform. A tool must be chosen now without making a later move costly.

## Considered options
Bicep; Terraform; ARM JSON.

## Decision outcome
Bicep, structured so migration is mechanical:
- one module per resource type under `infra/bicep/modules/`;
- parameters only in `*.bicepparam.example` (real parameter files are git-ignored);
- no logic in parameter files;
- all resource names produced by one naming module.

Revisit when the shared estate moves to Terraform.

### Consequences
- Good: native Azure tooling, low overhead; mechanical `terraform import` or rewrite later.
- Bad: deviation from the architecture specification, which preferred Terraform.
