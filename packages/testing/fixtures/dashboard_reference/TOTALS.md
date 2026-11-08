# Dashboard reference dataset: expected totals

Fully synthetic. `dataset.json` is the data; this file is the independently computed expectation. "Today" is 2026-11-09. Value = quantity per lot x lot acquisition cost (never the ERP price). Expiring means within 60 days.

## Lots and costs

| Variant (SKU) | Warehouse | Lot | Qty | Unit cost | Supplier | Expires |
|---------------|-----------|-----|-----|-----------|----------|---------|
| 1 (SYN-001) | 1 | L1 | 10 | 2.00 | sup-a | +400 d |
| 1 (SYN-001) | 2 | L2 | 5 | 4.00 | sup-a | +10 d |
| 2 (SYN-002) | 1 | L9 | 4 | 3.00 (fallback from lot OLD, estimated) | sup-b | +400 d |
| 3 (SYN-003) | 1 | none | 6 | no cost (unvalued) | - | +400 d |
| 4 (SYN-004) | 2 | L4 | 8 | 5.00 | sup-b | +45 d |

## Expected figures

| Figure | All | Warehouse 1 | Warehouse 2 | Supplier sup-a | Supplier sup-b |
|--------|-----|-------------|-------------|----------------|----------------|
| Stock value (EUR) | 92.00 | 32.00 | 60.00 | 40.00 | 52.00 |
| Expiring value (EUR) | 60.00 | 0.00 | 60.00 | 20.00 | 40.00 |
| Valued with estimate (count) | 1 | 1 | 0 | 0 | 1 |
| Unvalued lots (count) | 1 | 1 | 0 | 0 | 0 |

Arithmetic: all = 10x2 + 5x4 + 4x3 + 8x5 = 20 + 20 + 12 + 40 = 92. Warehouse 1 = 20 + 12 = 32. Warehouse 2 = 20 + 40 = 60. Expiring: L2 5x4 = 20 and L4 8x5 = 40 (L1, L9 and the unvalued lot expire later).

## Categories

SYN-001 is A, SYN-002 and SYN-003 are B, SYN-004 is C; SYN-003 and SYN-004 belong to a clinically critical product.

## Demand

SYN-001: 3 units a day in warehouse 1 for 90 days. SYN-002: 1 unit a day in warehouse 1 for 90 days; today's row is censored. SYN-003 and SYN-004 have no demand ("sin demanda").

Demand, forecast, capital and budget totals are added by the tasks that implement those indicators (T021, T022) after the owner confirms the capital definition (T003).
