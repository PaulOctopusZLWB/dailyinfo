from pathlib import Path

import pytest

from info_radar.config import RegistryError, load_registry


def test_registry_loads_enabled_sources_and_validates_required_fields(tmp_path: Path) -> None:
    registry_file = tmp_path / "source_registry.yml"
    registry_file.write_text(
        """
sources:
  - id: arxiv-ai
    name: arXiv AI
    type: arxiv
    url: https://export.arxiv.org/api/query?search_query=cat:cs.AI
    directions: [macro_ai, temporal]
    language_hint: en
    priority: 90
    enabled: true
    notes: AI research feed.
  - id: disabled-source
    name: Disabled
    type: rss
    url: https://example.com/feed.xml
    directions: [macro_ai]
    language_hint: en
    priority: 10
    enabled: false
    notes: Not active yet.
""",
        encoding="utf-8",
    )

    registry = load_registry(registry_file)

    assert [source.id for source in registry.enabled_sources()] == ["arxiv-ai"]
    assert registry.get("arxiv-ai").priority == 90
    assert registry.get("arxiv-ai").directions == ("macro_ai", "temporal")


def test_registry_rejects_unknown_direction(tmp_path: Path) -> None:
    registry_file = tmp_path / "source_registry.yml"
    registry_file.write_text(
        """
sources:
  - id: bad
    name: Bad
    type: rss
    url: https://example.com/feed.xml
    directions: [not_a_direction]
    language_hint: en
    priority: 10
    enabled: true
    notes: Invalid.
""",
        encoding="utf-8",
    )

    with pytest.raises(RegistryError, match="unknown direction"):
        load_registry(registry_file)
