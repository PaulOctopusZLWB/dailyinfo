import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from info_radar.models import RadarItem


def import_items(path: Path, source_id: str) -> List[RadarItem]:
    if path.suffix.lower() == ".jsonl":
        return _import_jsonl(path, source_id)
    if path.suffix.lower() in {".md", ".markdown"}:
        return _import_markdown(path, source_id)
    raise ValueError(f"unsupported import file type: {path.suffix}")


def _import_jsonl(path: Path, source_id: str) -> List[RadarItem]:
    items = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number} invalid JSONL") from exc
        items.append(_row_to_item(row, source_id))
    return items


def _import_markdown(path: Path, source_id: str) -> List[RadarItem]:
    sections = []
    current_title = None
    current_lines: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if current_title is not None:
                sections.append((current_title, current_lines))
            current_title = line.removeprefix("## ").strip()
            current_lines = []
        elif current_title is not None:
            current_lines.append(line)
    if current_title is not None:
        sections.append((current_title, current_lines))

    items = []
    for title, lines in sections:
        fields: Dict[str, str] = {"title": title}
        body_lines: List[str] = []
        reading_fields = True
        for line in lines:
            if reading_fields and not line.strip():
                reading_fields = False
                continue
            if reading_fields and ":" in line:
                key, value = line.split(":", 1)
                fields[key.strip()] = value.strip()
            else:
                body_lines.append(line)
        fields["content_or_excerpt"] = "\n".join(line for line in body_lines if line.strip()).strip()
        items.append(_row_to_item(fields, source_id))
    return items


def _row_to_item(row: Dict[str, object], source_id: str) -> RadarItem:
    required = ["title", "url", "source_name", "published_at", "content_or_excerpt"]
    missing = [field for field in required if not str(row.get(field, "")).strip()]
    if missing:
        raise ValueError(f"import item missing fields: {', '.join(missing)}")

    direction_hint = row.get("direction_hint", row.get("direction_hints", ()))
    return RadarItem(
        source_id=source_id,
        source_name=str(row["source_name"]),
        source_type="manual",
        title=str(row["title"]).strip(),
        url=str(row["url"]).strip(),
        published_at=str(row["published_at"]).strip(),
        content_or_excerpt=str(row["content_or_excerpt"]).strip(),
        direction_hints=_parse_direction_hints(direction_hint),
    )


def _parse_direction_hints(value: object) -> Tuple[str, ...]:
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, list):
        return tuple(str(part).strip() for part in value if str(part).strip())
    if isinstance(value, tuple):
        return tuple(str(part).strip() for part in value if str(part).strip())
    return ()
