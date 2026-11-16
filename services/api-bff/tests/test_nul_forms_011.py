"""Feature 011 (T091): the gateway refuses a NUL byte in the dataset name or the file name of an import upload before forwarding anything."""

from unittest.mock import AsyncMock

from test_imports_rbac import call
from tests_support import headers_for


def raw_multipart(fields, filename, data=b"sku;day;qty\n"):
    """A multipart body built by hand: httpx writes a NUL in a file name as %00, a custom client can send the raw byte."""
    b = "BOUNDARY"
    text = "".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in fields.items())
    text += f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: text/csv\r\n\r\n'
    return text.encode() + data + f"\r\n--{b}--\r\n".encode(), f"multipart/form-data; boundary={b}"


def test_a_nul_in_the_name_or_the_file_name_is_refused_and_nothing_is_forwarded(role_store):
    fc = AsyncMock()
    for fields, filename in (({"name": "Ho\x00ja"}, "datos.csv"), ({"name": "Hoja"}, "da\x00tos.csv")):
        body, ctype = raw_multipart(fields, filename, b"SKU;Fecha\n")
        res = call("POST", "/api/imports", {**headers_for("buyer-1", ["viewer", "buyer"], mfa_age_seconds=10), "Content-Type": ctype}, fc, content=body)
        assert res.status_code == 422 and res.json() == {"detail": "invalid_input"}
    fc.forward_raw.assert_not_called()
