from pathlib import Path

from info_radar.config import load_registry


def test_default_registry_loads_large_candidate_pool() -> None:
    registry = load_registry(Path("config/source_registry.yml"))

    assert len(registry.sources) >= 240
    assert registry.get("manual-bilibili").type == "bilibili"
    assert registry.get("manual-x").type == "x"
    assert registry.get("manual-zsxq").type == "zsxq"
    assert registry.get("manual-youtube-transcripts").type == "manual"
    assert registry.get("tnd-youtube-karpathy").type == "youtube"
    assert registry.get("tnd-reddit-machinelearning").type == "reddit"
    assert registry.get("tnd-sama-twitter").type == "x"
    assert registry.get("tnd-solidity-github").type == "github"
    assert registry.get("tnd-solidity-github").priority < 45
    assert "低可信" in registry.get("tnd-reddit-machinelearning").notes
    assert "Crypto/市场源低可信" in registry.get("tnd-solidity-github").notes
    assert "ai_philosophy" in registry.get("manual-restricted-cn").directions
    assert registry.get("cisa-ics-advisories").type == "rss"
    assert registry.get("seeq-blog").type == "rss"
    assert "industrial_ai" in registry.get("manual-industrial-cn").directions
    assert registry.get("openalex-time-series").type == "openalex"
    assert registry.get("arxiv-dynamical-systems-reconstruction").directions == ("dynamical_systems",)
    assert registry.get("openalex-dynamical-systems-reconstruction").include_title_any
    assert registry.get("github-timesfm").github_include_issues is False
    assert registry.get("atom-jmir-human-factors").include_any
    assert registry.get("noema-magazine").enabled is True
    assert "human_digital_twin" in registry.get("tnd-mem0-github").directions
    assert registry.get("tnd-hn-rss").enabled is False
    assert registry.enabled_sources()
