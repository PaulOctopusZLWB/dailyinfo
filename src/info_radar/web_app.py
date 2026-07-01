import json
import os
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
) -> FastAPI:
    repository = ReportRepository(reports_dir)
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
