from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time, timedelta
from email.utils import parsedate_to_datetime
from typing import Dict, Iterable, List, Tuple
from zoneinfo import ZoneInfo

from info_radar.config import load_registry
from info_radar.dedupe import dedupe_items
from info_radar.directions import DIRECTIONS
from info_radar.fetchers import fetch_source
from info_radar.importers import import_items
from info_radar.models import DirectionSummary, FetchFailure
from info_radar.render import (
    render_candidate_packet_markdown,
    render_candidate_packet_payload,
    write_candidate_packet,
)
from info_radar.scoring import score_item
from info_radar.store import RadarStore


def group_ranked_items(items, per_direction_limit: int = 10, per_source_limit: int | None = None):
    grouped = {direction_id: [] for direction_id in DIRECTIONS}
    used_clusters = set()
    used_urls = set()
    source_counts = {direction_id: {} for direction_id in DIRECTIONS}
    for item in sorted(items, key=lambda scored: scored.score, reverse=True):
        direction_id = item.primary_direction if item.primary_direction in grouped else "macro_ai"
        identity = item.cluster_id or item.url
        if identity in used_clusters or item.url in used_urls:
            continue
        if len(grouped[direction_id]) >= per_direction_limit:
            continue
        if per_source_limit is not None:
            count = source_counts[direction_id].get(item.source_id, 0)
            if count >= per_source_limit:
                continue
        grouped[direction_id].append(item)
        source_counts[direction_id][item.source_id] = source_counts[direction_id].get(item.source_id, 0) + 1
        used_clusters.add(identity)
        used_urls.add(item.url)
    return grouped


def run_pipeline(
    report_date: str,
    registry_path: Path,
    imports_dir: Path,
    staging_dir: Path,
    db_path: Path,
    per_direction_limit: int = 10,
    per_source_limit: int = 4,
    lookback_days: int = 15,
    fetch_workers: int = 12,
    fetch_enabled: bool = True,
):
    registry = load_registry(registry_path)
    store = RadarStore(db_path)
    store.initialize()

    raw_items = []
    failures: List[FetchFailure] = []
    if fetch_enabled:
        fetched_items, failures = fetch_enabled_sources(registry.enabled_sources(), max_workers=fetch_workers)
        raw_items.extend(fetched_items)

    raw_items.extend(load_imports(imports_dir))
    windowed_items = filter_recent_items(raw_items, report_date=report_date, lookback_days=lookback_days)
    deduped = dedupe_items(windowed_items)
    priority_by_source = {source.id: source.priority for source in registry.sources}
    scored = [score_item(item, source_priority=priority_by_source.get(item.source_id, 50)) for item in deduped]
    grouped = group_ranked_items(
        scored,
        per_direction_limit=per_direction_limit,
        per_source_limit=per_source_limit,
    )
    summaries = build_summaries(grouped, per_direction_limit)

    metadata = {
        "fetched": len(raw_items),
        "within_window": len(windowed_items),
        "lookback_days": lookback_days,
        "deduped": len(deduped),
        "rendered": sum(len(items) for items in grouped.values()),
        "failures": len(failures),
    }
    store.save_items(report_date, scored)
    store.record_run(report_date, metadata)

    markdown = render_candidate_packet_markdown(
        report_date=report_date,
        grouped_items=grouped,
        summaries=summaries,
        failures=failures,
        run_metadata=metadata,
    )
    payload = render_candidate_packet_payload(
        report_date=report_date,
        grouped_items=grouped,
        summaries=summaries,
        failures=failures,
        run_metadata=metadata,
    )
    markdown_path, json_path = write_candidate_packet(staging_dir, report_date, markdown, payload)
    return {"candidate_markdown_path": markdown_path, "candidate_json_path": json_path}, metadata


def fetch_enabled_sources(sources, max_workers: int = 12):
    if not sources:
        return [], []
    workers = max(1, min(max_workers, len(sources)))
    items = []
    failures: List[FetchFailure] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_source, source): source for source in sources}
        for future in as_completed(futures):
            source = futures[future]
            try:
                items.extend(future.result())
            except Exception as exc:  # noqa: BLE001 - failures must be visible in the report.
                failures.append(FetchFailure(source.id, source.name, str(exc)))
    return items, sorted(failures, key=lambda failure: failure.source_id)


def filter_recent_items(items, report_date: str, lookback_days: int = 15):
    if lookback_days <= 0:
        return list(items)
    cutoff, window_end = _window_bounds(report_date, lookback_days)
    recent = []
    for item in items:
        published_at = parse_item_datetime(item.published_at)
        if published_at is None:
            recent.append(item)
            continue
        if cutoff <= published_at < window_end:
            recent.append(item)
    return recent


def _window_bounds(report_date: str, lookback_days: int):
    timezone = ZoneInfo("Asia/Shanghai")
    report_day = datetime.strptime(report_date, "%Y-%m-%d").date()
    window_end = datetime.combine(report_day + timedelta(days=1), time.min, tzinfo=timezone)
    cutoff = window_end - timedelta(days=lookback_days)
    return cutoff.astimezone(ZoneInfo("UTC")), window_end.astimezone(ZoneInfo("UTC"))


def parse_item_datetime(value: str):
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed.astimezone(ZoneInfo("UTC"))


def load_imports(imports_dir: Path):
    if not imports_dir.exists():
        return []
    items = []
    for path in sorted(imports_dir.rglob("*")):
        if not _is_import_file(path):
            continue
        source_id = path.stem
        items.extend(import_items(path, source_id=source_id))
    return items


def _is_import_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.name.startswith("."):
        return False
    if path.name.lower() in {"readme.md", "readme.markdown"}:
        return False
    return path.suffix.lower() in {".jsonl", ".md", ".markdown"}


def build_summaries(grouped, per_direction_limit: int):
    summaries = {}
    for direction_id, items in grouped.items():
        shortage = per_direction_limit - len(items)
        summaries[direction_id] = DirectionSummary(
            direction_id=direction_id,
            target=per_direction_limit,
            actual=len(items),
            shortage_reason=f"候选不足 {shortage} 条" if shortage > 0 else "",
        )
    return summaries
