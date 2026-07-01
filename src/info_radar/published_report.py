import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class CoreItem:
    id: str
    number: int
    title: str
    abstract: str
    recommendation_reason: str
    deep_ids: list[str]


@dataclass(frozen=True)
class DeepItem:
    id: str
    title: str
    body: str
    recommendation_reason: str
    evidence_strength: str
    risk: str
    evidence_id: str


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    title: str
    url: str
    source_type: str
    published_at: str
    ad_risk: str
    usage: str


@dataclass(frozen=True)
class PublishedReport:
    date: str
    title: str
    source_markdown_path: str
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
) -> PublishedReport:
    title = _first_heading(markdown) or f"{report_date} 信息雷达晨报"
    core_section = _section(markdown, "## 核心阅读区", "## 深度阅读区")
    deep_section = _section(markdown, "## 深度阅读区", "## 证据区")
    evidence_section = _section(markdown, "## 证据区", "")
    return PublishedReport(
        date=report_date,
        title=title,
        source_markdown_path=source_markdown_path,
        core_items=_parse_core_items(core_section),
        deep_items=_parse_deep_items(deep_section),
        evidence_items=_parse_evidence_items(evidence_section),
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
        items.append(
            EvidenceItem(
                id=item_id,
                title=title,
                url=url,
                source_type=bullets.get("来源类型", ""),
                published_at=bullets.get("发布时间", ""),
                ad_risk=bullets.get("软文风险", ""),
                usage=bullets.get("用途", ""),
            )
        )
    return items


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


def _clean_body(text: str) -> str:
    return "\n\n".join(part.strip() for part in text.strip().split("\n\n") if part.strip())
