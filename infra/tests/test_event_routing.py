"""T146: every event a service publishes reaches a queue that exists and a consumer that handles its type.

The services cannot import each other, so this reads their source: producers' SUBSCRIPTIONS maps (event type -> queues),
consumers' queue name and the event types they handle, and the queues declared in infra/bicep/main.bicep.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVENT = re.compile(r"^[a-z]+(\.[a-z_]+)+\.v\d+$")

PRODUCERS = {
    "siweb-connector": "services/siweb-connector/src/outbox/publisher.py",
    "inventory-service": "services/inventory-service/src/demand/publisher.py",
    "forecast-service": "services/forecast-service/src/runs/runner.py",
    "procurement-service": "services/procurement-service/src/proposals/publisher.py",
    "siweb-cost-writer": "services/siweb-cost-writer/src/writer/flow.py",
}
CONSUMERS = {  # queue -> module(s) whose handler tables define what the queue accepts
    "inventory-in": ["services/inventory-service/src/projections/consumer.py"],
    "forecast-in": ["services/forecast-service/src/runs/consumer.py"],
    "procurement-in": ["services/procurement-service/src/consumer.py"],
    "costwriter-in": ["services/siweb-cost-writer/src/writer/consumer.py"],
}


def subscriptions(path: str) -> dict[str, list[str]]:
    tree = ast.parse((ROOT / path).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SUBSCRIPTIONS" for t in node.targets):
            out: dict[str, list[str]] = {}
            assert isinstance(node.value, ast.Dict)
            for k, v in zip(node.value.keys, node.value.values, strict=True):
                key = ast.literal_eval(k) if isinstance(k, ast.Constant) else _resolve(tree, k)
                out[key] = ast.literal_eval(v)
            return out
    raise AssertionError(f"no SUBSCRIPTIONS in {path}")


def _resolve(tree: ast.AST, node: ast.AST | None) -> str:
    """A constant referenced by name (EVENT_TYPE = "x.v1")."""
    assert isinstance(node, ast.Name)
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == node.id for t in n.targets):
            return str(ast.literal_eval(n.value))
    raise AssertionError(node.id)


def handled_types(paths: list[str]) -> set[str]:
    types: set[str] = set()
    for p in paths:
        for n in ast.walk(ast.parse((ROOT / p).read_text())):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and EVENT.match(n.value):
                types.add(n.value)
    return types


def bicep_queues() -> set[str]:
    text = (ROOT / "infra/bicep/main.bicep").read_text()
    block = re.search(r"var queueNames = \[(.*?)\]", text, re.S)
    assert block
    return set(re.findall(r"'([a-z-]+)'", block.group(1)))


def test_every_subscribed_queue_is_declared_in_the_infrastructure():
    declared = bicep_queues()
    for svc, path in PRODUCERS.items():
        for etype, queues in subscriptions(path).items():
            for q in queues:
                assert q in declared, f"{svc}: {etype} goes to {q}, which main.bicep does not create"


def test_every_published_event_type_is_handled_by_the_consumer_of_each_queue_it_is_sent_to():
    for svc, path in PRODUCERS.items():
        for etype, queues in subscriptions(path).items():
            for q in queues:
                if q == "bff-notifications":
                    continue                                  # consumed by the BFF notification feed (US6)
                assert q in CONSUMERS, f"{svc}: no consumer module registered for queue {q}"
                assert etype in handled_types(CONSUMERS[q]), f"{svc}: {etype} is sent to {q} but its consumer has no handler for it"


def test_every_consumer_queue_name_matches_its_declaration():
    for q, paths in CONSUMERS.items():
        text = "".join((ROOT / p).read_text() for p in paths)
        assert re.search(rf'QUEUE\s*=\s*"{q}"', text), f"{paths[0]} does not consume {q}"
        assert q in bicep_queues()


def test_events_documented_in_the_contract_have_a_producer():
    doc = (ROOT / "specs/001-mmi-purchase-intelligence/contracts/events.md").read_text()
    documented = set(re.findall(r"\| ([a-z.]+\.v\d+) \|", doc))
    produced = {e for path in PRODUCERS.values() for e in subscriptions(path)}
    missing = documented - produced
    assert not missing, f"documented but never published: {sorted(missing)}"
