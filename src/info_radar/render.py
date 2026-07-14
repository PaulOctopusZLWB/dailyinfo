import json
import re
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo

from info_radar.directions import DIRECTION_PREFIX, DIRECTIONS


PROCESSING_PROTOCOL = {
    "version": "deep_reading_v1",
    "required_sections": ["核心阅读区", "深度阅读区", "证据区"],
    "link_contract": {
        "core_to_deep": "C -> D",
        "deep_to_evidence": "D -> E",
        "evidence_to_original": "E -> URL",
        "max_explicit_deep_links_per_core": 3,
    },
    "core_strategy": "within each direction, discretize distinct viewpoints before synthesis; do not force 8-10 sources into one core judgment",
    "stages": [
        "Evidence Extractor",
        "Single Source Distiller",
        "Ad / Bias Auditor",
        "Morning Brief Renderer",
    ],
}


def render_markdown(report_date, grouped_items, summaries, failures, run_metadata):
    lines = [
        f"# {report_date} 信息雷达",
        "",
        "## 今日概览",
        "",
        f"- {_target_line(summaries)}",
        f"- 实际输出：{sum(len(items) for items in grouped_items.values())} 条",
        f"- 抓取/导入材料：{run_metadata.get('fetched', 0)} 条",
        f"- 去重后材料：{run_metadata.get('deduped', 0)} 条",
        *_freshness_lines(run_metadata),
        f"- 失败源：{run_metadata.get('failures', 0)} 个",
        "",
    ]

    for direction_id, label in DIRECTIONS.items():
        prefix = DIRECTION_PREFIX[direction_id]
        items = grouped_items.get(direction_id, [])
        lines.extend([f"## {prefix}：{label}", ""])
        if not items:
            lines.extend(["_今日没有达到阈值的候选。_", ""])
            continue
        for index, item in enumerate(items, start=1):
            lines.extend(
                [
                    f"### {index}. [{item.title}]({item.url})",
                    f"- 核心观点/论述：{item.core_argument.removeprefix('核心论述：')}",
                    f"- 推荐理由：{item.recommendation_reason}",
                    f"- 软文/广告风险：{item.ad_risk}",
                    f"- 证据来源：{item.source_name}（{item.source_type}，{item.evidence_type}，发布时间：{item.published_at or '未知'}，重复 {item.duplicate_count} 条）",
                    "",
                ]
            )

    lines.extend(["## 低置信/候选不足说明", ""])
    shortage_lines = [
        f"- {DIRECTIONS[direction_id]}：{summary.shortage_reason}"
        for direction_id, summary in summaries.items()
        if summary.shortage_reason
    ]
    if shortage_lines:
        lines.extend(shortage_lines)
    else:
        lines.append("- 所有方向均达到目标候选数量。")
    for failure in failures:
        lines.append(f"- 抓取失败：{failure.source_name}（{failure.source_id}）：{failure.reason}")
    lines.append("")

    lines.extend(["## 本次运行元数据", ""])
    for key, value in run_metadata.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    return "\n".join(lines)


def write_markdown(output_dir, report_date, markdown):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{report_date} 信息雷达.md"
    published_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    path.write_text(_obsidian_report(markdown, report_date, published_at), encoding="utf-8")
    return path


def _obsidian_report(markdown: str, report_date: str, published_at: str) -> str:
    text = markdown.lstrip("\ufeff")
    if text.startswith("---\n"):
        closing = text.find("\n---\n", 4)
        if closing < 0:
            raise ValueError("Processed report has an unterminated YAML frontmatter block.")
        header = text[: closing + 5]
        required = (
            'type: "information-radar"',
            'status: "reference"',
            f'date: "{report_date}"',
            "description:",
            'project: "FDE"',
        )
        missing = [field for field in required if field not in header]
        if missing:
            raise ValueError(f"Processed report frontmatter is not vault-compliant; missing: {', '.join(missing)}")
        return _insert_snapshot_callout(text, published_at)

    description = _radar_description(text, report_date)
    updated = published_at[:10]
    frontmatter = "\n".join(
        [
            "---",
            f'title: "{report_date} 信息雷达"',
            'type: "information-radar"',
            'project: "FDE"',
            'status: "reference"',
            f'date: "{report_date}"',
            f'updated: "{updated}"',
            f"description: {json.dumps(description, ensure_ascii=False)}",
            "tags:",
            '  - "project/fde"',
            '  - "domain/knowledge-management"',
            '  - "artifact/information-radar"',
            f'generated_on: "{published_at}"',
            f'last_verified: "{published_at}"',
            "---",
            "",
        ]
    )
    return frontmatter + _insert_snapshot_callout(text, published_at)


