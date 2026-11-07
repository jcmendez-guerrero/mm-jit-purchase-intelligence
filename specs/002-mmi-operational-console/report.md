# MMI 002: final technical report

Branch `claude/mmi-002-operational-console-ibqo4g`. Synthetic data only; no real ERP host was contacted and no write reached a real ERP. Nothing was merged or deployed.

## Verification run on this branch (last full pass)

| Suite | Result |
|---|---|
| Service unit and integration tests (inventory, forecast, procurement, api-bff, connector, cost-writer, contracts) | all pass (inventory 126, forecast 132, api-bff 113, contracts 185 plus skipped emulator tests) |
| Web unit tests (Vitest, includes localisation and no-hard-coded-options checks) | 214 pass |
| Spanish browser tests (Playwright on Chromium, backends mocked, axe checks) | 36 pass (includes 4 evidence captures) |
| PostgreSQL 16 migrations, upgrade and downgrade, all six schemas | 9 pass |
| Real-process approval end-to-end (real services, real PostgreSQL, two users, fresh MFA) | 3 pass |
| Infra tests (error codes and localisation, routing, storage policy, cost guardrails, alert rules, security abuse) | 51 pass, 14 skipped (need Docker or an emulator) |
| Dependency scan (`pip-audit` on the installed environment) | no known vulnerabilities |
| `npm audit` (production, high and above) | passes; 2 moderate advisories on `react-router` SSR hydration, a path this client-only app does not use |
| Pattern secret scan of tracked files | clean apart from the public Azurite development key (allow-listed in `.gitleaks.toml`); one business-domain development e-mail found and replaced |

## Not verified (honest gaps)

- Docker Compose stack, the Docker-based `RUN_E2E` pipeline suite, Bicep build and any Azure deployment were not run: no Docker or Azure access here. CI is configured to run them.
- Gitleaks and Trivy only run in CI; a pattern scan stood in locally.
- Real ERP behaviour: nothing was run against a real Siweb. T135 (supplier-cost PUT semantics on a non-production record) and the net-of-VAT assumption for variant prices stay open gates.
- Production identity (on-behalf-of tokens) is not wired; the BFF uses its development identity path.
- Seed originals use a local folder in development; production needs the private container described in the plan.
- The accuracy chart uses stored daily aggregates per warehouse and demand group, not per supplier.
- Performance: only the dashboard first-content budget (3 s, 1,000 alerts) is asserted, in a mocked browser; the 15-minute import and 2-minute rollback timings (SC-002) were not measured end to end.
- Stale-selling-price rule (G2) is decided (7 days) and implemented; the constitution v1.2.0 ratification date is pending.

## Success criteria to evidence

| Criterion | Evidence | Status |
|---|---|---|
| SC-001 supplier terms in under 10 minutes, shown in next proposal | `services/procurement-service/tests/test_terms_*.py`, `test_allocation_terms.py`; `apps/web/tests/e2e/suppliers.spec.ts` | functional behaviour covered; the 10-minute usability time was not measured |
| SC-002 import and rollback times | `services/forecast-service/tests/test_seed_activation.py`, `test_seed_rollback.py`, `test_imports_api.py`; `tests/e2e/import.spec.ts` | flow covered; timing not measured |
| SC-003 KPIs match reference totals; content under 3 s | `services/inventory-service/tests/test_aggregates.py`; `tests/e2e/dashboard.spec.ts`, `dashboard-perf.spec.ts` | covered |
| SC-004 no hard-coded options | `apps/web/tests/unit/no-hardcoded-options.test.ts`; `services/inventory-service/tests/test_filter_options.py`; `tests/e2e/warehouses.spec.ts` | covered |
| SC-005 every row accepted or listed; nothing counted as ERP movement | `test_seed_validation.py`, `test_seed_isolation.py` | covered |
| SC-006 audit entries and version references | `test_audit_chain.py` in each service; `test_runs.py`; `test_scenarios_isolation.py` | covered |
| SC-007 two-user approval after restart; self-approval and stale MFA refused | `infra/tests/test_approval_e2e.py` (real processes); `services/api-bff/tests/test_abuse_matrix.py`; `procurement-service/tests/test_approval*.py` | covered |
| SC-008 scenario changes with reasons | `test_scenarios_constraints.py`, `test_scenarios_sensitivity.py`, `test_scenarios_infeasible.py`, `test_scenarios_promote.py`; `tests/e2e/scenarios.spec.ts` | covered |
| SC-009 Spanish, EUR and Spanish formats | `tests/unit/i18n-coverage.test.ts`, `hardcoded-strings.baseline.json`; `infra/tests/test_error_keys_localised.py`; `test_formula_safe_export.py`; screenshots below | covered; a screenshot review found and fixed a percentage display bug and untranslated statuses |
| SC-010 suites, abuse cases, accessibility, performance, migrations | table above; `infra/tests/test_security_abuse.py`; `tests/e2e/a11y.spec.ts` | covered, except the Docker suites; axe colour-contrast rule is disabled in the accessibility run |
| SC-011 spend at or below EUR 120, scale to zero | `infra/tests/test_cost_guardrails.py` (checked to fail on a violation); estimate in `docs/architecture/implementation-plan.md` section 10 | covered; estimate is not a measurement |
| SC-012 margin rules, median cost, inventory value | `test_margin_rules.py`, `test_margin_override.py`, `test_median_cost.py`, `test_lots_in_stock.py`, `test_pvp.py` | covered |

The acceptance criteria labelled AC1 to AC9 live in the Jira issue, not in this repository, so they are mapped here through each user story's acceptance scenarios (US1 to US7 in `spec.md`), all of which have the tests above.

## Findings fixed during final verification

- The BFF let any viewer call the policy-override revert route, relying on the downstream check alone; it now requires buyer or approver (found by the route-matrix abuse test).
- Unknown dataset ids on the quarantine route returned an empty 200; they now return the stable 404 like every other dataset route.
- Percentages from the scenario service were shown multiplied by 100 again (9167 % instead of 91,7 %).
- A development default e-mail used the business's own domain; replaced with a reserved example domain.
- Migration 0007 (scenario summary column) was verified on PostgreSQL 16.

## Evidence screenshots (synthetic data)

`docs/architecture/evidence/`: `panel.png`, `escenarios.png`, `datos-predictivos.png`, `administracion.png`. Refresh with `CAPTURE_EVIDENCE=1` and the Playwright suite.

## Decisions for the owner

Malware scanning: owner accepted the risk on 2026-11-07 (recorded in ADR-020). Still open: decide the stale-price threshold (G2), VAT: all variant prices are treated as net for now, a sample shows some include VAT (follow-up T166, deferred), set the constitution v1.2.0 ratification date, and ADR-018, ADR-019 and ADR-020 are accepted (2026-11-07).
