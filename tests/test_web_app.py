import json
from pathlib import Path

from fastapi.testclient import TestClient

from info_radar.web_app import client_host_allowed, create_app, parse_allowed_client_networks


def write_report(path: Path, date: str, title: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{date}.json").write_text(
        json.dumps(
            {
                "date": date,
                "title": title,
                "source_markdown_path": f"/reports/{date}.md",
                "run_stats": {
                    "total_sources": 24,
                    "enabled_sources": 20,
                    "completed_sources": 18,
                    "failed_sources": 2,
                    "fetched_items": 100,
                    "within_window_items": 40,
                    "lookback_days": 15,
                    "deduped_items": 30,
                    "rendered_candidates": 10,
                    "final_core_items": 1,
                    "final_deep_items": 1,
                    "final_evidence_items": 1,
                },
                "core_items": [
                    {
                        "id": "C1",
                        "number": 1,
                        "title": "LLM 风险正在转向应用栈",
                        "abstract": "核心阅读区正文，强调应用栈风险。",
                        "recommendation_reason": "这会影响 agent 权限边界。",
                        "deep_ids": ["D1"],
                        "direction_id": "macro",
                    }
                ],
                "deep_items": [
                    {
                        "id": "D1",
                        "title": "LLM 应用栈漏洞综述",
                        "body": "深度阅读区正文。",
                        "core_argument": "核心论点正文。",
                        "impact": "对我们的影响正文。",
                        "recommendation_reason": "它把风险从模型层抬升到应用栈层。",
                        "evidence_strength": "high",
                        "risk": "未见明显推广。",
                        "evidence_id": "E1",
                        "source_category": "学术论文",
                        "direction_id": "macro",
                    }
                ],
                "evidence_items": [
                    {
                        "id": "E1",
                        "title": "LLM 应用栈漏洞综述",
                        "url": "http://arxiv.org/abs/2606.31639v1",
                        "source_label": "arXiv",
                        "source_type": "arXiv 论文",
                        "source_category": "学术论文",
                        "published_at": "2026-06-30T13:21:43Z",
                        "ad_risk": "未见明显推广",
                        "usage": "支持应用栈风险判断。",
                        "direction_label": "宏观 AI 前沿论点",
                        "direction_id": "macro",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_web_api_serves_reports_and_search(tmp_path: Path) -> None:
    reports_dir = tmp_path / "published"
    write_report(reports_dir, "2026-07-01", "2026-07-01 信息雷达晨报")
    write_report(reports_dir, "2026-06-30", "2026-06-30 信息雷达晨报")
    client = TestClient(create_app(reports_dir=reports_dir, static_dir=None))

    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/api/health").json() == {"status": "ok"}

    reports = client.get("/api/reports").json()
    assert [report["date"] for report in reports] == ["2026-07-01", "2026-06-30"]
    assert reports[0]["core_count"] == 1

    latest = client.get("/api/reports/latest").json()
    assert latest["date"] == "2026-07-01"
    assert latest["core_items"][0]["deep_ids"] == ["D1"]

    report = client.get("/api/reports/2026-06-30").json()
    assert report["title"] == "2026-06-30 信息雷达晨报"

    search = client.get("/api/search", params={"q": "应用栈"}).json()
    assert search["query"] == "应用栈"
    assert search["results"][0]["report_date"] == "2026-07-01"
    assert search["results"][0]["item_type"] == "core"


def test_web_api_records_and_summarizes_reader_analytics(tmp_path: Path) -> None:
    reports_dir = tmp_path / "published"
    analytics_path = tmp_path / "analytics" / "events.jsonl"
    write_report(reports_dir, "2026-07-01", "2026-07-01 信息雷达晨报")
    client = TestClient(create_app(reports_dir=reports_dir, static_dir=None, analytics_path=analytics_path))

    response = client.post(
        "/api/analytics/events",
        json={
            "events": [
                {
                    "event_type": "page_view",
                    "session_id": "session-a",
                    "report_date": "2026-07-01",
                    "created_at": "2026-07-01T08:00:00+08:00",
                },
                {
                    "event_type": "item_view",
                    "session_id": "session-a",
                    "report_date": "2026-07-01",
                    "item_layer": "deep",
                    "item_id": "D11",
                    "direction_id": "timeseries",
                    "source_category": "学术论文",
                    "duration_ms": 4200,
                    "created_at": "2026-07-01T08:00:03+08:00",
                },
                {
                    "event_type": "text_select",
                    "session_id": "session-a",
                    "report_date": "2026-07-01",
                    "item_layer": "deep",
                    "item_id": "D11",
                    "selected_text_excerpt": "x" * 240,
                    "selected_text_length": 240,
                    "created_at": "2026-07-01T08:00:05+08:00",
                },
                {
                    "event_type": "source_open",
                    "session_id": "session-a",
                    "report_date": "2026-07-01",
                    "item_layer": "evidence",
                    "item_id": "E11",
                    "created_at": "2026-07-01T08:00:06+08:00",
                },
            ]
        },
    )

    assert response.status_code == 200
    assert response.json() == {"accepted": 4}
    assert analytics_path.exists()

    summary = client.get("/api/analytics/summary", params={"date": "2026-07-01"}).json()
    assert summary["report_date"] == "2026-07-01"
    assert summary["active_sessions"] == 1
    assert summary["item_view_ms"] == 4200
    assert summary["source_opens"] == 1
    assert summary["text_selections"] == 1
    assert summary["top_items"][0]["item_id"] == "D11"
    assert summary["top_items"][0]["duration_ms"] == 4200

    stored_event = analytics_path.read_text(encoding="utf-8").splitlines()[2]
    assert '"selected_text_excerpt": "' + ("x" * 120) + '"' in stored_event


def test_web_api_returns_404_for_missing_report(tmp_path: Path) -> None:
    client = TestClient(create_app(reports_dir=tmp_path / "published", static_dir=None))

    response = client.get("/api/reports/2026-07-01")

    assert response.status_code == 404


def test_client_host_allowed_limits_reader_to_local_and_10_net() -> None:
    networks = parse_allowed_client_networks("127.0.0.0/8,::1/128,10.0.0.0/8")

    assert client_host_allowed("127.0.0.1", networks)
    assert client_host_allowed("::1", networks)
    assert client_host_allowed("10.10.172.168", networks)
    assert not client_host_allowed("192.168.1.10", networks)
    assert not client_host_allowed("testclient", networks)


def test_static_reader_page_is_served(tmp_path: Path) -> None:
    reports_dir = tmp_path / "published"
    write_report(reports_dir, "2026-07-01", "2026-07-01 信息雷达晨报")
    client = TestClient(create_app(reports_dir=reports_dir, static_dir=Path("web")))

    response = client.get("/")

    assert response.status_code == 200
    assert "信息雷达" in response.text
    assert "TPT技术研发部" in response.text
    assert "要点与来源" not in response.text
    assert "重点判断" in response.text
    assert "来源解读" in response.text
    assert "处理统计" in response.text
    assert "阅读热度" in response.text
    assert 'id="analyticsSummary"' in response.text
    assert 'id="readingPath"' in response.text
    assert 'id="morningTitle"' in response.text
    assert '<span class="pathIcon">1</span>' not in response.text
    assert "今日晨报" not in response.text
    assert "今日信号" not in response.text
    assert "核心阅读区优先" not in response.text
    assert "/api/reports/latest" in response.text
    assert "我的收藏" not in response.text
    assert "techBackdrop" in response.text
    assert "asciiMeshCanvas" in response.text

    css = Path("web/styles.css").read_text(encoding="utf-8")
    assert "asciiMeshCanvas" in css
    assert "Visible mesh background contract" in css
    assert "Wave mesh background contract" in css
    assert "--content-max" in css
    assert "--page-gutter" in css
    assert "--mesh-opacity" in css
    assert "pointer-events: none" in css
    assert "user-select: none" in css
    assert "Reader text must stay fully readable" in css
    assert "-webkit-line-clamp: unset" in css
    assert "prefers-reduced-motion" in css
    assert "runStats" in css
    assert "statItem" in css
    assert "analyticsSummary" in css
    assert "heatGrid" in css
    assert "topReadList" in css

    js = Path("web/app.js").read_text(encoding="utf-8")
    assert "initAsciiMesh" in js
    assert "buildAsciiMeshPattern" in js
    assert "drawAsciiMeshFrame" in js
    assert "WAVE_GLYPHS" in js
    assert "buildWaveMeshCell" in js
    assert "❏" in js
    assert "requestAnimationFrame" in js
    assert "fillText" in js
    assert "已整理" in js
    assert "可读线索" in js
    assert "renderRunStats" in js
    assert "renderReadingPath" in js
    assert "renderAnalyticsSummary" in js
    assert "trackEvent" in js
    assert "IntersectionObserver" in js
    assert "sendBeacon" in js
    assert "selectionchange" in js
    assert "/api/analytics/events" in js
    assert "/api/analytics/summary" in js
    assert "renderIcon" in js
    assert "DIRECTION_ICONS" in js
    assert "buildReportDirectionCounts" in js
    assert "getLayerCounts" in js
    assert "statNumber" in js
    assert "formatNumberOrDash" in js
    assert "directionById" in js
    assert "directionByLabel" in js
    assert "normalizeDirectionLabel" in js
    assert "visibleEvidenceItems" in js
    assert "核心论点" in js
    assert "对我们的影响" in js
    assert "source_category" in js
    assert "sourceCategoryForDeepItem" in js
    assert "direction_id" in js
    assert "direction_label" in js
    assert "source_label" in js
    assert "源状态" in js
    assert "候选池" in js
    assert "lookback_days || 15" not in js
    assert "来源 " in js
    assert "为什么值得读" in js
    assert 'icon: "T"' not in js
    assert 'icon: "M"' not in js
    assert 'icon: "A"' not in js
    assert "深读 " not in js
    assert "高价值候选" not in js
    assert 'aria-label="收藏"' not in js
    assert 'aria-label="打开"' not in js
    assert "iconRow" not in js
