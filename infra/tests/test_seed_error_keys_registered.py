"""MMI-7 T061: every import error key the forecast service can return is in the shared catalogue (contract-first)."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODES = set(json.loads((ROOT / "packages/contracts/errors/error_codes.json").read_text(encoding="utf-8"))["codes"])
SOURCES = [*(ROOT / "services/forecast-service/src/seeds").glob("*.py"), ROOT / "services/forecast-service/src/imports_api.py"]
KEY = re.compile(r"""["'](import_[a-z0-9_]+)["']""")
NOT_ERROR_KEYS = {"import_job"}            # an audit entity name, not an error key


def test_every_import_error_key_used_by_the_forecast_service_is_in_the_catalogue():
    used = {k for f in SOURCES for k in KEY.findall(f.read_text(encoding="utf-8"))} - NOT_ERROR_KEYS
    assert used, "no import error keys found: the pattern or paths are wrong"
    assert not used - CODES, f"keys used but not in packages/contracts/errors/error_codes.json: {sorted(used - CODES)}"


def _load(path: str, name: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_erp_export_signatures_are_real_headers_of_the_export_layouts():
    """T066: seeds/export_shapes.py keeps its own copy of a few header names; each must be a header of the layout it claims (feature 004 formats)."""
    shapes = _load("services/forecast-service/src/seeds/export_shapes.py", "export_shapes")
    formats = _load("packages/testing/src/export_loader/formats.py", "export_formats")
    assert set(shapes._SHAPES) == set(formats.HEADERS)
    for layout, distinctive in shapes._SHAPES.items():
        real = {formats.fold(h) for h in formats.HEADERS[layout]}
        assert distinctive <= real, f"{layout}: not in the ERP export layout: {sorted(distinctive - real)}"
        assert len(distinctive) >= 3, f"{layout}: too few signature headers to tell the layout apart"


def test_the_gateway_forwards_no_import_key_of_its_own():
    used = set(KEY.findall((ROOT / "services/api-bff/src/routes/imports.py").read_text(encoding="utf-8")))
    assert not used - CODES, sorted(used - CODES)
