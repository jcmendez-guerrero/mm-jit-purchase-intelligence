"""T034: ``python -m export_loader check|load|wipe`` (specs/004-local-test-data-suppliers/contracts/local-loader.md).

Prints counts only, never row content. Refuses folders inside the repository (except ``data/`` and the synthetic fixtures),
non-local targets and production environments. Files are recognised by their header row, not by name.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from . import guards
from .push_costs import http_push_costs
from .readers import identify
from .service import AppReader, LoaderService
from .to_procurement import http_push_links, http_push_suppliers
from .validate_file import LoaderFileError, load_limits

ORDER = ("suppliers", "inventory", "movements")          # suppliers first: the inventory load links products to them
DEFAULT_MOCK = "http://localhost:8089"
DEFAULT_CONNECTOR = "http://localhost:8092"


def default_state_dir() -> Path:
    if env := os.environ.get("MMI_LOADER_STATE_DIR"):
        return Path(env)
    root = guards.repo_root()
    return (root / "data" / "loader-state") if root else Path.home() / ".mmi-loader-state"


def http_push(mock_url: str) -> Callable[[dict[str, Any]], None]:
    def push(body: dict[str, Any]) -> None:
        r = httpx.post(f"{mock_url.rstrip('/')}/__mock__/load", json=body, timeout=120)
        r.raise_for_status()

    return push


def http_sync(connector_url: str) -> Callable[[], dict[str, Any]]:
    """Ask the connector (local only, flag-guarded) to collect from the mock, so the pipeline sees the new data."""
    from mmi_common.servicetoken import service_token

    def sync() -> dict[str, Any]:
        token = service_token("api://mmi-siweb-connector", "svc-local-loader-cli", ["local-loader"])
        r = httpx.post(f"{connector_url.rstrip('/')}/internal/local-sync", headers={"Authorization": f"Bearer {token}"}, timeout=1800)
        r.raise_for_status()
        return dict(r.json())

    return sync


def _line(res: dict[str, Any]) -> str:
    return (f"{res['kind']}: filas {res['rows']} | cargadas {res['loaded']} | actualizadas {res['updated']} | sin cambios {res['unchanged']} | "
            f"en revisión {res['quarantined']} | excluidas {res['excluded']} | servicios {res['services']} | diferencias {res.get('differences', 0)}")


def _scan(folder: Path, svc_limits) -> dict[str, tuple[str, bytes]]:
    found: dict[str, tuple[str, bytes]] = {}
    skipped = 0
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() not in {".csv", ".xlsx"} or not f.is_file() or f.name.startswith("."):
            continue
        data = f.read_bytes()
        kind = identify(f.name, data, svc_limits)
        if kind in ORDER and kind not in found:
            found[kind] = (f.name, data)
        else:
            skipped += 1
    if skipped:                                   # file names can carry customer data: only the count is printed
        print(f"{skipped} archivo(s) omitido(s): no son una exportación admitida o ya hay otra del mismo tipo.", file=sys.stderr)
    return found


def main(argv: list[str] | None = None, push: Callable[[dict[str, Any]], None] | None = None, state_dir: Path | None = None,
         reader: AppReader | None = None, sync: Callable[[], dict[str, Any]] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="export_loader")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "load"):
        s = sub.add_parser(name)
        s.add_argument("--dir", required=True)
        s.add_argument("--accept-interpretation", action="store_true")
        s.add_argument("--max-review-ratio", type=float, default=0.10)
        s.add_argument("--mock-url", default=os.environ.get("MMI_SIWEB_MOCK_URL", DEFAULT_MOCK))
        s.add_argument("--connector-url", default=os.environ.get("MMI_CONNECTOR_URL", DEFAULT_CONNECTOR))
        s.add_argument("--no-sync", action="store_true", help="load into the mock but do not start the collection")
    sub.add_parser("wipe")
    args = ap.parse_args(argv)
    try:
        guards.check_environment()
        state = state_dir or default_state_dir()
        if args.cmd == "wipe":
            LoaderService(state, lambda _b: None).wipe()
            print("Datos locales eliminados.")
            return 0
        folder = guards.check_dir(Path(args.dir))
        guards.check_local_url(args.mock_url)
        guards.check_local_url(args.connector_url)
        limits = load_limits()
        costs_url = os.environ.get("MMI_PROCUREMENT_URL")
        remote = bool(costs_url) and push is None
        svc = LoaderService(state, push or http_push(args.mock_url), reader, limits, push_costs=http_push_costs(costs_url) if remote else None,
                            push_suppliers=http_push_suppliers(costs_url) if remote else None, push_links=http_push_links(costs_url) if remote else None)
        files = _scan(folder, limits)
        if not files:
            print("No se encontraron exportaciones reconocidas en la carpeta.", file=sys.stderr)
            return 2
        worst = 0.0
        for kind in ORDER:
            if kind not in files:
                continue
            name, data = files[kind]
            if args.cmd == "check":
                res = svc.check(kind, name, data)
                if kind == "inventory":
                    it = res.get("interpretations", {})
                    print(f"Interpretación: impuesto incluido en {it.get('tax_included_rows', 0)} filas, no incluido en {it.get('tax_excluded_rows', 0)}; "
                          f"hora local {it.get('timezone')}")
            else:
                res = svc.load(kind, name, data, acknowledge_interpretation=args.accept_interpretation)
            print(_line(res))
            worst = max(worst, res["quarantined"] / res["rows"] if res["rows"] else 0.0)
        if args.cmd == "load" and not args.no_sync:
            runner = sync or (http_sync(args.connector_url) if push is None else None)
            if runner is not None:
                outcome = runner()
                print("Sincronización: " + ("correcta" if outcome.get("ok") else f"con errores (código {outcome.get('exit_code')})"))
                if not outcome.get("ok"):
                    return 1
        if worst > args.max_review_ratio:
            print(f"Demasiadas filas en revisión ({worst:.0%} > {args.max_review_ratio:.0%}).", file=sys.stderr)
            return 1
        return 0
    except guards.GuardError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 2
    except LoaderFileError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
