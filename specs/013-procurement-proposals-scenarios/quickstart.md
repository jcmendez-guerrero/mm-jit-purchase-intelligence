# Quickstart: validating Procurement Proposals & Scenarios

Prerequisites: Docker compose stack from `infra/compose.yaml`, Python 3.12 environment, Node with Playwright browsers; synthetic fixtures only (`packages/testing`). Never point any of this at a real Siweb host.

1. **Domain tests** (from `services/procurement-service`): run the proposal, approval, scenario, allocation and export tests. Expect green, including the new determinism (20 runs), no-outbound-request and 2,000-SKU timing tests.
2. **Gateway tests** (from `services/api-bff`): run the route and role tests. Expect a viewer export to be refused with `auth_forbidden_role` and an audit entry.
3. **Gates**: from `scripts/`, run `python -m gates run`. Expect pass (required because error keys change).
4. **End-to-end**: start the compose stack, then run the Playwright journey in `apps/web/tests/e2e/`. Expected path: generate proposal → open line explanation → edit a line → create and compare scenarios → promote (old proposal shows as superseded) → submit → self-approval refused → approval by a second user with fresh MFA → CSV and Excel export. All text must be Spanish with EUR and Spanish date formats.
5. **Evidence**: save screenshots of the journey and the inventory table results to the PR description (synthetic data only).

Contracts and data model: see [contracts/proposals-scenarios.delta.md](contracts/proposals-scenarios.delta.md) and [data-model.md](data-model.md).
