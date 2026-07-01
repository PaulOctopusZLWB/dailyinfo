import json
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class CoreItem:
    id: str
    number: int
    title: str
    abstract: str
    recommendation_reason: str
    deep_ids: list[str]
    direction_id: str = ""


@dataclass(frozen=True)
class DeepItem:
    id: str
    title: str
    body: str
    recommendation_reason: str
    evidence_strength: str
    risk: str
    evidence_id: str
    direction_id: str = ""


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    title: str
    url: str
    source_label: str
    source_type: str
    published_at: str
    ad_risk: str
    usage: str
    direction_label: str = ""
    direction_id: str = ""


@dataclass(frozen=True)
class PublishedReport:
    date: str
    title: str
    source_markdown_path: str
    run_stats: dict[str, Any]
    core_items: list[CoreItem]
    deep_items: list[DeepItem]
    evidence_items: list[EvidenceItem]

    def to_dict(self) -> dict:
        return asdict(self)


CORE_HEADING_RE = re.compile(r"^###\s+(\d+)\.\s+(.+)$", re.MULTILINE)
DEEP_HEADING_RE = re.compile(r"^###\s+(D\d+)\.\s+(.+)$", re.MULTILINE)
EVIDENCE_HEADING_RE = re.compile(r"^###\s+(E\d+)\.\s+(.+)$", re.MULTILINE)
WIKI_LINK_RE = re.compile(r"\[\[#([^|\]]+)\|[^\]]+\]\]")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def parse_published_report(
    markdown: str,
    report_date: str,
    source_markdown_path: str = "",
    run_stats: dict[str, Any] | None = None,
) -> PublishedReport:
    title = _first_heading(markdown) or f"{report_date} 信息雷达晨报"
    core_section = _section(markdown, "## 核心阅读区", "## 深度阅读区")
    deep_section = _section(markdown, "## 深度阅读区", "## 证据区")
    evidence_section = _section(markdown, "## 证据区", "")
    evidence_items = _parse_evidence_items(evidence_section)
    deep_items = _attach_deep_directions(_parse_deep_items(deep_section), evidence_items)
    core_items = _attach_core_directions(_parse_core_items(core_section), deep_items)
    stats = dict(run_stats or {})
    stats.update(
        {
            "final_core_items": len(core_items),
            "final_deep_items": len(deep_items),
            "final_evidence_items": len(evidence_items),
        }
    )
    return PublishedReport(
        date=report_date,
        title=title,
        source_markdown_path=source_markdown_path,
        run_stats=stats,
        core_items=core_items,
        deep_items=deep_items,
        evidence_items=evidence_items,
    )


def write_published_report_json(output_dir: Path | str, report: PublishedReport) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    path = output_path / f"{report.date}.json"
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _parse_core_items(section: str) -> list[CoreItem]:
    items = []
    for number_text, raw_title, body in _iter_heading_blocks(section, CORE_HEADING_RE):
        number = int(number_text)
        title = _strip_inline_links(raw_title)
        deep_ids = _extract_ids(raw_title + "\n" + body, "D")
        body_without_links = _strip_deep_entry_line(body)
        abstract, recommendation = _split_recommendation(body_without_links)
        items.append(
            CoreItem(
                id=f"C{number}",
                number=number,
                title=title,
                abstract=abstract,
                recommendation_reason=recommendation,
                deep_ids=deep_ids,
            )
        )
    return items


def _parse_deep_items(section: str) -> list[DeepItem]:
    items = []
    for item_id, raw_title, body in _iter_heading_blocks(section, DEEP_HEADING_RE):
        title = _strip_inline_links(raw_title)
        evidence_ids = _extract_ids(raw_title + "\n" + body, "E")
        body_text, bullets = _split_bullets(body)
        evidence_strength = bullets.get("证据强度", "")
        if "，" in evidence_strength:
            evidence_strength = evidence_strength.split("，", 1)[0].strip()
        items.append(
            DeepItem(
                id=item_id,
                title=title,
                body=body_text,
                recommendation_reason=bullets.get("推荐理由", ""),
                evidence_strength=evidence_strength,
                risk=bullets.get("风险提示", ""),
                evidence_id=evidence_ids[0] if evidence_ids else "",
            )
        )
    return items


def _parse_evidence_items(section: str) -> list[EvidenceItem]:
    items = []
    for item_id, raw_title, body in _iter_heading_blocks(section, EVIDENCE_HEADING_RE):
        title = _strip_inline_links(raw_title)
        _, bullets = _split_bullets(body)
        original = bullets.get("原文", "") or bullets.get("来源", "")
        url = _extract_markdown_url(original) or original
        direction_label = bullets.get("方向标签", "")
        items.append(
            EvidenceItem(
                id=item_id,
                title=title,
                url=url,
                source_label=_source_label(url, bullets.get("来源类型", ""), title),
                source_type=bullets.get("来源类型", ""),
                published_at=bullets.get("发布时间", ""),
                ad_risk=bullets.get("软文风险", ""),
                usage=bullets.get("用途", ""),
                direction_label=direction_label,
                direction_id=_direction_id(direction_label),
            )
        )
    return items


