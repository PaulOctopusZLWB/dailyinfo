import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from ipaddress import ip_address, ip_network
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def create_app(
    reports_dir: Path | str = ".info_radar/published",
    static_dir: Path | str | None = None,
    analytics_path: Path | str = ".info_radar/analytics/events.jsonl",
) -> FastAPI:
    repository = ReportRepository(reports_dir)
    analytics = AnalyticsRepository(analytics_path)
    app = FastAPI(title="Info Radar Reader", docs_url=None, redoc_url=None)
    allowed_networks = parse_allowed_client_networks(os.environ.get("INFO_RADAR_ALLOWED_CLIENT_NETS", ""))

    @app.middleware("http")
    async def restrict_client_networks(request: Request, call_next):
        if allowed_networks and not client_host_allowed(request.client.host if request.client else "", allowed_networks):
            return JSONResponse({"detail": "Forbidden"}, status_code=403)
        return await call_next(request)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/health")
    def api_health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/reports")
    def list_reports() -> list[dict[str, Any]]:
        return repository.list_reports()

    @app.get("/api/reports/latest")
    def latest_report() -> dict[str, Any]:
        report = repository.latest_report()
        if report is None:
            raise HTTPException(status_code=404, detail="No published reports found")
        return report

    @app.get("/api/reports/{report_date}")
    def get_report(report_date: str) -> dict[str, Any]:
        report = repository.get_report(report_date)
        if report is None:
            raise HTTPException(status_code=404, detail=f"Report not found: {report_date}")
        return report

    @app.get("/api/search")
    def search_reports(q: str = Query(default="", min_length=0)) -> dict[str, Any]:
        return {"query": q, "results": repository.search(q)}

    @app.post("/api/analytics/events")
    async def record_analytics_events(request: Request) -> dict[str, int]:
        payload = await request.json()
        events = payload.get("events", payload if isinstance(payload, list) else [])
        if not isinstance(events, list):
            raise HTTPException(status_code=400, detail="events must be a list")
        return {"accepted": analytics.record_events(events)}

    @app.get("/api/analytics/summary")
    def analytics_summary(date: str = Query(..., min_length=10, max_length=10)) -> dict[str, Any]:
        return analytics.summary(date)

    if static_dir is not None:
        static_path = Path(static_dir)
        index_path = static_path / "index.html"

        @app.get("/")
        def index() -> FileResponse:
            if not index_path.exists():
                raise HTTPException(status_code=404, detail="Reader UI not found")
            return FileResponse(index_path)

        app.mount("/assets", StaticFiles(directory=static_path), name="assets")

    return app


class ReportRepository:
    def __init__(self, reports_dir: Path | str):
        self.reports_dir = Path(reports_dir)

    def list_reports(self) -> list[dict[str, Any]]:
        reports = []
        for path in self._report_paths():
            report = self._read_report(path)
            reports.append(
                {
                    "date": report.get("date", path.stem),
                    "title": report.get("title", path.stem),
                    "core_count": len(report.get("core_items", [])),
                    "deep_count": len(report.get("deep_items", [])),
                    "evidence_count": len(report.get("evidence_items", [])),
                }
            )
        return reports

    def latest_report(self) -> dict[str, Any] | None:
        paths = self._report_paths()
        if not paths:
            return None
        return self._read_report(paths[0])

    def get_report(self, report_date: str) -> dict[str, Any] | None:
        path = self.reports_dir / f"{report_date}.json"
        if not path.exists():
            return None
        return self._read_report(path)

    def search(self, query: str) -> list[dict[str, Any]]:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []
        results = []
        for path in self._report_paths():
            report = self._read_report(path)
            report_date = report.get("date", path.stem)
            for item_type, key in (
                ("core", "core_items"),
                ("deep", "deep_items"),
                ("evidence", "evidence_items"),
            ):
                for item in report.get(key, []):
                    searchable = json.dumps(item, ensure_ascii=False).lower()
                    if normalized_query not in searchable:
                        continue
                    results.append(
                        {
                            "report_date": report_date,
                            "item_type": item_type,
                            "id": item.get("id", ""),
                            "title": item.get("title", ""),
                        }
                    )
        return results

    def _report_paths(self) -> list[Path]:
        if not self.reports_dir.exists():
            return []
        return sorted(self.reports_dir.glob("*.json"), key=lambda path: path.stem, reverse=True)

    def _read_report(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))


