"""Feature 011 (T062, owner decision): the stockout-censoring rule applies by scope, most specific first (product, then segment, then global)."""

from datetime import UTC, date, datetime

from conftest import auth
from db.tables import product_segments, products, stock_history, variants
from demand.rebuild import rebuild
from projections.rules import censoring_resolver
from sqlalchemy import insert, select
from test_review_and_metrics import T, add, snapshot

RULE = "/demand-rules/rules/min_zero_stock_days"


def catalogue(engine, critical_product=None):
    """Variant 1 (product 5, class A) and variant 2 (product 6, class B), both with a two-day stock-out."""
    with engine.begin() as c:
        for vid, pid, abc in ((1, 5, "A"), (2, 6, "B")):
            c.execute(insert(products).values(external_id=pid, name=f"P{pid}", status="active", missed_syncs=0, clinical_critical=(critical_product == pid)))
            c.execute(insert(variants).values(external_id=vid, product_id=pid, sku=f"SYN-{vid}", name="V", pack_size=1, uom="unit"))
            c.execute(insert(product_segments).values(variant_id=vid, abc=abc, xyz="X", pattern="smooth", forecast_eligible=True, reason="", metrics={},
                                                      computed_at=datetime(2026, 11, 9, tzinfo=UTC), run_id="r"))
    for vid in (1, 2):
        add(engine, vid * 10 + 1, "initial_stock", 4, T(1), variant=vid)
        add(engine, vid * 10 + 2, "sale_shipment", -4, T(2), variant=vid)          # out of stock from day 2
        add(engine, vid * 10 + 3, "purchase_receipt", 6, T(4), variant=vid)         # back on day 4
        snapshot(engine, vid, date(2026, 10, 6), 6)
    with engine.begin() as c:
        rebuild(c)


def censored(engine, vid):
    with engine.connect() as c:
        return sorted(r.day.day for r in c.execute(select(stock_history).where(stock_history.c.variant_id == vid, stock_history.c.censored)).all())


def put(client, value, scope="global", key=None, version=None, role="buyer"):
    body = {"value": value, "scope": scope, **({} if key is None else {"key": key})}
    return client.put(RULE, json=body, headers={**auth(role), **({} if version is None else {"If-Match": f'"{version}"'})})


def test_migration_0009_adds_scope_and_key_and_old_rows_stay_global():
    import importlib.util
    from pathlib import Path

    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0009_censoring_scope.py"
    spec = importlib.util.spec_from_file_location("mig0009", path)
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)
    eng = sa.create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(sa.text("create table censoring_rules (id integer primary key, rule varchar(40), value integer, valid_from date, revision integer, changed_by varchar(120))"))
        c.execute(sa.text("insert into censoring_rules (rule, value, valid_from, revision, changed_by) values ('min_zero_stock_days', 3, '2026-10-01', 1, 'u')"))
    with eng.begin() as c, Operations.context(MigrationContext.configure(c)):
        mig.upgrade()
    with eng.connect() as c:
        assert c.execute(sa.text("select scope, key from censoring_rules")).one() == ("global", "*")
    with eng.begin() as c, Operations.context(MigrationContext.configure(c)):
        mig.downgrade()
    assert {"scope", "key"}.isdisjoint({col["name"] for col in sa.inspect(eng).get_columns("censoring_rules")})
    assert (mig.revision, mig.down_revision) == ("0009", "0008")


def test_the_default_hides_a_short_stock_out_for_everyone(client, engine):
    catalogue(engine)
    assert censored(engine, 1) and censored(engine, 2)


