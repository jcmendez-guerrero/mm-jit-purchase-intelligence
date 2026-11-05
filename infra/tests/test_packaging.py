"""The shared contracts package must work when installed from its wheel, not only from a repository checkout.

A first end-to-end run in containers showed every event rejected as "unknown event type": the schemas lived next to the
repository layout, not inside the package. This builds the wheel and validates an envelope from the unpacked copy.
"""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(shutil.which("uv") is None, reason="needs uv to build the wheel")


@pytest.fixture(scope="module")
def unpacked(tmp_path_factory):
    out = tmp_path_factory.mktemp("wheel")
    subprocess.run(["uv", "build", "--wheel", "--out-dir", str(out), str(ROOT / "packages/contracts")], check=True, capture_output=True)
    wheel = next(out.glob("*.whl"))
    dest = out / "site"
    with zipfile.ZipFile(wheel) as z:
        z.extractall(dest)
    return dest


def test_the_wheel_contains_every_event_schema(unpacked):
    packaged = {p.name for p in (unpacked / "mmi_common/schemas/events").glob("*.schema.json")}
    source = {p.name for p in (ROOT / "packages/contracts/events").glob("*.schema.json")}
    assert source and packaged == source


def test_an_envelope_validates_using_only_the_installed_package(unpacked, tmp_path):
    code = (
        "import sys; sys.path.insert(0, sys.argv[1])\n"
        "import mmi_common.bus as b, pathlib\n"
        "assert str(b.SCHEMA_DIR).startswith(sys.argv[1]), b.SCHEMA_DIR\n"
        "e = b.new_envelope('siweb.sync.completed.v1', 'r', b'{}', 'file:///x', '7d3b7c3e-1c0e-4f6a-9d58-0c7a1a2b3c4d')\n"
        "b.validate_envelope(e)\n"
        "print('ok')\n"
    )
    r = subprocess.run([sys.executable, "-I", "-c", code, str(unpacked)], capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0 and r.stdout.strip() == "ok", r.stderr[-800:]
