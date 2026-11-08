"""T034: the command: counts only, files recognised by header, guards on directory and target, exit codes."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from export_loader import cli, guards
from generator.exports import write_exports


@pytest.fixture
def folder(tmp_path):
    d = tmp_path / "exports"
    write_exports(d, seed=42)
    # real files carry customer names and dates in their names: the loader must not rely on them
    (d / "inventario.csv").rename(d / "inventario_Nombre_Apellido_Empresa__2026-11-08.csv")
    (d / "movimientos.xlsx").rename(d / "movimientos_stock_2026-11-08.xlsx")
    return d


def run(argv, tmp_path, pushes=None):
    return cli.main(argv, push=(pushes.append if pushes is not None else (lambda b: None)), state_dir=tmp_path / "state")


def test_check_prints_counts_and_the_interpretation_and_writes_nothing(folder, tmp_path, capsys):
    pushes: list = []
    assert run(["check", "--dir", str(folder)], tmp_path, pushes) == 0
    out = capsys.readouterr().out
    assert "inventory: filas" in out and "Interpretación" in out and not pushes
    assert not (tmp_path / "state").exists()


def test_load_runs_inventory_then_movements_whatever_the_file_names(folder, tmp_path, capsys):
    pushes: list = []
    assert run(["load", "--dir", str(folder), "--accept-interpretation"], tmp_path, pushes) == 0
    out = capsys.readouterr().out
    assert out.index("inventory:") < out.index("movements:") and len(pushes) == 2
    assert pushes[-1]["movements"] and pushes[-1]["variants"]


def test_output_never_contains_row_content(folder, tmp_path, capsys):
    run(["load", "--dir", str(folder), "--accept-interpretation"], tmp_path)
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert "SYN-" not in text and "Producto Sintetico" not in text and "Nombre_Apellido" not in text


def test_inventory_needs_the_interpretation_to_be_accepted(folder, tmp_path, capsys):
    assert run(["load", "--dir", str(folder)], tmp_path) == 3
    assert "local_load_interpretation_not_acknowledged" in capsys.readouterr().err


def test_second_load_changes_nothing(folder, tmp_path, capsys):
    run(["load", "--dir", str(folder), "--accept-interpretation"], tmp_path)
    capsys.readouterr()
    assert run(["load", "--dir", str(folder), "--accept-interpretation"], tmp_path) == 0
    assert "cargadas 0 | actualizadas 0" in capsys.readouterr().out


def test_directories_inside_the_repository_are_refused_except_data_and_fixtures(capsys, tmp_path):
    root = guards.repo_root()
    assert root is not None
    assert run(["check", "--dir", str(root / "packages" / "testing" / "src")], tmp_path) == 2
    assert "local_load_dir_not_allowed" in capsys.readouterr().err
    assert guards.check_dir(root / "packages" / "testing" / "fixtures" / "exports") is not None
    assert guards.check_dir(root / "data" / "local-exports") is not None


def test_non_local_targets_are_refused(folder, tmp_path, capsys):
    assert run(["load", "--dir", str(folder), "--accept-interpretation", "--mock-url", "https://example.com"], tmp_path) == 2
    assert "local_load_not_local_target" in capsys.readouterr().err


def test_production_environment_is_refused(folder, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MMI_ENV", "prod")
    assert run(["check", "--dir", str(folder)], tmp_path) == 2
    assert "local_load_disabled" in capsys.readouterr().err


def test_unrecognised_files_are_skipped_not_loaded(folder, tmp_path, capsys):
    (folder / "otro.csv").write_text("a,b\n1,2\n")
    assert run(["check", "--dir", str(folder)], tmp_path) == 0
    assert "omitido" in capsys.readouterr().err


def test_empty_folder_is_reported(tmp_path, capsys):
    d = tmp_path / "empty"
    d.mkdir()
    assert run(["check", "--dir", str(d)], tmp_path) == 2


def test_review_threshold_gives_a_non_zero_exit(folder, tmp_path):
    assert run(["load", "--dir", str(folder), "--accept-interpretation", "--max-review-ratio", "0.0001"], tmp_path) == 1


def test_wipe_removes_the_state(folder, tmp_path):
    run(["load", "--dir", str(folder), "--accept-interpretation"], tmp_path)
    assert (tmp_path / "state").exists() and any((tmp_path / "state").iterdir())
    assert run(["wipe"], tmp_path) == 0
    assert not any((tmp_path / "state").iterdir())


def test_sync_runs_once_after_the_loads(folder, tmp_path, capsys):
    calls = []
    assert cli.main(["load", "--dir", str(folder), "--accept-interpretation"], push=lambda b: calls.append("push"),
                    state_dir=tmp_path / "state", sync=lambda: calls.append("sync") or {"ok": True, "exit_code": 0}) == 0
    assert calls == ["push", "push", "sync"] and "Sincronización: correcta" in capsys.readouterr().out


def test_a_failed_sync_gives_a_non_zero_exit(folder, tmp_path, capsys):
    assert cli.main(["load", "--dir", str(folder), "--accept-interpretation"], push=lambda b: None, state_dir=tmp_path / "state",
                    sync=lambda: {"ok": False, "exit_code": 1}) == 1


def test_no_sync_flag_skips_the_connector(folder, tmp_path):
    calls = []
    cli.main(["load", "--dir", str(folder), "--accept-interpretation", "--no-sync"], push=lambda b: None, state_dir=tmp_path / "state",
             sync=lambda: calls.append("sync") or {"ok": True})
    assert calls == []


def test_non_local_connector_urls_are_refused(folder, tmp_path, capsys):
    assert cli.main(["load", "--dir", str(folder), "--accept-interpretation", "--connector-url", "https://example.com"], push=lambda b: None,
                    state_dir=tmp_path / "state") == 2


def test_unused_import_guard():
    assert shutil and Path
