"""MessageBus interface with in-memory and Azure Storage Queue implementations.

Delivery is at-least-once. Consumers deduplicate on ``event_id`` (see outbox.py inbox).
Messages that fail schema/checksum validation, are stale, or exceed the delivery limit end up
in the poison queue ``<queue>-poison`` so an alert can fire.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import jsonschema
from referencing import Registry, Resource

from .time import utc_now

DEFAULT_MAX_AGE = timedelta(hours=24)
MAX_AGE_OVERRIDES = {"procurement.cost.write_requested.v1": timedelta(hours=1)}
POISON_SUFFIX = "-poison"
_PACKAGED = Path(__file__).resolve().parent / "schemas" / "events"      # installed wheel
SCHEMA_DIR = _PACKAGED if _PACKAGED.is_dir() else Path(__file__).resolve().parents[2] / "events"   # repository checkout


class MessageRejected(Exception):
    """Schema, checksum or freshness validation failed."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def new_envelope(
    type_: str,
    resource_id: str,
    payload: bytes,
    payload_uri: str,
    correlation_id: str,
    schema_version: str = "1.0.0",
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "type": type_,
        "schema_version": schema_version,
        "occurred_at": (occurred_at or utc_now()).isoformat().replace("+00:00", "Z"),
        "correlation_id": correlation_id,
        "resource_id": resource_id,
        "payload_ref": {"uri": payload_uri, "sha256": sha256_hex(payload)},
    }


def _registry() -> Registry:
    reg: Registry = Registry()
    for f in SCHEMA_DIR.glob("*.schema.json"):
        reg = reg.with_resource("mmi/events/" + f.name, Resource.from_contents(json.loads(f.read_text())))
    return reg


def validate_envelope(envelope: dict[str, Any], now: datetime | None = None) -> None:
    """Validate against the schema registered for ``envelope['type']`` and check freshness."""
    type_ = envelope.get("type")
    schema_file = SCHEMA_DIR / f"{type_}.schema.json"
    if not isinstance(type_, str) or not schema_file.exists():
        raise MessageRejected(f"unknown event type: {type_!r}")
    schema = json.loads(schema_file.read_text())
    validator = jsonschema.Draft202012Validator(
        schema, registry=_registry(), format_checker=jsonschema.FormatChecker()
    )
    errors = sorted(validator.iter_errors(envelope), key=lambda e: list(e.path))
    if errors:
        raise MessageRejected(f"schema validation failed: {errors[0].message}")
    occurred = datetime.fromisoformat(envelope["occurred_at"].replace("Z", "+00:00"))
    max_age = MAX_AGE_OVERRIDES.get(type_, DEFAULT_MAX_AGE)
    if (now or utc_now()) - occurred > max_age:
        raise MessageRejected("message older than the freshness window")


def verify_payload(envelope: dict[str, Any], payload: bytes) -> None:
    if sha256_hex(payload) != envelope["payload_ref"]["sha256"]:
        raise MessageRejected("payload checksum mismatch")


@dataclass
class Received:
    receipt: str
    body: dict[str, Any]
    delivery_count: int


class MessageBus(ABC):
    @abstractmethod
    def send(self, queue: str, envelope: dict[str, Any]) -> None: ...

    @abstractmethod
    def receive(self, queue: str, max_messages: int = 1) -> list[Received]: ...

    @abstractmethod
    def complete(self, queue: str, receipt: str) -> None:
        """Acknowledge and delete."""

    @abstractmethod
    def abandon(self, queue: str, receipt: str) -> None:
        """Return to the queue for retry; moved to poison after the delivery limit."""

    @abstractmethod
    def poison(self, queue: str, receipt: str) -> None:
        """Move straight to the poison queue (validation failures)."""


@dataclass
class _Item:
    body: dict[str, Any]
    deliveries: int = 0
    in_flight: bool = False


@dataclass
class InMemoryBus(MessageBus):
    max_deliveries: int = 5
    queues: dict[str, dict[str, _Item]] = field(default_factory=dict)

    def _q(self, name: str) -> dict[str, _Item]:
        return self.queues.setdefault(name, {})

    def send(self, queue: str, envelope: dict[str, Any]) -> None:
        self._q(queue)[str(uuid.uuid4())] = _Item(json.loads(json.dumps(envelope)))

    def receive(self, queue: str, max_messages: int = 1) -> list[Received]:
        out: list[Received] = []
        for receipt, item in list(self._q(queue).items()):
            if item.in_flight:
                continue
            item.in_flight = True
            item.deliveries += 1
            out.append(Received(receipt, item.body, item.deliveries))
            if len(out) >= max_messages:
                break
        return out

    def complete(self, queue: str, receipt: str) -> None:
        self._q(queue).pop(receipt, None)

    def abandon(self, queue: str, receipt: str) -> None:
        item = self._q(queue).get(receipt)
        if item is None:
            return
        if item.deliveries >= self.max_deliveries:
            self.poison(queue, receipt)
        else:
            item.in_flight = False

    def poison(self, queue: str, receipt: str) -> None:
        item = self._q(queue).pop(receipt, None)
        if item is not None:
            self._q(queue + POISON_SUFFIX)[receipt] = _Item(item.body)

    def depth(self, queue: str) -> int:
        return len(self._q(queue))


class StorageQueueBus(MessageBus):
    """Azure Storage Queue implementation (Azurite locally). Uses the queue's own dequeue count.

    Authentication: connection string for Azurite in dev; managed identity in Azure
    (pass a ``QueueServiceClient`` built by the caller).
    """

    def __init__(self, service_client: Any, max_deliveries: int = 5, visibility_timeout: int = 60):
        self._svc = service_client
        self._max = max_deliveries
        self._vis = visibility_timeout
        self._pending: dict[str, Any] = {}

    def _client(self, queue: str) -> Any:
        client = self._svc.get_queue_client(queue)
        try:
            client.create_queue()
        except Exception:  # noqa: S110 - queue may already exist; real errors surface on first use
            pass
        return client

    def send(self, queue: str, envelope: dict[str, Any]) -> None:
        self._client(queue).send_message(json.dumps(envelope))

    def receive(self, queue: str, max_messages: int = 1) -> list[Received]:
        out = []
        for msg in self._client(queue).receive_messages(
            messages_per_page=max_messages, visibility_timeout=self._vis
        ):
            receipt = f"{msg.id}|{msg.pop_receipt}"
            self._pending[receipt] = msg
            out.append(Received(receipt, json.loads(msg.content), msg.dequeue_count))
            if len(out) >= max_messages:
                break
        return out

    def complete(self, queue: str, receipt: str) -> None:
        msg = self._pending.pop(receipt)
        self._client(queue).delete_message(msg.id, msg.pop_receipt)

    def abandon(self, queue: str, receipt: str) -> None:
        msg = self._pending.get(receipt)
        if msg is not None and msg.dequeue_count >= self._max:
            self.poison(queue, receipt)
        # otherwise the message reappears after the visibility timeout

    def poison(self, queue: str, receipt: str) -> None:
        msg = self._pending.pop(receipt)
        self._client(queue + POISON_SUFFIX).send_message(msg.content)
        self._client(queue).delete_message(msg.id, msg.pop_receipt)
