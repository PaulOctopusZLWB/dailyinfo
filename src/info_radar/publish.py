import re
from dataclasses import dataclass


REQUIRED_SECTIONS = ("## 核心阅读区", "## 深度阅读区", "## 证据区")
MAX_CORE_DEEP_LINKS = 3
FORBIDDEN_CORE_MARKERS = (
    "初步核心论述",
    "初步推荐理由",
    "原始摘录",
    "材料主张：",
    "核心论述：围绕",
    "值得推荐：它与",
    "证据类型为",
)
CORE_ENTRY_HEADING_RE = re.compile(r"^###\s+\d+\.\s+.+$", re.MULTILINE)
CORE_ENTRY_BLOCK_RE = re.compile(
    r"^(###\s+(\d+)\.\s+[^\n]+)(.*?)(?=^###\s+\d+\.|\Z)",
    re.MULTILINE | re.DOTALL,
)
DEEP_ENTRY_HEADING_RE = re.compile(r"^###\s+D\d+\.\s+.+$", re.MULTILINE)
CLICKABLE_LINK_RE = re.compile(r"(\[「link」\]\([^)]+\)|\[\[[^\]]+\|「link」\]\])")
CORE_TO_DEEP_LINK_RE = re.compile(r"(\[「link」\]\(#D\d+[^)]*\)|\[\[#D\d+[^\]]*\|「link」\]\])")
DEEP_LINK_ID_RE = re.compile(r"(\[\[[^\]]*#(D\d+)[^\]]*\]\]|\[[^\]]+\]\(#(D\d+)[^)]*\))")
DEEP_TO_EVIDENCE_LINK_RE = re.compile(r"(\[「证据」\]\(#E\d+[^)]*\)|\[\[#E\d+[^\]]*\|「证据」\]\])")


class PublishValidationError(ValueError):
    pass


def validate_processed_morning_brief(markdown: str) -> None:
    missing = [section for section in REQUIRED_SECTIONS if section not in markdown]
    if missing:
        raise PublishValidationError(f"缺少必需章节：{', '.join(missing)}")
    _validate_section_order(markdown)

    core = _section(markdown, "## 核心阅读区", "## 深度阅读区")
    deep = _section(markdown, "## 深度阅读区", "## 证据区")
    evidence = _section(markdown, "## 证据区", "")
    if not core.strip():
        raise PublishValidationError("核心阅读区为空")
    if not deep.strip():
        raise PublishValidationError("深度阅读区为空")
    if not evidence.strip():
        raise PublishValidationError("证据区为空")

    bad_markers = [marker for marker in FORBIDDEN_CORE_MARKERS if marker in core or marker in deep]
    if bad_markers:
        raise PublishValidationError(f"核心阅读区包含未加工候选包痕迹：{', '.join(bad_markers)}")

    if len(re.findall(r"[\u4e00-\u9fff]", core)) < 80:
        raise PublishValidationError("核心阅读区中文信息量不足")
    if len(re.findall(r"[\u4e00-\u9fff]", deep)) < 80:
        raise PublishValidationError("深度阅读区中文信息量不足")

    headings_without_link = [
        heading for heading in CORE_ENTRY_HEADING_RE.findall(core) if not CLICKABLE_LINK_RE.search(heading)
    ]
    if headings_without_link:
        raise PublishValidationError("核心阅读区条目缺少可点击「link」")

    headings_without_deep_link = [
        heading for heading in CORE_ENTRY_HEADING_RE.findall(core) if not CORE_TO_DEEP_LINK_RE.search(heading)
    ]
    if headings_without_deep_link:
        raise PublishValidationError("核心阅读区条目必须链接到深度阅读区 D 卡")
    _validate_core_deep_link_fanout(core)

    deep_headings = DEEP_ENTRY_HEADING_RE.findall(deep)
    if not deep_headings:
        raise PublishValidationError("深度阅读区缺少 D 编号条目")
    deep_headings_without_evidence_link = [
        heading for heading in deep_headings if not DEEP_TO_EVIDENCE_LINK_RE.search(heading)
    ]
    if deep_headings_without_evidence_link:
        raise PublishValidationError("深度阅读区条目缺少可点击「证据」链接")


def _validate_section_order(markdown: str) -> None:
    positions = [markdown.find(section) for section in REQUIRED_SECTIONS]
    if positions != sorted(positions):
        raise PublishValidationError("晨报章节顺序必须是：核心阅读区、深度阅读区、证据区")


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


def _validate_core_deep_link_fanout(core: str) -> None:
    for heading, number, body in CORE_ENTRY_BLOCK_RE.findall(core):
        deep_ids = _unique_deep_link_ids(f"{heading}\n{body}")
        if len(deep_ids) > MAX_CORE_DEEP_LINKS:
            raise PublishValidationError(
                f"核心阅读区单条判断最多显性关联 {MAX_CORE_DEEP_LINKS} 个深读证据："
                f"第 {number} 条关联 {len(deep_ids)} 个"
            )


def _unique_deep_link_ids(text: str) -> list[str]:
    deep_ids: list[str] = []
    for match in DEEP_LINK_ID_RE.finditer(text):
        deep_id = match.group(2) or match.group(3)
        if deep_id and deep_id not in deep_ids:
            deep_ids.append(deep_id)
    return deep_ids
