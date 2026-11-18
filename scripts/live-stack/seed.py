"""Loads the synthetic dashboard reference dataset into the inventory database of a local stack (feature 014, T006).

Synthetic data only: the data is `packages/testing/fixtures/dashboard_reference/dataset.json`, mapped to tables by the same function the service tests use, so the figures
on screen equal the documented totals in TOTALS.md. The script refuses any host that is not this machine, and refuses a database that already holds products, so it can
never mix the fixture with data collected from the ERP or loaded from real exports.

    uv run python scripts/live-stack/seed.py --database-url postgresql+psycopg://inventory_svc:dev-only-local@127.0.0.1:55432/mmi
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "packages" / "contracts" / "python"), str(ROOT / "services" / "inventory-service" / "src"), str(ROOT / "services" / "inventory-service" / "tests")]

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", ""}


class SeedRefused(Exception):
    pass


def seed(url: str, create_tables: bool = False) -> dict[str, int]:
    """Seeds the database at ``url``. ``create_tables`` is for a throw-away SQLite database; a real stack gets its tables from the service migrations."""
    from dashboard.kpis import refresh_aggregates
    from db.tables import metadata, products
    from reference_dataset import NOW, TODAY, seed_reference
    from sqlalchemy import create_engine, func, select

    host = urlparse(url).hostname or ""
    if url.split(":", 1)[0].startswith("postgresql") and host not in LOCAL_HOSTS:
        raise SeedRefused(f"refusing host {host!r}: the reference dataset is loaded only into a database on this machine")
    engine = create_engine(url)
    if create_tables:
        metadata.create_all(engine)
    with engine.connect() as c:
        if c.execute(select(func.count()).select_from(products)).scalar_one():
            raise SeedRefused("the database already holds products: the fixture is never mixed with other data")
    ds = seed_reference(engine)
    with engine.begin() as c:
        written = refresh_aggregates(c, TODAY, None, NOW)
    return {"variants": len(ds["variants"]), "lots": len(ds["lots"]), "aggregate_rows": written}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--database-url", required=True)
    args = ap.parse_args()
    try:
        out = seed(args.database_url)
    except SeedRefused as exc:
        print(f"seed refused: {exc}", file=sys.stderr)
        return 2
    print(f"seeded the synthetic reference dataset: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
