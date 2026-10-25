"""Pure helpers for sz_incremental_withinfo (no Senzing SDK dependency)."""

from collections.abc import Iterable

import orjson


def missing_entity_line(entity_id: int) -> str:
    """Return the JSON line written for an entity that no longer exists.

    Same shape as get_entity_by_entity_id output, with no records, so consumers
    of the delta file can treat it as a deleted entity.
    """
    return orjson.dumps(
        {"RESOLVED_ENTITY": {"ENTITY_ID": entity_id, "RECORDS": []}}
    ).decode()


def extract_unique_entities(withinfo_lines: Iterable[str]) -> set[int]:
    """Collect the distinct AFFECTED_ENTITIES ENTITY_IDs from WithInfo JSON lines."""
    unique_entities: set[int] = set()
    for line in withinfo_lines:
        if not line.strip():
            continue
        record = orjson.loads(line)
        for entity in record.get("AFFECTED_ENTITIES", []):
            unique_entities.add(entity["ENTITY_ID"])
    return unique_entities
