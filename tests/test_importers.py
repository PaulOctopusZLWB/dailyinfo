from pathlib import Path

from info_radar.importers import import_items


def test_import_jsonl_items(tmp_path: Path) -> None:
    import_file = tmp_path / "items.jsonl"
    import_file.write_text(
        '{"title":"Agent repo","url":"https://github.com/example/agent","source_name":"X 手工导入","published_at":"2026-06-30T08:00:00+08:00","content_or_excerpt":"一个关于 agent workflow 的重要讨论。","direction_hint":"ai_agents"}\n',
        encoding="utf-8",
    )

    items = import_items(import_file, source_id="x-manual")

    assert len(items) == 1
    assert items[0].title == "Agent repo"
    assert items[0].source_id == "x-manual"
    assert items[0].direction_hints == ("ai_agents",)
    assert items[0].content_or_excerpt == "一个关于 agent workflow 的重要讨论。"


def test_import_markdown_sections(tmp_path: Path) -> None:
    import_file = tmp_path / "items.md"
    import_file.write_text(
        """
## B 站时序模型分享
url: https://www.bilibili.com/video/BV1xx
source_name: Bilibili 手工导入
published_at: 2026-06-30T09:00:00+08:00
direction_hint: temporal

这个视频讨论 time-series foundation model 在工业预测中的应用。

## 知识星球讨论
url: zsxq://group/topic/123
source_name: 知识星球手工导入
published_at: 2026-06-30T10:00:00+08:00
direction_hint: human_digital_twin

只保留摘要，不输出付费全文。
""".strip(),
        encoding="utf-8",
    )

    items = import_items(import_file, source_id="manual-cn")

    assert [item.title for item in items] == ["B 站时序模型分享", "知识星球讨论"]
    assert items[0].direction_hints == ("temporal",)
    assert items[1].url == "zsxq://group/topic/123"
