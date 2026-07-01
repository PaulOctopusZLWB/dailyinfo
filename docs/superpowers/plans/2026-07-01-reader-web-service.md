# Reader Web Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reader-facing internal web service for published Info Radar daily reports.

**Architecture:** Keep the existing CLI as the maintenance/generation layer. Add a published-report JSON exporter, a read-only FastAPI service, and a static reader UI that renders latest/date-specific reports from JSON.

**Tech Stack:** Python 3.12-compatible package, FastAPI, Uvicorn, vanilla HTML/CSS/JavaScript, pytest.

---

## File Structure

- Create `src/info_radar/published_report.py`: dataclasses and Markdown parser for published three-layer reports.
- Modify `src/info_radar/cli.py`: `publish` writes structured JSON and new `web` command starts the server.
- Create `src/info_radar/web_app.py`: FastAPI app factory, JSON report repository, API routes, static asset serving.
- Create `web/index.html`, `web/styles.css`, `web/app.js`: reader-only UI.
- Modify `pyproject.toml`: add FastAPI, Uvicorn, and HTTPX test dependency.
- Add tests:
  - `tests/test_published_report.py`
  - `tests/test_web_app.py`
  - Update `tests/test_store_and_cli.py`

### Task 1: Published Report Parser

**Files:**
- Create: `src/info_radar/published_report.py`
- Test: `tests/test_published_report.py`

- [ ] **Step 1: Write failing parser test**

Create a test with one core item, one deep card, and one evidence card:

```python
from pathlib import Path

from info_radar.published_report import parse_published_report, write_published_report_json


SAMPLE = """# 2026-07-01 信息雷达晨报

## 核心阅读区

### 1. LLM 风险正在转向应用栈 [[#D1. LLM 应用栈漏洞综述|「link」]]
核心判断正文。

推荐理由：这会影响 agent 权限和工具调用边界。

## 深度阅读区

### D1. LLM 应用栈漏洞综述 [[#E1. LLM 应用栈漏洞综述|「证据」]]
单源深度提炼正文。

- 推荐理由：它把风险从模型层抬升到应用栈层。
- 证据强度：high，系统性综述。
- 风险提示：未见明显推广。

## 证据区

### E1. LLM 应用栈漏洞综述
- 原文：[A Lifecycle Survey](http://arxiv.org/abs/2606.31639v1)
- 来源类型：arXiv 论文
- 发布时间：2026-06-30T13:21:43Z
- 软文风险：未见明显推广
- 用途：支持应用栈风险判断。
"""


def test_parse_published_report_extracts_three_layers(tmp_path: Path) -> None:
    report = parse_published_report(SAMPLE, report_date="2026-07-01", source_markdown_path="/tmp/report.md")

    assert report.date == "2026-07-01"
    assert report.title == "2026-07-01 信息雷达晨报"
    assert report.core_items[0].id == "C1"
    assert report.core_items[0].deep_ids == ["D1"]
    assert report.core_items[0].recommendation_reason == "这会影响 agent 权限和工具调用边界。"
    assert report.deep_items[0].id == "D1"
    assert report.deep_items[0].evidence_id == "E1"
    assert report.deep_items[0].evidence_strength == "high"
    assert report.evidence_items[0].url == "http://arxiv.org/abs/2606.31639v1"


def test_write_published_report_json_writes_date_file(tmp_path: Path) -> None:
    report = parse_published_report(SAMPLE, report_date="2026-07-01")
    path = write_published_report_json(tmp_path, report)

    assert path == tmp_path / "2026-07-01.json"
    assert '"core_items"' in path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_published_report.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'info_radar.published_report'`.

- [ ] **Step 3: Implement parser and JSON writer**

Implement dataclasses `PublishedReport`, `CoreItem`, `DeepItem`, `EvidenceItem`, `parse_published_report`, and `write_published_report_json`.

- [ ] **Step 4: Run parser tests**

Run: `uv run pytest tests/test_published_report.py -q`

Expected: PASS.

### Task 2: Publish Writes Web JSON

**Files:**
- Modify: `src/info_radar/cli.py`
- Test: `tests/test_store_and_cli.py`

- [ ] **Step 1: Write failing CLI test update**