def _radar_description(markdown: str, report_date: str) -> str:
    in_core = False
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line == "## 核心阅读区":
            in_core = True
            continue
        if in_core and line.startswith("## "):
            break
        if in_core and line.startswith("### "):
            title = re.sub(r"^\d+\.\s*", "", line[4:])
            title = title.split("[[#", 1)[0].strip()
            title = re.sub(r"\s+", " ", title)
            if title:
                return f"{report_date} 信息雷达主线：{title}"[:150]
    return f"{report_date} 信息雷达：核心阅读、深度阅读与证据链的每日决策快照。"


def _insert_snapshot_callout(markdown: str, published_at: str) -> str:
    if "> 数据截止与发布校验：" in markdown:
        return markdown
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("# "):
            callout = (
                f"> 数据截止与发布校验：{published_at}（Asia/Shanghai）。"
                "本文为 episodic 快照，后续状态复用前须重新核验。"
            )
            lines[index + 1:index + 1] = ["", callout]
            return "\n".join(lines).rstrip() + "\n"
    return markdown.rstrip() + "\n"


def render_candidate_packet_markdown(report_date, grouped_items, summaries, failures, run_metadata):
    lines = [
        f"# {report_date} 信息雷达候选包",
        "",
        "## Codex 加工任务",
        "",
        "- 这是 staging 候选包，不是最终日报。",
        "- 不要把本候选包原样写入 Obsidian。",
        "- 最终 Obsidian 晨报必须分成「核心阅读区」「深度阅读区」「证据区」。",
        "- 核心阅读区只服务每天早上快速阅读：只放中文、加工提炼后的重点判断，不放原始摘录。",
        "- 核心阅读区不设固定条数上限；在每个方向内优先离散内部不同论点，选择最不同、最有信息增量的判断沉淀下来。",
        "- 不要把 8-10 个来源硬合并成一个大判断；如果同方向有多条不同机制链，应拆成多条核心判断。",
        "- 深度阅读区是一源一卡：只写高价值源自己的核心提炼，不做多源总结，不复述原文。",
        "- 每张深度阅读卡必须分成 `核心论点：...` 和 `对我们的影响：...` 两节；前者只写来源自身主张，后者写对 FDE/工业预测/信息雷达/个人上下文等内部决策的影响。",
        "- 证据区只做回溯：保留 URL、来源类型、发布时间、软文风险、重复/聚类信息和相关候选。",
        "- 证据区必须写读者友好的来源分类，例如 `学术论文`、`播客/访谈`、`个人观点`、`企业发布`、`开源项目`、`安全公告`、`新闻/政策`。",
        "- 链接契约：核心阅读区只能链接到深度阅读区 D 卡；深度阅读区 D 卡必须链接到证据区 E 卡；证据区 E 卡再保留原始 URL。",
        "- 每条核心判断最多显性关联 3 个深度阅读 D 卡；超过 3 个时必须拆成多个核心判断。",
        "- 每条核心观点标题必须带可点击的 `「link」`，格式如 `[[#D1. 高价值源标题|「link」]]`。",
        "- 每条深度阅读标题必须带可点击的 `「证据」`，格式如 `[[#E1. 原始证据标题|「证据」]]`。",
        "- 每条核心观点写成 100-200 字中文 abstract：讲清楚发生了什么、为什么新或重要、对方向/决策意味着什么，逻辑闭合、故事完整。",
        "- 推荐理由必须说明具体信息增量、决策关系和后续动作，不要写“与方向相关、证据类型为论文”这类车轱辘话。",
        "- 请合并重复论述，删除软文/广告/低信息增量内容，把英文材料压缩成中文判断。",
        "",
        "## 深度阅读加工协议",
        "",
        "### Stage 1. Evidence Extractor",
        "- 目标：只从单个来源抽取可验证的信息骨架，不写最终摘要。",
        "- 输出字段：`main_claim`、`mechanism_chain`、`new_information`、`decision_relevance`、`evidence_type`、`ad_or_bias_signals`、`missing_context`、`recommendation_seed`。",
        "- 约束：只基于候选材料和元数据；无法从原文支持的内容写 `not_found`；关键判断必须保留短证据片段；不输出付费全文或长引用。",
        "",
        "### Stage 2. Single Source Distiller",
        "- 目标：把一个高价值来源写成深度阅读区的一源一卡。",
        "- 写法：150-280 字中文，闭合回答“它说了什么 -> 为什么成立 -> 新意在哪里 -> 对决策有什么用”。",
        "- 禁止：不要做多源综合，不要复述标题，不要堆名词，不要写“值得关注”“有启发”等空话。",
        "",
        "### Stage 3. Ad / Bias Auditor",
        "- 目标：检查深读卡是否把厂商宣传当事实、把发布当验证、缺少第三方证据、过度推断或推荐理由空泛。",
        "- 输出：`pass`、`risk_level`、`problems`、`rewrite_instructions`、`final_ad_risk_label`。",
        "- 处理：风险中高的内容必须降权、收敛措辞，或只保留在证据区。",
        "",
        "### Stage 4. Morning Brief Renderer",
        "- 目标：把通过审计的深读卡提炼成离散核心判断，同时保留深度阅读区和证据区。",
        "- 核心阅读区是观点沉淀层：同方向内优先拆出不同机制链、不同证据类型和不同决策含义；深度阅读区是一源一卡；证据区是可追溯底座。",
        "- 一个核心判断如依赖多个深读卡，在正文末尾追加 `深读入口：[[#D1. ...|D1]] · [[#D2. ...|D2]]`，但同一核心判断最多 3 个 D 卡。",
        "",
        "### 推荐输出骨架",
        "",
        "```md",
        "## 核心阅读区",
        "",
        "### 1. 核心判断标题 [[#D1. 高价值源标题|「link」]]",
        "100-200 字中文 abstract。",
        "",
        "## 深度阅读区",
        "",
        "### D1. 高价值源标题 [[#E1. 原始证据标题|「证据」]]",
        "核心论点：150 字以内，只写这个来源自己的主张、机制或发现。",
        "",
        "对我们的影响：150 字以内，写它会如何影响内部判断、源权重、产品设计或后续验证动作。",
        "",
        "- 推荐理由：具体信息增量、决策关系和后续动作。",
        "- 证据强度：high|medium|low，一句解释。",
        "- 风险提示：广告/立场/证据缺口；没有则写未见明显风险。",
        "",
        "## 证据区",
        "",
        "### E1. 原始证据标题",
        "- 原文：[source](https://example.com)",
        "- 来源分类：学术论文|播客/访谈|个人观点|企业发布|开源项目|安全公告|新闻/政策|其他",
        "- 来源类型：...",
        "- 发布时间：...",
        "- 软文风险：...",
        "```",
        "",
        "## 候选包概览",
        "",
        f"- {_target_line(summaries)}",
        f"- 实际候选：{sum(len(items) for items in grouped_items.values())} 条",
        f"- 抓取/导入材料：{run_metadata.get('fetched', 0)} 条",
        f"- 去重后材料：{run_metadata.get('deduped', 0)} 条",
        *_freshness_lines(run_metadata),
        f"- 失败源：{run_metadata.get('failures', 0)} 个",
        "",
    ]
    for direction_id, label in DIRECTIONS.items():
        items = grouped_items.get(direction_id, [])
        lines.extend([f"## {DIRECTION_PREFIX[direction_id]}：{label}", ""])
        if not items:
            lines.extend(["_无候选。_", ""])
            continue
        for index, item in enumerate(items, start=1):
            lines.extend(
                [
                    f"### {index}. {item.title}",
                    f"- URL：{item.url}",
                    f"- 初步核心论述：{item.core_argument}",
                    f"- 初步推荐理由：{item.recommendation_reason}",
                    f"- 软文/广告风险：{item.ad_risk}",
                    f"- 证据来源：{item.source_name}（{item.source_type}，{item.evidence_type}，发布时间：{item.published_at or '未知'}，重复 {item.duplicate_count} 条）",
                    f"- 原始摘录：{_compact_excerpt(item.content_or_excerpt)}",
                    "",
                ]
            )
    lines.extend(["## 缺口与失败", ""])
    for direction_id, summary in summaries.items():
        if summary.shortage_reason:
            lines.append(f"- {DIRECTIONS[direction_id]}：{summary.shortage_reason}")
    for failure in failures:
        lines.append(f"- 抓取失败：{failure.source_name}（{failure.source_id}）：{failure.reason}")
    if lines[-1] == "## 缺口与失败":
        lines.append("- 无。")
    lines.append("")
    return "\n".join(lines)


