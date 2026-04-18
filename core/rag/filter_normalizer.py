from __future__ import annotations

from typing import Any, Dict, Mapping


def normalize_where_filter(where: Mapping[str, Any] | None) -> Dict[str, Any] | None:
    """
    Normalize metadata filters into Chroma operator DSL.

    Rules:
    - No filter -> None
    - Single field -> unchanged
    - Multiple plain fields -> {"$and": [{...}, {...}]}
    - Operator-based payloads are preserved; mixed payloads are wrapped safely.
    """
    if where is None:
        return None
    if not isinstance(where, Mapping):
        return None

    cleaned: Dict[str, Any] = {}
    for key, value in where.items():
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        cleaned[str(key)] = value

    if not cleaned:
        return None

    if len(cleaned) == 1:
        return dict(cleaned)

    clauses: list[Dict[str, Any]] = []
    for key, value in cleaned.items():
        clauses.append({key: value})
    return {"$and": clauses}