Update `test_cli_publish_writes_processed_markdown_to_obsidian` so the publish command passes `--web-output-dir <tmp>/published` and asserts `<tmp>/published/2026-07-01.json` exists and contains `core_items`, `deep_items`, and `evidence_items`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_store_and_cli.py::test_cli_publish_writes_processed_markdown_to_obsidian -q`

Expected: FAIL because `--web-output-dir` is unknown.

- [ ] **Step 3: Add CLI option and export**

Add `DEFAULT_WEB_OUTPUT_DIR = Path(".info_radar/published")`. Add `--web-output-dir` to `publish`. After `validate_processed_morning_brief`, parse the final Markdown and write JSON to the web output directory.

- [ ] **Step 4: Run CLI publish test**

Run: `uv run pytest tests/test_store_and_cli.py::test_cli_publish_writes_processed_markdown_to_obsidian -q`

Expected: PASS.

### Task 3: Read-Only API

**Files:**
- Create: `src/info_radar/web_app.py`
- Modify: `src/info_radar/cli.py`
- Modify: `pyproject.toml`
- Test: `tests/test_web_app.py`

- [ ] **Step 1: Write failing API tests**

Create tests using `fastapi.testclient.TestClient` for `/healthz`, `/api/reports`, `/api/reports/latest`, `/api/reports/2026-07-01`, and `/api/search?q=应用栈`.

- [ ] **Step 2: Run API tests to verify failure**

Run: `uv run pytest tests/test_web_app.py -q`

Expected: FAIL because FastAPI dependency and `info_radar.web_app` do not exist.

- [ ] **Step 3: Add dependencies**

Add runtime dependencies:

```toml
"fastapi>=0.115.0",
"uvicorn>=0.30.0",
```

Add dev dependency:

```toml
"httpx>=0.27.0",
```

Run: `uv lock`

- [ ] **Step 4: Implement API app**

Implement `create_app(reports_dir: Path | str = ".info_radar/published", static_dir: Path | str | None = None)` and routes:

- `GET /healthz`
- `GET /api/reports`
- `GET /api/reports/latest`
- `GET /api/reports/{report_date}`
- `GET /api/search`

- [ ] **Step 5: Add CLI web command**

Add:

```bash
uv run info-radar web --host 127.0.0.1 --port 8787 --reports-dir .info_radar/published
```

- [ ] **Step 6: Run API tests**

Run: `uv run pytest tests/test_web_app.py -q`

Expected: PASS.

### Task 4: Reader Static Frontend

**Files:**
- Create: `web/index.html`
- Create: `web/styles.css`
- Create: `web/app.js`
- Test: `tests/test_web_app.py`

- [ ] **Step 1: Write failing static asset test**

Add a test that creates the app with `static_dir=Path("web")`, requests `/`, and asserts the HTML includes `信息雷达`, `核心阅读区`, and `/api/reports/latest`.

- [ ] **Step 2: Run static test to verify failure**

Run: `uv run pytest tests/test_web_app.py::test_static_reader_page_is_served -q`

Expected: FAIL because `web/index.html` does not exist or static route is not mounted.

- [ ] **Step 3: Implement static reader UI**

Build vanilla HTML/CSS/JS:

- Latest report loads on first page.
- Core items are primary cards.
- Deep cards render below and can be filtered by clicking `深读`.
- Evidence opens in a right-side drawer.
- Search filters core/deep/evidence text.
- Date selector uses `/api/reports`.

- [ ] **Step 4: Run static test**

Run: `uv run pytest tests/test_web_app.py::test_static_reader_page_is_served -q`

Expected: PASS.

### Task 5: Verification and Local Service

**Files:**
- Modify docs if commands changed.

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest`

Expected: all tests pass.

- [ ] **Step 2: Compile Python**

Run: `uv run python -m compileall src`

Expected: exit 0.

- [ ] **Step 3: Publish current processed report to web JSON**

Run:

```bash
uv run info-radar publish --date 2026-07-01 --final-file .info_radar/processed/2026-07-01-processed.md --output-dir /Users/paul/Documents/Obsidian/Supcon/信息雷达 --web-output-dir .info_radar/published
```

Expected: writes `.info_radar/published/2026-07-01.json`.

- [ ] **Step 4: Start local service**

Run:

```bash
nohup uv run info-radar web --host 127.0.0.1 --port 8787 --reports-dir .info_radar/published > .info_radar/web.log 2>&1 & echo $! > .info_radar/web.pid
```

- [ ] **Step 5: Smoke test service**

Run:

```bash
curl -s http://127.0.0.1:8787/healthz
curl -s http://127.0.0.1:8787/api/reports/latest | python -m json.tool | head
```

Expected: health returns `{"status":"ok"}` and latest report returns JSON.
