"""MMI-7 T037 (FR-021, FR-022, FR-023): seed data is MMI-owned. It can never produce an ERP request, never be read by another service, and never mix with locally loaded export data."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORECAST = ROOT / "services/forecast-service/src"
SEED_MODULES = [*(FORECAST / "seeds").glob("*.py"), FORECAST / "imports_api.py", FORECAST / "runs/seeds.py"]
SEED_TABLES = re.compile(r"\bseed_(datasets|rows|quarantine|mappings)\b")
HTTP_CLIENTS = re.compile(r"^\s*(import|from)\s+(httpx|requests|urllib\.request|aiohttp|http\.client|socket)\b", re.M)      # urllib.parse (file:// references) is not a network client


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_seed_code_has_no_http_client_and_no_siweb_reference():
    for f in SEED_MODULES:
        text = source(f)
        assert not HTTP_CLIENTS.search(text), f"{f.relative_to(ROOT)} imports an HTTP client"
        assert "siweb" not in text.lower().replace("id de variante siweb", ""), f"{f.relative_to(ROOT)} names Siweb"


def test_no_other_service_reads_or_writes_the_seed_tables():
    offenders = [str(f.relative_to(ROOT)) for svc in (ROOT / "services").iterdir() if svc.name != "forecast-service" for f in (svc / "src").rglob("*.py") if SEED_TABLES.search(source(f))]
    assert not offenders, f"seed tables referenced outside the forecast service: {offenders}"


def test_the_siweb_services_know_nothing_about_seed_datasets():
    for name in ("siweb-connector", "siweb-cost-writer"):
        for f in (ROOT / "services" / name / "src").rglob("*.py"):
            text = source(f).lower()
            assert "seed_" not in text and "predictive" not in text, f"{f.relative_to(ROOT)} refers to seed data"


def test_seed_code_never_touches_the_local_export_loader_or_its_surrogate_ids():
    for f in SEED_MODULES:
        text = source(f)
        assert "export_loader" not in text and "SURROGATE_BASE" not in text and "9_000_000" not in text, f"{f.relative_to(ROOT)} mixes in locally loaded export data"
