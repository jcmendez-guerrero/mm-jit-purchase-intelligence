"""Feature 011 (T091): a NUL byte in the supplier id of a price-list upload is refused before any query or audit write (PostgreSQL cannot store U+0000)."""


from conftest import auth
from test_api import seed

GOOD = b"variant_id;cost;includes_recargo;pack_size;lead_time_days;min_order_qty\n10;100;no;12;3;6\n"


def raw_multipart(fields, filename, data=b"sku;day;qty\n"):
    """A multipart body built by hand: httpx writes a NUL in a file name as %00, a custom client can send the raw byte."""
    b = "BOUNDARY"
    text = "".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in fields.items())
    text += f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: text/csv\r\n\r\n'
    return text.encode() + data + f"\r\n--{b}--\r\n".encode(), f"multipart/form-data; boundary={b}"


def test_a_nul_in_the_supplier_id_is_refused(client, engine):
    sid = seed(engine)
    body, ctype = raw_multipart({"supplier_id": sid + "\x00"}, "lista.csv", GOOD)
    res = client.post("/costs/import", content=body, headers={**auth("buyer"), "Content-Type": ctype})
    assert res.status_code == 422 and res.json() == {"detail": "invalid_input"}
    assert client.get("/costs", headers=auth()).json() == []


def test_a_nul_in_the_file_name_is_refused(client, engine):
    sid = seed(engine)
    body, ctype = raw_multipart({"supplier_id": sid}, "li\x00sta.csv", GOOD)
    res = client.post("/costs/import", content=body, headers={**auth("buyer"), "Content-Type": ctype})
    assert res.status_code == 422 and res.json() == {"detail": "invalid_input"}
    assert client.get("/costs", headers=auth()).json() == []
