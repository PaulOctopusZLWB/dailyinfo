from info_radar.models import DirectionSummary, RadarItem
from info_radar.render import render_candidate_packet_markdown, render_candidate_packet_payload
from info_radar.scoring import score_item


def test_candidate_packet_is_staging_input_not_final_report() -> None:
    item = RadarItem(
        source_id="manual-cn",
        source_name="X 手工导入",
        source_type="manual",
        title="Agent workflow repo",
        url="https://github.com/example/agent-workflow",
        published_at="2026-06-30T08:00:00+08:00",
        content_or_excerpt="GitHub repo benchmark for best agent workflow.",
        direction_hints=("ai_agents",),
    )
    scored = score_item(item, source_priority=80)
    grouped = {"ai_agents": [scored]}
    summaries = {"ai_agents": DirectionSummary("ai_agents", 10, 1, "候选不足 9 条")}
    metadata = {"fetched": 1, "deduped": 1, "rendered": 1, "failures": 0}

    markdown = render_candidate_packet_markdown("2026-07-01", grouped, summaries, [], metadata)
    payload = render_candidate_packet_payload("2026-07-01", grouped, summaries, [], metadata)

    assert "Codex 加工任务" in markdown
    assert "不要把本候选包原样写入 Obsidian" in markdown
    assert "最终 Obsidian 晨报必须分成「核心阅读区」「深度阅读区」「证据区」" in markdown
    assert "Evidence Extractor" in markdown
    assert "Single Source Distiller" in markdown
    assert "Ad / Bias Auditor" in markdown
    assert "Morning Brief Renderer" in markdown
    assert "优先离散内部不同论点" in markdown
    assert "最多显性关联 3 个深度阅读 D 卡" in markdown
    assert "核心论点" in markdown
    assert "对我们的影响" in markdown
    assert "来源分类" in markdown
    assert "深度阅读区是一源一卡" in markdown
    assert "核心阅读区只能链接到深度阅读区 D 卡" in markdown
    assert "100-200 字中文 abstract" in markdown
    assert "每条核心观点标题必须带可点击的 `「link」`" in markdown
    assert "推荐理由必须说明具体信息增量" in markdown
    assert "候选目标：60 条（6 个方向，每组目标 10 条）" in markdown
    assert payload["status"] == "staging_requires_codex_processing"
    assert payload["processing_protocol"]["version"] == "deep_reading_v1"
    assert payload["processing_protocol"]["required_sections"] == ["核心阅读区", "深度阅读区", "证据区"]
    assert payload["processing_protocol"]["link_contract"]["core_to_deep"] == "C -> D"
    assert payload["processing_protocol"]["link_contract"]["deep_to_evidence"] == "D -> E"
    assert payload["processing_protocol"]["link_contract"]["max_explicit_deep_links_per_core"] == 3
    assert "discretize distinct viewpoints" in payload["processing_protocol"]["core_strategy"]
    assert "ai_philosophy" in payload["directions"]
    assert payload["directions"]["ai_agents"][0]["title"] == "Agent workflow repo"
