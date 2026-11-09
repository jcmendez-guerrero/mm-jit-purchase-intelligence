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
| 5 (SYN-005) | 1 | L5a | 2 | 1.00 | sup-a | +400 d |
| 5 (SYN-005) | 1 | L5b | 3 | 2.00 | sup-b | +400 d |

SYN-005 has stock from two suppliers. SYN-004 also has an old cost row from sup-a (lot OLDA, 9.00) with no stock: it must not put SYN-004 in sup-a's figures.

## Expected figures

| Figure | All | Warehouse 1 | Warehouse 2 | Supplier sup-a | Supplier sup-b |
|--------|-----|-------------|-------------|----------------|----------------|
| Stock value (EUR) | 100.00 | 40.00 | 60.00 | 42.00 | 58.00 |
| Expiring value (EUR) | 60.00 | 0.00 | 60.00 | 20.00 | 40.00 |
| Valued with estimate (count) | 1 | 1 | 0 | 0 | 1 |
| Unvalued lots (count) | 1 | 1 | 0 | 0 | 0 |

Arithmetic: all = 10x2 + 5x4 + 4x3 + 8x5 + 2x1 + 3x2 = 20 + 20 + 12 + 40 + 2 + 6 = 100. Warehouse 1 = 20 + 12 + 2 + 6 = 40. sup-a = 20 + 20 + 2 = 42. sup-b = 12 + 40 + 6 = 58. Warehouse 2 = 20 + 40 = 60. Expiring: L2 5x4 = 20 and L4 8x5 = 40 (L1, L9 and the unvalued lot expire later).

## Categories

SYN-001 is A, SYN-002, SYN-003 and SYN-005 are B, SYN-004 is C; SYN-003 and SYN-004 belong to a clinically critical product.

## Demand

SYN-001: 3 units a day in warehouse 1 for 90 days. SYN-002: 1 unit a day in warehouse 1 for 90 days; today's row is censored. SYN-003 and SYN-004 have no demand ("sin demanda").

### Expected demand and forecast (T021)

| Figure | Value | Why |
|--------|-------|-----|
| Demand, last 60 days (units) | 239 | SYN-001: 3 x 60 = 180; SYN-002: 1 x 59 = 59 (today's row is censored and left out) |
| Daily average | 3.98 | 239 / 60 |
| Censored rows left out | 1 | SYN-002, today |
| Demand in warehouse 2 | no data | no sales there |
| Forecast, next 28 days, with daily means 2.0 / 0.5 / 1.0 for SYN-001 / 002 / 005 | 98.00 units | 3.5 x 28; SYN-003 and SYN-004 have none and are counted as incomplete (2) |

Capital tied up (stock at cost plus confirmed unreceived orders) and the purchasing budget are added with T022 and T091, because the open-orders amount and the caps come from the procurement service.
