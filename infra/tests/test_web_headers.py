"""T038: the web server sends the standard security headers, and the content security policy stays strict."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONF = (ROOT / "apps/web/nginx.conf.template").read_text(encoding="utf-8")


def header(name: str) -> str:
    m = re.search(rf'add_header {name} "([^"]+)" always;', CONF)
    assert m, f"{name} missing (it must be set with `always` so error pages carry it too)"
    return m.group(1)


def test_standard_headers_are_present():
    assert header("X-Content-Type-Options") == "nosniff"
    assert header("X-Frame-Options") == "DENY"
    assert header("Referrer-Policy") == "no-referrer"
    assert "geolocation=()" in header("Permissions-Policy")
    assert "server_tokens off;" in CONF


def test_the_content_security_policy_is_strict():
    csp = header("Content-Security-Policy")
    directives = dict(d.strip().split(" ", 1) for d in csp.split(";") if d.strip())
    assert directives["default-src"] == "'self'"
    assert directives["script-src"] == "'self'"                       # no inline scripts, no eval, no third-party scripts
    assert "'unsafe-eval'" not in csp and "*" not in csp.replace("https://", "")
    assert directives["frame-ancestors"] == "'none'" and directives["object-src"] == "'none'"
    assert directives["connect-src"] == "'self'"                      # the SPA talks only to its own origin
    third_parties = set(re.findall(r"https://[a-z.]+", csp))
    assert third_parties <= {"https://fonts.googleapis.com", "https://fonts.gstatic.com"}, third_parties


def test_the_built_page_needs_no_inline_script():
    index = (ROOT / "apps/web/index.html").read_text(encoding="utf-8")
    inline = [m for m in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.+?)</script\s*>", index, re.S | re.I) if m.strip()]
    assert not inline