def render_candidate_packet_payload(report_date, grouped_items, summaries, failures, run_metadata):
    return {
        "status": "staging_requires_codex_processing",
        "report_date": report_date,
        "metadata": run_metadata,
        "processing_protocol": PROCESSING_PROTOCOL,
        "directions": {
            direction_id: [_item_payload(item) for item in grouped_items.get(direction_id, [])]
            for direction_id in DIRECTIONS
        },
        "summaries": {
            direction_id: {
                "target": summary.target,
                "actual": summary.actual,
                "shortage_reason": summary.shortage_reason,
            }
            for direction_id, summary in summaries.items()
        },
        "failures": [
            {"source_id": failure.source_id, "source_name": failure.source_name, "reason": failure.reason}
            for failure in failures
        ],
    }


def write_candidate_packet(staging_dir, report_date, markdown, payload):
    staging_dir = Path(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = staging_dir / f"{report_date}-candidates.md"
    json_path = staging_dir / f"{report_date}-candidates.json"
    markdown_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return markdown_path, json_path


def _target_line(summaries) -> str:
    per_direction_target = 10
    if summaries:
        per_direction_target = max(summary.target for summary in summaries.values())
    direction_count = len(DIRECTIONS)
    total_target = direction_count * per_direction_target
    return f"候选目标：{total_target} 条（{direction_count} 个方向，每组目标 {per_direction_target} 条）"


def _freshness_lines(run_metadata: Mapping) -> list[str]:
    if "cross_day_excluded" not in run_metadata:
        return []
    return [
        f"- 跨日排重剔除：{run_metadata.get('cross_day_excluded', 0)} 条",
        f"- 当日新增候选池：{run_metadata.get('fresh', 0)} 条",
    ]


def _item_payload(item):
    return {
        "title": item.title,
        "url": item.url,
        "source_name": item.source_name,
        "source_type": item.source_type,
        "published_at": item.published_at,
        "primary_direction": item.primary_direction,
        "score": item.score,
        "evidence_type": item.evidence_type,
        "ad_risk": item.ad_risk,
        "core_argument": item.core_argument,
        "recommendation_reason": item.recommendation_reason,
        "duplicate_count": item.duplicate_count,
        "excerpt": item.content_or_excerpt,
    }


def _direction_labels(item) -> str:
    labels = []
    if item.primary_direction in DIRECTIONS:
        labels.append(DIRECTIONS[item.primary_direction])
    for direction_id in item.direction_hints:
        if direction_id in DIRECTIONS and DIRECTIONS[direction_id] not in labels:
            labels.append(DIRECTIONS[direction_id])
    return "；".join(labels) if labels else "未分类"


def _compact_excerpt(excerpt: str) -> str:
    normalized = " ".join((excerpt or "").split())
    if len(normalized) > 180:
        return normalized[:177] + "..."
    return normalized or "无摘录"
