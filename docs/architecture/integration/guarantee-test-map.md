# Platform guarantees and the tests that cover them

Spec FR-013: each guarantee that must survive integration is mapped to existing tests. The security gate runs every file listed here, one pytest process per service or package (`python -m gates run --gate security`). The map was reviewed by reading each test's name and key assertions (T059); a first mapping had two wrong entries, corrected below. Review was by test names and the assertions quoted here, not by line-by-line reading of every test body.

| Guarantee | Covering test files | What they show |
|---|---|---|
| Role-based access | `services/api-bff/tests/test_auth_rbac.py`, `services/api-bff/tests/test_rbac_refusals.py` | a viewer cannot mutate; refusals are recorded in the audit chain and survive a restart; a revoked role or a deactivated user is refused even with a valid cookie; missing CSRF is refused |
| Second factor for sensitive operations | `services/api-bff/tests/test_auth_rbac.py`, `services/procurement-service/tests/test_writes.py`, `services/procurement-service/tests/test_median_cost.py` | step-up second factor required (gateway); release needs the buyer role and a fresh second factor (procurement, also for the median-cost release) |
| Audit trail | `services/inventory-service/tests/test_audit_chain.py`, `services/procurement-service/tests/test_writes.py`, `services/siweb-cost-writer/tests/test_write_flow.py` | the hash chain links, verifies and detects tampering or removal (inventory); every write step is in the tamper-evident trail (procurement); the audit names who released a write with old and new values (cost writer) |
| UTC timestamps (with the original string kept) | `packages/contracts/tests/test_common.py` | a naive local timestamp becomes UTC with the original string kept (`raw`) and the assumed zone recorded; offset timestamps are kept; DST gap and overlap are flagged ambiguous |
| Decimal money | `packages/contracts/tests/test_common.py`, `services/siweb-connector/tests/contract/test_minimisation.py`, `services/procurement-service/tests/test_median_cost.py` | `Money` addition is exact; a unit cost normalises to `Decimal`, never float; the median rounds half-up to whole cents |

## Known gaps in what these tests show

- **Audit trail:** the chain mechanism is tested in the inventory service; the other services' trails are tested for their own steps. Nothing tests one chain across services, and no test proves every service writes to its trail on every sensitive path.
- **UTC timestamps:** only the shared parser (`parse_siweb_timestamp`) is tested for the original-string rule. Services that store timestamps are not each checked for keeping the original string alongside the UTC value. (`services/inventory-service/tests/test_projections.py::test_utc_conversion_uses_madrid_local_time` also covers one service's conversion but is not in the gate yet.)
- **Decimal money:** covered for the shared type, the connector's normalisation and the median; other services' money arithmetic (margin rules, allocation) is tested elsewhere (`test_margin_rules.py`, `test_allocation.py`) but not part of this gate.
- **Second factor:** tested for the cost-write release and the gateway's step-up; the full list of sensitive operations was not enumerated here.

These are gaps in evidence, not known defects. A guarantee is considered mapped when at least one existing test exercises the rule it states; closing the gaps above needs new tests, which were not added here.

Other security checks in the gate: `infra/tests/test_security_abuse.py`, `infra/tests/test_erp_boundary.py`, `infra/tests/test_web_headers.py` and the export-signature guard `scripts/check_export_signatures.py`.
