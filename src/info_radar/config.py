from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

import yaml

from info_radar.directions import DIRECTIONS


class RegistryError(ValueError):
    pass


ALLOWED_SOURCE_TYPES = {
    "rss",
    "atom",
    "arxiv",
    "github",
    "reddit",
    "youtube",
    "web_list",
    "manual",
    "bilibili",
    "x",
    "zsxq",
}


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    type: str
    url: str
    directions: Tuple[str, ...]
    language_hint: str
    priority: int
    enabled: bool
    notes: str


@dataclass(frozen=True)
class Registry:
    sources: Tuple[Source, ...]

    def enabled_sources(self) -> List[Source]:
        return [source for source in self.sources if source.enabled]

    def get(self, source_id: str) -> Source:
        for source in self.sources:
            if source.id == source_id:
                return source
        raise RegistryError(f"unknown source id: {source_id}")


def load_registry(path: Path) -> Registry:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_sources = data.get("sources")
    if not isinstance(raw_sources, list):
        raise RegistryError("registry must contain a sources list")

    sources = [_parse_source(index, raw) for index, raw in enumerate(raw_sources, start=1)]
    ids = [source.id for source in sources]
    duplicates = sorted({source_id for source_id in ids if ids.count(source_id) > 1})
    if duplicates:
        raise RegistryError(f"duplicate source id: {', '.join(duplicates)}")
    return Registry(tuple(sources))


def _parse_source(index: int, raw: object) -> Source:
    if not isinstance(raw, dict):
        raise RegistryError(f"source #{index} must be an object")

    required = ["id", "name", "type", "url", "directions", "language_hint", "priority", "enabled", "notes"]
    missing = [field for field in required if field not in raw]
    if missing:
        raise RegistryError(f"source #{index} missing required fields: {', '.join(missing)}")

    source_type = str(raw["type"])
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise RegistryError(f"source {raw['id']} has unsupported type: {source_type}")

    directions = _parse_directions(raw["directions"], source_id=str(raw["id"]))
    priority = int(raw["priority"])
    if priority < 0 or priority > 100:
        raise RegistryError(f"source {raw['id']} priority must be between 0 and 100")

    return Source(
        id=str(raw["id"]),
        name=str(raw["name"]),
        type=source_type,
        url=str(raw["url"]),
        directions=directions,
        language_hint=str(raw["language_hint"]),
        priority=priority,
        enabled=bool(raw["enabled"]),
        notes=str(raw["notes"]),
    )


def _parse_directions(value: object, source_id: str) -> Tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise RegistryError(f"source {source_id} directions must be a non-empty list")
    directions = tuple(str(item) for item in value)
    unknown = [direction for direction in directions if direction not in DIRECTIONS]
    if unknown:
        raise RegistryError(f"source {source_id} has unknown direction: {', '.join(unknown)}")
    return directions
