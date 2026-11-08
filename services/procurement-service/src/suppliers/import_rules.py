"""T061: rules for the supplier import: a conservative suggestion for obvious expense vendors. The buyer always has the last word."""

from __future__ import annotations

from suppliers.dedupe import name_key

# word starts that mark an expense vendor (energy, insurance, telecoms, software and hosting, security, advisers); "gas" and "luz" must be whole words
STEMS = ("energi", "electric", "seguro", "telecom", "telefon", "hosting", "software", "alarma", "asesor", "gestor", "consultor", "auditor", "informatic", "inmobil", "banc", "publicidad", "marketing")
WHOLE = ("gas", "luz", "internet")


def suggest_classification(name: str) -> str:
    """``non_purchasing`` for names that are clearly not merchandise suppliers, otherwise ``unclassified`` (the buyer decides)."""
    words = name_key(name).replace("-", " ").split()
    if any(w.startswith(STEMS) or w in WHOLE for w in words):
        return "non_purchasing"
    return "unclassified"
