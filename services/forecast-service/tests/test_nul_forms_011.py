"""Feature 011 (T091): a NUL byte in a multipart text field (the dataset name, the file name) is refused before anything is stored.

PostgreSQL cannot store U+0000, so it used to come back as a server error; the guard in ``create_service_app`` cannot read a multipart body (the file bytes share it).
"""

import io

from test_imports_api import api, h  # noqa: F401  (the same app fixture and headers)


def raw_multipart(fields, filename, data=b"sku;day;qty\n"):
    """A multipart body built by hand: httpx writes a NUL in a file name as %00, a custom client can send the raw byte."""
    b = "BOUNDARY"
    text = "".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in fields.items())
    text += f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: text/csv\r\n\r\n'
    return text.encode() + data + f"\r\n--{b}--\r\n".encode(), f"multipart/form-data; boundary={b}"


def test_a_nul_in_the_dataset_name_is_refused_and_nothing_is_stored(api):  # noqa: F811
    res = api.post("/imports", files={"file": ("datos.csv", io.BytesIO(b"sku;day;qty\n"))}, data={"name": "Ho\x00ja"}, headers=h("buyer"))
    assert res.status_code == 422 and res.json() == {"detail": "invalid_input"}
    assert api.get("/imports", headers=h("buyer")).json() in ([], {"datasets": []}) or not api.get("/imports", headers=h("buyer")).json().get("datasets")


def test_a_nul_in_the_file_name_is_refused(api):  # noqa: F811
    body, ctype = raw_multipart({"name": "Hoja"}, "da\x00tos.csv")
    res = api.post("/imports", content=body, headers={**h("buyer"), "Content-Type": ctype})
    assert res.status_code == 422 and res.json() == {"detail": "invalid_input"}
