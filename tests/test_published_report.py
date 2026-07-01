from pathlib import Path

from info_radar.published_report import parse_published_report, write_published_report_json


SAMPLE = """# 2026-07-01 信息雷达晨报

## 核心阅读区

### 1. LLM 风险正在转向应用栈 [[#D1. LLM 应用栈漏洞综述|「link」]]
核心判断正文。

推荐理由：这会影响 agent 权限和工具调用边界。

## 深度阅读区

### D1. LLM 应用栈漏洞综述 [[#E1. LLM 应用栈漏洞综述|「证据」]]
单源深度提炼正文。

- 推荐理由：它把风险从模型层抬升到应用栈层。
- 证据强度：high，系统性综述。
- 风险提示：未见明显推广。

## 证据区

### E1. LLM 应用栈漏洞综述
- 原文：[A Lifecycle Survey](http://arxiv.org/abs/2606.31639v1)
- 来源类型：arXiv 论文
- 发布时间：2026-06-30T13:21:43Z
- 软文风险：未见明显推广
- 用途：支持应用栈风险判断。
"""


def test_parse_published_report_extracts_three_layers(tmp_path: Path) -> None:
    report = parse_published_report(SAMPLE, report_date="2026-07-01", source_markdown_path="/tmp/report.md")

    assert report.date == "2026-07-01"
    assert report.title == "2026-07-01 信息雷达晨报"
    assert report.source_markdown_path == "/tmp/report.md"
    assert report.core_items[0].id == "C1"
    assert report.core_items[0].number == 1
    assert report.core_items[0].title == "LLM 风险正在转向应用栈"
    assert report.core_items[0].deep_ids == ["D1"]
    assert report.core_items[0].recommendation_reason == "这会影响 agent 权限和工具调用边界。"
    assert report.deep_items[0].id == "D1"
    assert report.deep_items[0].evidence_id == "E1"
    assert report.deep_items[0].evidence_strength == "high"
    assert report.deep_items[0].recommendation_reason == "它把风险从模型层抬升到应用栈层。"
    assert report.deep_items[0].risk == "未见明显推广。"
    assert report.evidence_items[0].id == "E1"
    assert report.evidence_items[0].url == "http://arxiv.org/abs/2606.31639v1"
    assert report.evidence_items[0].source_type == "arXiv 论文"
    assert report.evidence_items[0].published_at == "2026-06-30T13:21:43Z"
    assert report.evidence_items[0].ad_risk == "未见明显推广"
    assert report.evidence_items[0].usage == "支持应用栈风险判断。"


def test_write_published_report_json_writes_date_file(tmp_path: Path) -> None:
    report = parse_published_report(SAMPLE, report_date="2026-07-01")
    path = write_published_report_json(tmp_path, report)

    assert path == tmp_path / "2026-07-01.json"
    text = path.read_text(encoding="utf-8")
    assert '"core_items"' in text
    assert '"deep_items"' in text
    assert '"evidence_items"' in text