class AnalyticsRepository:
    allowed_event_types = {
        "page_view",
        "page_heartbeat",
        "item_view",
        "source_open",
        "search",
        "filter",
        "text_select",
    }

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def record_events(self, events: list[Any]) -> int:
        normalized = [event for event in (self._normalize_event(raw) for raw in events) if event]
        if not normalized:
            return 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            for event in normalized:
                handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return len(normalized)

    def summary(self, report_date: str) -> dict[str, Any]:
        events = [event for event in self._read_events() if event.get("report_date") == report_date]
        sessions = {event.get("session_id") for event in events if event.get("session_id")}
        item_view_ms = 0
        page_active_ms = 0
        source_opens = 0
        text_selections = 0
        top_items: dict[tuple[str, str], dict[str, Any]] = {}
        source_categories: dict[str, int] = defaultdict(int)
        for event in events:
            event_type = event.get("event_type")
            duration_ms = _safe_int(event.get("duration_ms"))
            if event_type == "item_view":
                item_view_ms += duration_ms
                item_key = (event.get("item_layer") or "", event.get("item_id") or "")
                if item_key[1]:
                    item = top_items.setdefault(
                        item_key,
                        {
                            "item_layer": item_key[0],
                            "item_id": item_key[1],
                            "direction_id": event.get("direction_id", ""),
                            "source_category": event.get("source_category", ""),
                            "duration_ms": 0,
                            "views": 0,
                        },
                    )
                    item["duration_ms"] += duration_ms
                    item["views"] += 1
            elif event_type == "page_heartbeat":
                page_active_ms += duration_ms
            elif event_type == "source_open":
                source_opens += 1
            elif event_type == "text_select":
                text_selections += 1
            category = event.get("source_category")
            if category:
                source_categories[category] += 1
        return {
            "report_date": report_date,
            "events": len(events),
            "active_sessions": len(sessions),
            "page_active_ms": page_active_ms,
            "item_view_ms": item_view_ms,
            "source_opens": source_opens,
            "text_selections": text_selections,
            "top_items": sorted(top_items.values(), key=lambda item: (-item["duration_ms"], item["item_id"]))[:8],
            "source_categories": [
                {"source_category": category, "events": count}
                for category, count in sorted(source_categories.items(), key=lambda item: (-item[1], item[0]))
            ],
        }

    def _read_events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
        return events

    def _normalize_event(self, raw: Any) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        event_type = _clean_string(raw.get("event_type"), 40)
        report_date = _clean_string(raw.get("report_date"), 10)
        session_id = _clean_string(raw.get("session_id"), 80)
        if event_type not in self.allowed_event_types or not report_date or not session_id:
            return None
        selected_text = _clean_string(raw.get("selected_text_excerpt"), 120)
        selected_length = _safe_int(raw.get("selected_text_length"))
        if selected_text and selected_length < len(selected_text):
            selected_length = len(selected_text)
        return {
            "event_type": event_type,
            "session_id": session_id,
            "report_date": report_date,
            "item_layer": _clean_string(raw.get("item_layer"), 20),
            "item_id": _clean_string(raw.get("item_id"), 24),
            "direction_id": _clean_string(raw.get("direction_id"), 40),
            "source_category": _clean_string(raw.get("source_category"), 40),
            "duration_ms": max(0, _safe_int(raw.get("duration_ms"))),
            "scroll_depth": max(0, min(100, _safe_int(raw.get("scroll_depth")))),
            "selected_text_excerpt": selected_text,
            "selected_text_length": selected_length,
            "created_at": _clean_string(raw.get("created_at"), 64) or _now_iso(),
            "received_at": _now_iso(),
        }


def parse_allowed_client_networks(value: str):
    networks = []
    for raw in (value or "").split(","):
        token = raw.strip()
        if not token:
            continue
        networks.append(ip_network(token, strict=False))
    return tuple(networks)


def client_host_allowed(host: str, networks) -> bool:
    try:
        client_ip = ip_address(host)
    except ValueError:
        return False
    return any(client_ip in network for network in networks)


def _clean_string(value: Any, max_length: int) -> str:
    if value is None:
        return ""
    return str(value).strip()[:max_length]


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
