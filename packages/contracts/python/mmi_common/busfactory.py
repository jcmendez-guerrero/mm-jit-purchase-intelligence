"""Build the message bus from the environment: Azurite connection string locally, managed identity in Azure."""

from __future__ import annotations

import os

from .bus import MessageBus, StorageQueueBus


def bus_from_env() -> MessageBus:
    conn = os.environ.get("MMI_QUEUE_CONNECTION_STRING") or os.environ.get("MMI_QUEUE_CONNECTION")      # Azurite (dev only)
    url = os.environ.get("MMI_QUEUE_URL")
    if not conn and not url:
        raise RuntimeError("configure MMI_QUEUE_CONNECTION_STRING or MMI_QUEUE_CONNECTION (dev) or MMI_QUEUE_URL (Azure)")
    from azure.storage.queue import QueueServiceClient  # type: ignore[import-not-found]

    if conn:
        return StorageQueueBus(QueueServiceClient.from_connection_string(conn))
    from azure.identity import DefaultAzureCredential  # type: ignore[import-not-found]

    return StorageQueueBus(QueueServiceClient(url, credential=DefaultAzureCredential()))
