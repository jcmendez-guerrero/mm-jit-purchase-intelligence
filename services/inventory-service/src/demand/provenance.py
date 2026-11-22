"""T013: the one place that decides a demand value's provenance label (feature 018, FR-014).

Only demand collected from the ERP, under a real Siweb variant id, is ``observed``. Seed, locally loaded (feature 004,
surrogate ids from 9,000,000), imputed and unknown origins are never ``observed``: an unknown origin fails safe to
``estimated``, so a missing label can never present an estimate as a sale.
"""

from __future__ import annotations

OBSERVED = "observed"
ESTIMATED = "estimated"
MANUAL = "manual"
LABELS = (OBSERVED, ESTIMATED, MANUAL)

SURROGATE_BASE = 9_000_000                       # ids reserved for locally loaded SKUs; never real Siweb ids
ERP_ORIGINS = frozenset({"erp", "erp_sync"})


def provenance(origin: str | None, variant_id: int | None = None) -> str:
    if origin == MANUAL:
        return MANUAL
    if variant_id is not None and variant_id >= SURROGATE_BASE:
        return ESTIMATED                          # local-export ids are never ERP-observed, whatever the origin text says
    return OBSERVED if origin in ERP_ORIGINS else ESTIMATED