def test_a_segment_rule_changes_only_its_segment_and_beats_the_global_rule(client, engine):
    catalogue(engine)
    assert put(client, 5).json()["revision"] == 1                                                 # global: short stock-outs are no longer hidden demand
    assert not censored(engine, 1) and not censored(engine, 2)
    with engine.begin() as c:                                    # every save recomputes the segments; seed the classes again as a real run would have them
        c.execute(product_segments.delete())
        for vid, abc in ((1, "A"), (2, "B")):
            c.execute(insert(product_segments).values(variant_id=vid, abc=abc, xyz="X", pattern="smooth", forecast_eligible=True, reason="", metrics={},
                                                      computed_at=datetime(2026, 11, 9, tzinfo=UTC), run_id="r"))
    assert put(client, 1, "segment", "A").json()["revision"] == 1                                 # class A keeps the strict rule
    assert censored(engine, 1) and not censored(engine, 2)


def test_a_product_rule_is_set_by_sku_and_beats_the_segment_rule(client, engine):
    catalogue(engine)
    put(client, 1, "segment", "A")
    assert censored(engine, 1)
    assert put(client, 5, "product", "syn-1").json()["revision"] == 1                             # people type the SKU, case ignored
    assert not censored(engine, 1) and censored(engine, 2)


def test_revisions_are_kept_per_scope_and_key(client, engine):
    catalogue(engine)
    assert put(client, 3).json()["revision"] == 1
    assert put(client, 2, "segment", "A").json()["revision"] == 1                                 # its own first revision, no If-Match needed
    assert put(client, 4, "segment", "A").status_code == 428
    assert put(client, 4, "segment", "A", version=1).json()["revision"] == 2
    stale = put(client, 6, "segment", "A", version=1)
    assert stale.status_code == 412 and stale.json()["current_version"] == 2
    assert put(client, 4, version=1).json()["revision"] == 2                                      # the global one is unaffected by the segment saves


def test_scope_key_and_value_are_validated(client, engine):
    catalogue(engine)
    assert put(client, 2, "planet").status_code == 422
    assert put(client, 2, "segment", "Z").status_code == 422
    assert put(client, 2, "segment").status_code == 422
    assert put(client, 2, "product", "NOPE").json()["detail"] == "sku_unknown"
    assert put(client, 99, "segment", "A").status_code == 422
    assert put(client, 2, "segment", "A", role="viewer").status_code == 403


def test_the_list_shows_every_saved_scope_with_the_sku_not_the_id(client, engine):
    catalogue(engine)
    put(client, 3)
    put(client, 2, "segment", "critical")
    put(client, 4, "product", "SYN-2")
    rules = client.get("/demand-rules", headers=auth()).json()["rules"]
    assert [(r["scope"], r["key"], r["value"]) for r in rules] == [("global", "*", 3), ("segment", "critical", 2), ("product", "SYN-2", 4)]
    assert all("variant_id" not in r for r in rules)


def test_the_resolver_follows_critical_before_class_and_product_before_both(client, engine):
    catalogue(engine, critical_product=5)                       # product 5 is clinically critical
    put(client, 7)                                              # global
    put(client, 3, "segment", "A")
    put(client, 2, "segment", "critical")
    with engine.connect() as c:
        resolve = censoring_resolver(c, "min_zero_stock_days")
        assert resolve(1) == 2                                  # critical wins over class A
        assert resolve(2) == 7                                  # class B has no rule: global
    put(client, 9, "product", "SYN-1")
    with engine.connect() as c:
        assert censoring_resolver(c, "min_zero_stock_days")(1) == 9


def test_the_audit_and_the_versions_carry_scope_and_key_but_no_ids(client, engine):
    catalogue(engine)
    put(client, 3, "segment", "A")
    put(client, 4, "product", "SYN-1")
    items = client.get("/policy-audit", headers=auth("admin")).json()["items"]
    afters = [i["after"] for i in items if i["action"] == "censoring_rule.saved"]
    assert {(a["scope"], a["key"]) for a in afters} == {("segment", "A"), ("product", "SYN-1")} and "variant_id" not in str(items)
    assert client.get("/export/series", headers=auth()).json()["rule_versions"]["censoring.min_zero_stock_days"] == 2      # one revision per scope, summed
