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
- 方向标签：宏观 AI 前沿论点
- 软文风险：未见明显推广
- 用途：支持应用栈风险判断。
"""


def test_parse_published_report_extracts_three_layers(tmp_path: Path) -> None:
    report = parse_published_report(
        SAMPLE,
        report_date="2026-07-01",
        source_markdown_path="/tmp/report.md",
        run_stats={"enabled_sources": 10, "failed_sources": 2},
    )

    assert report.date == "2026-07-01"
    assert report.title == "2026-07-01 信息雷达晨报"
    assert report.source_markdown_path == "/tmp/report.md"
    assert report.run_stats["enabled_sources"] == 10
    assert report.run_stats["failed_sources"] == 2
    assert report.run_stats["final_core_items"] == 1
    assert report.run_stats["final_deep_items"] == 1
    assert report.run_stats["final_evidence_items"] == 1
    assert report.core_items[0].id == "C1"
    assert report.core_items[0].number == 1
    assert report.core_items[0].title == "LLM 风险正在转向应用栈"
    assert report.core_items[0].deep_ids == ["D1"]
    assert report.core_items[0].direction_id == "macro"
    assert report.core_items[0].recommendation_reason == "这会影响 agent 权限和工具调用边界。"
    assert report.deep_items[0].id == "D1"
    assert report.deep_items[0].evidence_id == "E1"
    assert report.deep_items[0].direction_id == "macro"
    assert report.deep_items[0].core_argument == "单源深度提炼正文。"
    assert report.deep_items[0].impact == "它把风险从模型层抬升到应用栈层。"
    assert report.deep_items[0].source_category == "学术论文"
    assert report.deep_items[0].evidence_strength == "high"
    assert report.deep_items[0].recommendation_reason == "它把风险从模型层抬升到应用栈层。"
    assert report.deep_items[0].risk == "未见明显推广。"
    assert report.evidence_items[0].id == "E1"
    assert report.evidence_items[0].url == "http://arxiv.org/abs/2606.31639v1"
    assert report.evidence_items[0].source_label == "arXiv"
    assert report.evidence_items[0].source_type == "arXiv 论文"
    assert report.evidence_items[0].source_category == "学术论文"
    assert report.evidence_items[0].published_at == "2026-06-30T13:21:43Z"
    assert report.evidence_items[0].direction_label == "宏观 AI 前沿论点"
    assert report.evidence_items[0].direction_id == "macro"
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
    assert '"run_stats"' in text
    assert '"source_label": "arXiv"' in text
    assert '"source_category": "学术论文"' in text
    assert '"direction_id": "macro"' in text


def test_parse_published_report_splits_deep_body_into_argument_and_impact() -> None:
    markdown = """# 2026-07-01 信息雷达晨报

## 核心阅读区

### 1. 能源时序需要表达关系和不确定性 [[#D11. Relational and Sequential Conformal Inference for Energy Time Series over Graphs via Foundation Models|「link」]]
核心判断正文。

推荐理由：这会影响工业预测边界。

## 深度阅读区

### D11. Relational and Sequential Conformal Inference for Energy Time Series over Graphs via Foundation Models [[#E11. Relational and Sequential Conformal Inference for Energy Time Series over Graphs via Foundation Models|「证据」]]
STOIC 把 foundation model、图结构和 conformal prediction 结合，试图让能源时序预测同时表达空间关系和不确定性。 这条来源的主要价值不是让我们立即接受它的结论，而是把一个可追踪的判断点放进源池：它能反推我们在 FDE/工业预测中应如何处理非平稳、干预、不确定性和评价口径。 后续需要继续打开原文、追踪引用或版本反馈，把它从候选信号升级为稳定认知。

- 推荐理由：推荐把它作为高优先级证据卡保留。
- 证据强度：high，来源可追溯。
- 风险提示：未见明显推广。

## 证据区

### E11. Relational and Sequential Conformal Inference for Energy Time Series over Graphs via Foundation Models
- 原文：[source](http://arxiv.org/abs/2606.12345v1)
- 来源类型：arxiv
- 发布时间：2026-06-30T13:21:43Z
- 方向标签：时序智能
- 软文风险：未见明显推广
- 用途：支持能源时序判断。
"""

    report = parse_published_report(markdown, report_date="2026-07-01")

    deep = report.deep_items[0]
    assert deep.core_argument == "STOIC 把 foundation model、图结构和 conformal prediction 结合，试图让能源时序预测同时表达空间关系和不确定性。"
    assert deep.impact.startswith("这条来源的主要价值不是让我们立即接受它的结论")
    assert "非平稳、干预、不确定性和评价口径" in deep.impact
    assert deep.source_category == "学术论文"
