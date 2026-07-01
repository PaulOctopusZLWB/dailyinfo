from pathlib import Path

from info_radar.models import DirectionSummary, RadarItem
from info_radar.render import render_markdown, write_markdown
from info_radar.scoring import score_item


def test_render_markdown_has_required_sections_and_chinese_fields() -> None:
    item = RadarItem(
        source_id="arxiv-ai",
        source_name="arXiv AI",
        source_type="arxiv",
        title="Time-series foundation model",
        url="https://arxiv.org/abs/1234.5678",
        published_at="2026-06-30T08:00:00+08:00",
        content_or_excerpt="A paper about temporal reasoning and forecasting.",
        direction_hints=("temporal",),
    )
    scored = score_item(item, source_priority=90)
    grouped = {"temporal": [scored]}
    summaries = {
        "temporal": DirectionSummary(direction_id="temporal", target=10, actual=1, shortage_reason="候选不足 9 条")
    }

    markdown = render_markdown(
        report_date="2026-07-01",
        grouped_items=grouped,
        summaries=summaries,
        failures=[],
        run_metadata={"fetched": 1, "deduped": 1, "rendered": 1},
    )

    assert "# 2026-07-01 信息雷达" in markdown
    assert "## 今日概览" in markdown
    assert "## 方向二：时序模型、时序算法、时序认知、时序应用前沿" in markdown
    assert "核心观点/论述" in markdown
    assert "推荐理由" in markdown
    assert "摘要/摘录" not in markdown
    assert "软文/广告风险" in markdown
    assert "## 低置信/候选不足说明" in markdown
    assert "## 本次运行元数据" in markdown


def test_write_markdown_creates_obsidian_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "Obsidian" / "Supcon" / "信息雷达"
    path = write_markdown(output_dir, "2026-07-01", "# report")

    assert path == output_dir / "2026-07-01 信息雷达.md"
    assert path.read_text(encoding="utf-8") == "# report"
