"""T094 (FR-038, R17): locally loaded data and the real ERP are never mixed.

The local sync trigger leaves a marker row in ``external_mappings`` (entity ``local_data``). Loader-made movement ids are far above
anything the ERP serves (minutes since 2020 x 1000), so a checkpoint at or above the floor is evidence too. Before any request to a host
that is not the mock, the job calls ``assert_no_local_data``; the owner must wipe the local data first.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from db.tables import external_mappings, sync_checkpoints
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

LOCAL_HOSTS = {"siweb-mock", "localhost", "127.0.0.1", "::1"}
LOCAL_MOVEMENT_ID_FLOOR = 1_000_000_000
ENTITY = "local_data"


class LocalDataPresentError(Exception):
    code = "local_data_present"

    def __init__(self) -> None:
        super().__init__("Hay datos cargados localmente: bórrelos antes de sincronizar con el ERP real")


def mark_local_data(engine: Engine) -> None:
    with engine.begin() as c:
        if c.execute(select(external_mappings.c.entity).where(external_mappings.c.entity == ENTITY)).first() is None:
            c.execute(insert(external_mappings).values(entity=ENTITY, external_id="loaded", internal_id="1"))


def local_data_present(engine: Engine) -> bool:
    with engine.connect() as c:
        if c.execute(select(external_mappings.c.entity).where(external_mappings.c.entity == ENTITY)).first() is not None:
            return True
        high = c.execute(select(sync_checkpoints.c.last_movement_id).where(sync_checkpoints.c.last_movement_id >= LOCAL_MOVEMENT_ID_FLOOR)).first()
        return high is not None


def assert_no_local_data(engine: Engine, base_url: str) -> None:
    host = (urlsplit(base_url).hostname or "").lower()
    if host not in LOCAL_HOSTS and local_data_present(engine):
        raise LocalDataPresentError