def _attach_deep_directions(deep_items: list[DeepItem], evidence_items: list[EvidenceItem]) -> list[DeepItem]:
    evidence_by_id = {item.id: item for item in evidence_items}
    attached = []
    for item in deep_items:
        evidence = evidence_by_id.get(item.evidence_id)
        attached.append(replace(item, direction_id=evidence.direction_id if evidence else ""))
    return attached


def _attach_core_directions(core_items: list[CoreItem], deep_items: list[DeepItem]) -> list[CoreItem]:
    deep_by_id = {item.id: item for item in deep_items}
    attached = []
    for item in core_items:
        direction_id = ""
        for deep_id in item.deep_ids:
            direction_id = deep_by_id.get(deep_id, DeepItem("", "", "", "", "", "", "")).direction_id
            if direction_id:
                break
        attached.append(replace(item, direction_id=direction_id))
    return attached


def _iter_heading_blocks(section: str, heading_re: re.Pattern) -> list[tuple[str, str, str]]:
    matches = list(heading_re.finditer(section))
    blocks = []
    for index, match in enumerate(matches):
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        blocks.append((match.group(1), match.group(2).strip(), section[body_start:body_end].strip()))
    return blocks


def _first_heading(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
    return ""


def _section(markdown: str, start_marker: str, end_marker: str) -> str:
    start = markdown.find(start_marker)
    if start == -1:
        return ""
    start += len(start_marker)
    if not end_marker:
        return markdown[start:]
    end = markdown.find(end_marker, start)
    if end == -1:
        return markdown[start:]
    return markdown[start:end]


def _strip_inline_links(text: str) -> str:
    stripped = WIKI_LINK_RE.sub("", text)
    stripped = MARKDOWN_LINK_RE.sub(r"\1", stripped)
    return " ".join(stripped.split())


def _extract_ids(text: str, prefix: str) -> list[str]:
    ids = []
    for target in WIKI_LINK_RE.findall(text):
        candidate = target.split(".", 1)[0].strip()
        if candidate.startswith(prefix) and candidate not in ids:
            ids.append(candidate)
    return ids


def _strip_deep_entry_line(text: str) -> str:
    lines = [line for line in text.splitlines() if not line.strip().startswith("深读入口：")]
    return "\n".join(lines).strip()


def _split_recommendation(text: str) -> tuple[str, str]:
    marker = "推荐理由："
    if marker not in text:
        return _clean_body(text), ""
    before, after = text.split(marker, 1)
    return _clean_body(before), _clean_body(after)


def _split_bullets(text: str) -> tuple[str, dict[str, str]]:
    body_lines = []
    bullets = {}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and "：" in stripped:
            key, value = stripped.removeprefix("- ").split("：", 1)
            bullets[key.strip()] = value.strip()
        elif stripped:
            body_lines.append(stripped)
    return _clean_body("\n".join(body_lines)), bullets


def _extract_markdown_url(value: str) -> str:
    match = MARKDOWN_LINK_RE.search(value)
    if match:
        return match.group(2).strip()
    return ""


def _source_label(url: str, source_type: str, title: str) -> str:
    source_text = f"{source_type} {url} {title}".lower()
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    if "arxiv.org" in host or "arxiv" in source_text:
        return "arXiv"
    if "github.com" in host or "github" in source_text:
        return "GitHub"
    if "cisa.gov" in host or "cisa" in source_text:
        return "CISA ICS"
    if "seeq.com" in host or "seeq" in source_text:
        return "Seeq"
    if "openai.com" in host:
        return "OpenAI"
    if "anthropic.com" in host:
        return "Anthropic"
    if host:
        return host
    return source_type or title or "未标注来源"


def _direction_id(label: str) -> str:
    normalized = re.sub(r"[\s+＋、，,·/／\-—_]", "", (label or "").lower())
    if not normalized:
        return ""
    mappings = {
        "宏观ai前沿论点": "macro",
        "宏观a前沿论点": "macro",
        "时序智能": "timeseries",
        "时序模型时序算法时序认知时序应用前沿": "timeseries",
        "工业软件ai": "industrial",
        "工业控制软件ai结合前沿": "industrial",
        "aiagent生态": "agent",
        "最佳使用aiagent的github库方法论认知讨论重要观点": "agent",
        "数字孪生": "twin",
        "面向人类的数字孪生": "twin",
        "ai时代的泛哲学讨论": "philosophy",
        "泛哲学讨论": "philosophy",
    }
    return mappings.get(normalized, "")


def _clean_body(text: str) -> str:
    return "\n\n".join(part.strip() for part in text.strip().split("\n\n") if part.strip())
