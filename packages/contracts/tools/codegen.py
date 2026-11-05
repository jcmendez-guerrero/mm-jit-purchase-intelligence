"""Generate Pydantic models (and TypeScript types when json-schema-to-typescript is available)."""

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cfg = tomllib.loads((ROOT / "codegen.toml").read_text())


def python_models() -> None:
    out = ROOT / cfg["python"]["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    for d in cfg["python"]["input_dirs"]:
        subprocess.run(
            [sys.executable, "-m", "datamodel_code_generator", "--input", str(ROOT / d),
             "--output", str(out / d), *cfg["python"]["args"]],
            check=True,
        )
    (out / "__init__.py").write_text('"""Generated from JSON Schema. Do not edit."""\n')


def typescript_types() -> None:
    if not shutil.which("npx"):
        print("npx not found; skipping TypeScript generation")
        return
    out = (ROOT / cfg["typescript"]["output_dir"]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    for d in cfg["typescript"]["input_dirs"]:
        subprocess.run(["npx", "--yes", "json-schema-to-typescript", str(ROOT / d), "--output", str(out / d)], check=True)


if __name__ == "__main__":
    python_models()
    typescript_types()
