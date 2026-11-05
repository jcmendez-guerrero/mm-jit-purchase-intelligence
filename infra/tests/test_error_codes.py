"""T156: services return stable error codes, never user-facing free text (FR-028). The BFF maps codes to the es-ES catalogue."""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE = re.compile(r"[a-z][a-z0-9_:]*")
SERVICES = ["procurement-service", "inventory-service", "forecast-service", "siweb-cost-writer", "siweb-connector"]   # api-bff owns the user-facing texts


def http_exceptions():
    for svc in SERVICES:
        for path in (ROOT / "services" / svc / "src").rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", "")) == "HTTPException":
                    yield path.relative_to(ROOT), node


def is_code(expr: ast.AST) -> bool:
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return bool(CODE.fullmatch(expr.value))
    if isinstance(expr, ast.Call) and getattr(expr.func, "id", "") == "error_code":
        return True
    if isinstance(expr, ast.Attribute) and expr.attr == "code":
        return True
    if isinstance(expr, ast.IfExp):
        return is_code(expr.body) and is_code(expr.orelse)
    return False


def test_every_http_error_carries_a_code_not_a_sentence():
    seen = list(http_exceptions())
    assert len(seen) > 30                                              # the scan really finds the endpoints
    bad = [f"{p}:{n.lineno}" for p, n in seen if (len(n.args) < 2 and not any(k.arg == "detail" for k in n.keywords)) or
           (len(n.args) >= 2 and not is_code(n.args[1]))]
    assert not bad, f"free-text error details (use a code or error_code(exc)): {bad}"


def test_exception_classes_used_in_apis_have_snake_case_codes():
    from_pkg = (ROOT / "packages/contracts/python/mmi_common/errors.py").read_text()
    assert "def error_code" in from_pkg
    namespace: dict[str, object] = {}
    exec(compile(from_pkg, "errors.py", "exec"), namespace)   # noqa: S102 - our own tiny module, to test it in isolation
    code = namespace["error_code"]

    class ConcurrencyError(Exception):
        pass

    class WithCode(Exception):
        code = "version_conflict"

    assert code(ConcurrencyError("x")) == "concurrency" and code(WithCode("y")) == "version_conflict" and code(ValueError("z")) == "value"
