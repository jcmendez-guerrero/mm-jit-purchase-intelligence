"""T014a (inventory, FR-023): responses carry UTC timestamps, decimal strings and SKUs only; no Siweb variant id appears."""

import json
import re
from datetime import datetime, timedelta

from conftest import auth
from test_quality_api import FROM, TO, seed_case

SIWEB_ID_KEYS = re.compile(r'"(variant_id|product_id|external_id|contact_id|warehouse_id)"')


def _walk(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _first_flag_day(client, sku):
    return client.get(f"/quality/products/{sku}/anomalies", headers=auth()).json()["anomalies"][0]["day"]


def _responses(client, engine):
    sku, _ = seed_case(engine, "outlier")
    client.post("/quality/recompute", headers=auth("buyer"))
    client.put(f"/quality/products/{sku}/anomalies/{_first_flag_day(client, sku)}", json={"decision": "accepted"}, headers=auth("buyer"))
    paths = [f"/quality/products/{sku}?from={FROM}&to={TO}", f"/quality/products/{sku}/anomalies", "/quality/portfolio", "/quality/portfolio/products?bucket=class&key=AX"]
    return sku, [client.get(p, headers=auth()).json() for p in paths]


def test_timestamps_are_utc_and_amounts_are_decimal_strings(client, engine):
    _, bodies = _responses(client, engine)
    stamps = [v for body in bodies for k, v in _walk(body) if k in ("built_at", "decided_at") and v]
    assert stamps
    for text in stamps:
        assert datetime.fromisoformat(text).utcoffset() == timedelta(0), text
    for body in bodies:
        for k, v in _walk(body):
            if k in ("original_value", "coverage_ratio", "rejected_share", "anomaly_share") and v is not None:
                assert isinstance(v, str), (k, v)


def test_users_see_skus_and_no_siweb_ids(client, engine):
    sku, bodies = _responses(client, engine)
    text = json.dumps(bodies)
    assert sku in text
    assert not SIWEB_ID_KEYS.search(text)
