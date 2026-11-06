"""Message catalogue lookup. User-facing text lives in locale/es-ES.json, never in code."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

LOCALE_DIR = Path(__file__).parent / "locale"


@lru_cache(maxsize=4)
def catalogue(locale: str = "es-ES") -> dict[str, str]:
    return json.loads((LOCALE_DIR / f"{locale}.json").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def t(key: str, locale: str = "es-ES") -> str:
    try:
        return catalogue(locale)[key]
    except KeyError:
        raise KeyError(f"missing translation: {key}") from None
