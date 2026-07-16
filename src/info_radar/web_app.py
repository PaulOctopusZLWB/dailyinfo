import json
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address, ip_network
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from info_radar.api_credentials import ApiCredentialStore, CredentialValidationError


def create_app(
    reports_dir: Path | str = ".info_radar/published",
    static_dir: Path | str | None = None,
    analytics_path: Path | str = ".info_radar/analytics/events.jsonl",
    credentials_path: Path | str = ".env",
    settings_local_only: bool = True,
) -> FastAPI:
    repository = ReportRepository(reports_dir)
    analytics = AnalyticsRepository(analytics_path)
    credentials = ApiCredentialStore(credentials_path)
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

    def require_local_settings_access(request: Request) -> None:
        client_host = request.client.host if request.client else ""
        if settings_local_only and not client_host_is_loopback(client_host):
            raise HTTPException(status_code=403, detail="API settings are available from localhost only")

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

    @app.get("/api/analytics/recent")
    def recent_analytics(
        request: Request,
        days: int = Query(default=7, ge=1, le=31),
    ) -> dict[str, Any]:
        require_local_settings_access(request)
        return analytics.recent(days=days)

    @app.get("/api/settings/credentials")
    def credential_status(request: Request) -> JSONResponse:
        require_local_settings_access(request)
        return JSONResponse(
            {
                "credentials": credentials.status(),
                "storage": {
                    "path": str(credentials.path),
                    "local_only": True,
                    "returns_secret_values": False,
                },
            },
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/api/settings/credentials")
    async def update_credentials(request: Request) -> JSONResponse:
        require_local_settings_access(request)
        content_length = _safe_int(request.headers.get("content-length"))
        if content_length > 24_000:
            raise HTTPException(status_code=413, detail="Credential payload is too large")
        if not request.headers.get("content-type", "").lower().startswith("application/json"):
            raise HTTPException(status_code=415, detail="Content-Type must be application/json")
        try:
            payload = await request.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Credential payload must be an object")
        try:
            status = credentials.update(payload.get("values", {}), payload.get("clear", []))
        except CredentialValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return JSONResponse(
            {"credentials": status, "saved": sorted(payload.get("values", {})), "cleared": sorted(payload.get("clear", []))},
            headers={"Cache-Control": "no-store"},
        )

    if static_dir is not None:
        static_path = Path(static_dir)
        index_path = static_path / "index.html"
        settings_path = static_path / "settings.html"

        @app.get("/")
        def index() -> FileResponse:
            if not index_path.exists():
                raise HTTPException(status_code=404, detail="Reader UI not found")
            return FileResponse(index_path)

        @app.get("/settings")
        def settings(request: Request) -> FileResponse:
            require_local_settings_access(request)
            if not settings_path.exists():
                raise HTTPException(status_code=404, detail="API settings UI not found")
            return FileResponse(settings_path, headers={"Cache-Control": "no-store"})

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
    visit_timeout = timedelta(minutes=30)
    active_heartbeat_cap_ms = 15_000
    allowed_event_types = {
        "page_view",
        "page_heartbeat",
        "item_view",
        "deep_open",
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
        attributed_events = self._attribute_visits(events)
        sessions = {event.get("session_id") for event in events if event.get("session_id")}
        visits = {event.get("visit_id") for event in attributed_events if event.get("visit_id")}
        item_view_ms = 0
        page_active_ms = 0
        source_opens = 0
        deep_opens = 0
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
            elif event_type == "deep_open":
                deep_opens += 1
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
            "active_visits": len(visits),
            "page_active_ms": page_active_ms,
            "item_view_ms": item_view_ms,
            "deep_opens": deep_opens,
            "source_opens": source_opens,
            "text_selections": text_selections,
            "top_items": sorted(top_items.values(), key=lambda item: (-item["duration_ms"], item["item_id"]))[:8],
            "hot_items": self._hot_items(attributed_events),
            "source_categories": [
                {"source_category": category, "events": count}
                for category, count in sorted(source_categories.items(), key=lambda item: (-item[1], item[0]))
            ],
        }

    def recent(self, days: int = 7, now: datetime | None = None) -> dict[str, Any]:
        local_tz = ZoneInfo("Asia/Shanghai")
        current = (now or datetime.now(timezone.utc)).astimezone(local_tz)
        start_date = current.date() - timedelta(days=days - 1)
        all_events = self._read_events()
        recent_events = [
            event
            for event in all_events
            if (activity_date := self._activity_date(event, local_tz)) is not None and activity_date >= start_date
        ]
        attributed_events = self._attribute_visits(recent_events)
        analysis_events = [event for event in attributed_events if not self._is_test_session(event.get("session_id", ""))]
        daily: dict[str, dict[str, Any]] = {}
        for event in analysis_events:
            activity_date = self._activity_date(event, local_tz)
            if activity_date is None:
                continue
            key = activity_date.isoformat()
            bucket = daily.setdefault(
                key,
                {
                    "activity_date": key,
                    "events": 0,
                    "sessions": set(),
                    "visits": set(),
                    "page_active_ms": 0,
                    "item_view_ms": 0,
                    "deep_opens": 0,
                    "source_opens": 0,
                    "text_selections": 0,
                    "searches": 0,
                    "filters": 0,
                },
            )
            bucket["events"] += 1
            bucket["sessions"].add(event.get("session_id"))
            bucket["visits"].add(event.get("visit_id"))
            event_type = event.get("event_type")
            duration_ms = max(0, _safe_int(event.get("duration_ms")))
            if event_type == "page_heartbeat":
                bucket["page_active_ms"] += min(duration_ms, self.active_heartbeat_cap_ms)
            elif event_type == "item_view":
                bucket["item_view_ms"] += duration_ms
            elif event_type == "deep_open":
                bucket["deep_opens"] += 1
            elif event_type == "source_open":
                bucket["source_opens"] += 1
            elif event_type == "text_select":
                bucket["text_selections"] += 1
            elif event_type == "search":
                bucket["searches"] += 1
            elif event_type == "filter":
                bucket["filters"] += 1

        daily_rows = []
        for bucket in sorted(daily.values(), key=lambda item: item["activity_date"]):
            bucket["sessions"] = len({value for value in bucket["sessions"] if value})
            bucket["visits"] = len({value for value in bucket["visits"] if value})
            daily_rows.append(bucket)

        event_types: dict[str, int] = defaultdict(int)
        for event in analysis_events:
            event_types[event.get("event_type", "unknown")] += 1
        heartbeat_events = event_types.get("page_heartbeat", 0)
        missing_visit_ids = sum(1 for event in recent_events if not event.get("visit_id"))
        test_events = len(recent_events) - len(analysis_events)
        return {
            "generated_at": _now_iso(),
            "timezone": "Asia/Shanghai",
            "start_date": start_date.isoformat(),
            "end_date": current.date().isoformat(),
            "events": len(analysis_events),
            "sessions": len({event.get("session_id") for event in analysis_events if event.get("session_id")}),
            "visits": len({event.get("visit_id") for event in analysis_events if event.get("visit_id")}),
            "event_types": dict(sorted(event_types.items())),
            "daily": daily_rows,
            "hot_items": self._hot_items(analysis_events),
            "quality": {
                "test_events_excluded": test_events,
                "legacy_events_missing_visit_id": missing_visit_ids,
                "heartbeat_share": round(heartbeat_events / len(analysis_events), 4) if analysis_events else 0,
                "heartbeat_duration_is_capped": True,
            },
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
            "event_id": _clean_string(raw.get("event_id"), 80),
            "session_id": session_id,
            "visit_id": _clean_string(raw.get("visit_id"), 80),
            "report_date": report_date,
            "item_layer": _clean_string(raw.get("item_layer"), 20),
            "item_id": _clean_string(raw.get("item_id"), 24),
            "context_item_id": _clean_string(raw.get("context_item_id"), 24),
            "direction_id": _clean_string(raw.get("direction_id"), 40),
            "source_category": _clean_string(raw.get("source_category"), 40),
            "query": _clean_string(raw.get("query"), 80),
            "filter_type": _clean_string(raw.get("filter_type"), 40),
            "filter_value": _clean_string(raw.get("filter_value"), 80),
            "duration_ms": max(0, _safe_int(raw.get("duration_ms"))),
            "scroll_depth": max(0, min(100, _safe_int(raw.get("scroll_depth")))),
            "selected_text_excerpt": selected_text,
            "selected_text_length": selected_length,
            "created_at": _clean_string(raw.get("created_at"), 64) or _now_iso(),
            "received_at": _now_iso(),
        }

    def _attribute_visits(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        attributed = [dict(event) for event in events]
        by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for event in attributed:
            by_session[event.get("session_id", "")].append(event)
        for session_id, session_events in by_session.items():
            session_events.sort(key=lambda event: self._event_time(event) or datetime.min.replace(tzinfo=timezone.utc))
            visit_number = 0
            previous_time: datetime | None = None
            for event in session_events:
                event_time = self._event_time(event)
                if event.get("visit_id"):
                    previous_time = event_time or previous_time
                    continue
                if previous_time is None or event_time is None or event_time - previous_time > self.visit_timeout:
                    visit_number += 1
                event["visit_id"] = f"legacy:{session_id}:{visit_number}"
                previous_time = event_time or previous_time
        return attributed

    def _hot_items(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        metrics: dict[tuple[str, str, str], dict[str, Any]] = {}
        for event in events:
            if self._is_test_session(event.get("session_id", "")):
                continue
            event_type = event.get("event_type")
            if event_type not in {"item_view", "deep_open", "source_open", "text_select"}:
                continue
            item_id = event.get("context_item_id") or event.get("item_id") or ""
            if not item_id:
                continue
            item_layer = "deep" if event.get("context_item_id") else (event.get("item_layer") or "")
            report_date = event.get("report_date") or ""
            key = (report_date, item_layer, item_id)
            item = metrics.setdefault(
                key,
                {
                    "report_date": report_date,
                    "item_layer": item_layer,
                    "item_id": item_id,
                    "direction_id": event.get("direction_id", ""),
                    "source_category": event.get("source_category", ""),
                    "view_ms_by_visit": defaultdict(int),
                    "deep_open_visits": set(),
                    "source_open_visits": set(),
                    "selection_visits": set(),
                },
            )
            visit_id = event.get("visit_id") or event.get("session_id")
            if event_type == "item_view":
                item["view_ms_by_visit"][visit_id] += max(0, _safe_int(event.get("duration_ms")))
            elif event_type == "deep_open":
                item["deep_open_visits"].add(visit_id)
            elif event_type == "source_open":
                item["source_open_visits"].add(visit_id)
            elif event_type == "text_select":
                item["selection_visits"].add(visit_id)

        results = []
        for item in metrics.values():
            capped_view_ms = sum(min(duration, 120_000) for duration in item["view_ms_by_visit"].values())
            effective_views = sum(1 for duration in item["view_ms_by_visit"].values() if duration >= 2_000)
            deep_opens = len(item["deep_open_visits"])
            source_opens = len(item["source_open_visits"])
            text_selections = len(item["selection_visits"])
            score = (
                effective_views
                + 2 * deep_opens
                + 4 * source_opens
                + 5 * text_selections
                + math.log1p(capped_view_ms / 1000)
            )
            results.append(
                {
                    "report_date": item["report_date"],
                    "item_layer": item["item_layer"],
                    "item_id": item["item_id"],
                    "direction_id": item["direction_id"],
                    "source_category": item["source_category"],
                    "effective_views": effective_views,
                    "view_duration_ms": capped_view_ms,
                    "deep_opens": deep_opens,
                    "source_opens": source_opens,
                    "text_selections": text_selections,
                    "hot_score": round(score, 3),
                }
            )
        return sorted(results, key=lambda item: (-item["hot_score"], item["item_id"]))[:10]

    @staticmethod
    def _event_time(event: dict[str, Any]) -> datetime | None:
        for key in ("created_at", "received_at"):
            value = event.get(key)
            if not value:
                continue
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    def _activity_date(self, event: dict[str, Any], timezone_info: ZoneInfo):
        event_time = self._event_time(event)
        return event_time.astimezone(timezone_info).date() if event_time else None

    @staticmethod
    def _is_test_session(session_id: str) -> bool:
        normalized = str(session_id).lower()
        return any(marker in normalized for marker in ("manual", "test", "check"))


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


def client_host_is_loopback(host: str) -> bool:
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


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
