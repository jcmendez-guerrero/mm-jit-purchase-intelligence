# Quickstart: validate the SKU in the policy history

All data is synthetic (fixtures from `packages/testing`); nothing touches a real Siweb host.

## 1. Contract

```bash
cd packages/contracts && python -m pytest tests/test_mmi002_contracts.py -q
```

Expect: the five `sku` cases in [the delta](contracts/policy-history-row.delta.md) pass.

## 2. Procurement

```bash
cd services/procurement-service && python -m pytest tests/test_policy_api_011.py -q
```

Expect: list rows carry the SKU; unknown or blank gives null; rows are never dropped.

## 3. Gateway

```bash
cd services/api-bff && python -m pytest tests -q -k "admin_status or policies or no_money"
```

Expect: the `policy_history` card carries `sku`; the route-arithmetic guard still passes.

## 4. Web

```bash
cd apps/web && npx vitest run tests/unit
```

Expect: variant-id display test passes with the `AdminStatusScreen.tsx` baseline entry removed; i18n coverage passes with the new keys.

## 5. Gates

```bash
cd scripts && python -m gates run
```

Expect: contracts and isolation gates pass.

## Manual check (local)

Open the administration status screen as an administrator with seeded overrides: the policy column shows SKUs, a row with an unknown product shows the "no aplica" marker, and no numeric variant id appears.

## Load check (SC-004)

`test_a_history_of_200_rows_lists_with_a_sku_on_each` lists 200 synthetic rows with a SKU on each, and checks that `limit=20` (what the status screen asks for) returns only 20 rows.
