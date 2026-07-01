import json
import os
import subprocess
import sys
from pathlib import Path

from info_radar.cli import load_local_env
from info_radar.store import RadarStore


def test_store_persists_items_and_run_metadata(tmp_path: Path) -> None:
    db_path = tmp_path / "radar.sqlite"
    store = RadarStore(db_path)
    store.initialize()
    store.record_run("2026-07-01", {"fetched": 2, "rendered": 1})

    assert store.get_run("2026-07-01")["rendered"] == 1


def test_load_local_env_does_not_override_exported_values(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text('X_BEARER_TOKEN="local-token"\nGITHUB_TOKEN=file-token\n', encoding="utf-8")
    monkeypatch.setenv("GITHUB_TOKEN", "exported-token")
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)

    load_local_env(env_file)

    assert os.environ["X_BEARER_TOKEN"] == "local-token"
    assert os.environ["GITHUB_TOKEN"] == "exported-token"


def test_cli_run_generates_candidate_packet_without_obsidian_report(tmp_path: Path) -> None:
    registry_file = tmp_path / "registry.yml"
    imports_dir = tmp_path / "imports"
    output_dir = tmp_path / "obsidian"
    staging_dir = tmp_path / "staging"
    db_path = tmp_path / "radar.sqlite"
    imports_dir.mkdir()

    registry_file.write_text(
        """
sources:
  - id: manual-cn
    name: 中文手工导入
    type: manual
    url: file://manual
    directions: [macro_ai, temporal, industrial_ai, ai_agents, human_digital_twin]
    language_hint: zh
    priority: 80
    enabled: true
    notes: Manual imports for restricted platforms.
""",
        encoding="utf-8",
    )

    import_file = imports_dir / "items.jsonl"
    rows = [
        {
            "title": "Agent workflow repo",
            "url": "https://github.com/example/agent-workflow",
            "source_name": "X 手工导入",
            "published_at": "2026-06-30T08:00:00+08:00",
            "content_or_excerpt": "GitHub repo benchmark for best agent workflow.",
            "direction_hint": "ai_agents",
        },
        {
            "title": "工业控制 AI 案例",
            "url": "https://example.com/industrial-ai",
            "source_name": "Bilibili 手工导入",
            "published_at": "2026-06-30T09:00:00+08:00",
            "content_or_excerpt": "DCS SCADA control software with AI copilot in factory.",
            "direction_hint": "industrial_ai",
        },
    ]
    import_file.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
    transcript_dir = imports_dir / "youtube-transcripts"
    transcript_dir.mkdir()
    transcript_row = {
        "title": "YouTube agent interview transcript",
        "url": "https://www.youtube.com/watch?v=agent",
        "source_name": "YouTube transcript",
        "published_at": "2026-06-30T10:00:00+08:00",
        "content_or_excerpt": "An interview about agent evaluation and reproducible workflows.",
        "direction_hint": "ai_agents",
    }
    (transcript_dir / "agent-interview.jsonl").write_text(
        json.dumps(transcript_row, ensure_ascii=False),
        encoding="utf-8",
    )
    (imports_dir / "README.md").write_text(
        "# 手工导入说明\n\n## JSONL\n\n不是导入材料。\n\n## Markdown\n\n也不是导入材料。",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "info_radar.cli",
            "run",
            "--date",
            "2026-07-01",
            "--registry",
            str(registry_file),
            "--imports-dir",
            str(imports_dir),
            "--output-dir",
            str(output_dir),
            "--staging-dir",
            str(staging_dir),
            "--db",
            str(db_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    markdown_path = Path(payload["candidate_markdown_path"])
    json_path = Path(payload["candidate_json_path"])
    assert markdown_path == staging_dir / "2026-07-01-candidates.md"
    assert json_path == staging_dir / "2026-07-01-candidates.json"
    assert not (output_dir / "2026-07-01 信息雷达.md").exists()

    packet = markdown_path.read_text(encoding="utf-8")
    assert "Codex 加工任务" in packet
    assert "Agent workflow repo" in packet
    assert "工业控制 AI 案例" in packet
    assert "YouTube agent interview transcript" in packet
    assert "不要把本候选包原样写入 Obsidian" in packet


def test_cli_publish_writes_processed_markdown_to_obsidian(tmp_path: Path) -> None:
    final_file = tmp_path / "processed.md"
    output_dir = tmp_path / "obsidian"
    web_output_dir = tmp_path / "published"
    final_file.write_text(
        "# 2026-07-01 信息雷达晨报\n\n"
        "## 核心阅读区\n\n"
        "### 1. Agent 工作流开始从脚本集合变成可评测的软件工程系统 [[#D1. Agent workflow repo|「link」]]\n"
        "过去一天的候选源显示，agent 领域的增量不在单个工具发布，而在工作流可验证性：浏览器自动化、沙盒运行、表格端到端 benchmark 和 provider 兼容性问题同时出现。"
        "这说明 agent 工程正在从演示能力转向可复现、可审计、可迁移的系统能力。对我们来说，值得跟进的是哪些能力已经能沉淀成 FDE/个人工作流里的稳定接口，而不是继续追逐单点 demo。\n\n"
        "推荐理由：这条线索把多个候选源合并成一个判断，具体增量是 agent 的评价对象从“能否完成任务”转向“能否在受控环境里稳定完成复杂业务工作流”。这会影响我们后续选择 agent 库、设计本地自动化和构建晨报加工层的方式。\n\n"
        "## 深度阅读区\n\n"
        "### D1. Agent workflow repo [[#E1. Agent 工作流证据|「证据」]]\n"
        "这个来源的价值不在于又提供了一个 agent demo，而在于它把 agent 工作流作为可运行、可复现、可调试的软件对象来组织。它暗示后续 agent 选型不能只看任务完成率，还要看轨迹记录、环境隔离、失败定位和依赖边界是否能被工程化沉淀。对我们的决策意义是：FDE 和晨报加工层都应优先选择能暴露执行证据的 agent 框架。\n\n"
        "- 推荐理由：它把“agent 能力”落到了可验证工程接口上，可直接影响库选型和系统边界设计。\n"
        "- 证据强度：medium，来源是项目材料，需要后续用 issue、release 和真实任务验证。\n"
        "- 风险提示：未见明显风险。\n\n"
        "## 证据区\n\n"
        "### E1. Agent 工作流证据\n"
        "- 来源：https://github.com/example/agent-workflow\n"
        "- 来源类型：GitHub / 论文 / issue 聚合\n"
        "- 软文风险：未见明显推广\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "info_radar.cli",
            "publish",
            "--date",
            "2026-07-01",
            "--final-file",
            str(final_file),
            "--output-dir",
            str(output_dir),
            "--web-output-dir",
            str(web_output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    report_path = output_dir / "2026-07-01 信息雷达.md"
    report = report_path.read_text(encoding="utf-8")
    assert "## 核心阅读区" in report
    assert "## 深度阅读区" in report
    assert "## 证据区" in report
    assert "[[#D1. Agent workflow repo|「link」]]" in report
    assert "[[#E1. Agent 工作流证据|「证据」]]" in report
    assert "agent 工程正在从演示能力转向可复现、可审计、可迁移的系统能力" in report

    web_report = json.loads((web_output_dir / "2026-07-01.json").read_text(encoding="utf-8"))
    assert web_report["date"] == "2026-07-01"
    assert web_report["core_items"][0]["deep_ids"] == ["D1"]
    assert web_report["deep_items"][0]["evidence_id"] == "E1"
    assert web_report["evidence_items"][0]["url"] == "https://github.com/example/agent-workflow"


def test_cli_publish_rejects_unprocessed_candidate_markdown(tmp_path: Path) -> None:
    final_file = tmp_path / "bad.md"
    output_dir = tmp_path / "obsidian"
    final_file.write_text(
        "# 2026-07-01 信息雷达候选包\n\n"
        "## 核心阅读区\n\n"
        "### 1. Agent workflow repo\n"
        "- 初步核心论述：核心论述：围绕「Agent workflow repo」，材料主张：GitHub repo benchmark.\n"
        "- 推荐理由：值得推荐：它与方向直接相关，证据类型为代码/开源项目。\n\n"
        "## 深度阅读区\n\n"
        "### D1. Agent workflow repo [[#E1. Agent 工作流证据|「证据」]]\n"
        "初步推荐理由：值得推荐：它与方向直接相关，证据类型为代码/开源项目。\n\n"
        "## 证据区\n\n"
        "- 原始摘录：GitHub repo benchmark for best agent workflow.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "info_radar.cli",
            "publish",
            "--date",
            "2026-07-01",
            "--final-file",
            str(final_file),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "核心阅读区包含未加工候选包痕迹" in result.stderr
    assert not (output_dir / "2026-07-01 信息雷达.md").exists()


def test_cli_publish_rejects_missing_morning_brief_sections(tmp_path: Path) -> None:
    final_file = tmp_path / "bad.md"
    output_dir = tmp_path / "obsidian"
    final_file.write_text("# 2026-07-01 信息雷达\n\n## 今日需要判断的事\n\n内容。\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "info_radar.cli",
            "publish",
            "--date",
            "2026-07-01",
            "--final-file",
            str(final_file),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "缺少必需章节" in result.stderr
    assert not (output_dir / "2026-07-01 信息雷达.md").exists()


def test_cli_publish_rejects_core_entries_without_clickable_link(tmp_path: Path) -> None:
    final_file = tmp_path / "bad.md"
    output_dir = tmp_path / "obsidian"
    final_file.write_text(
        "# 2026-07-01 信息雷达晨报\n\n"
        "## 核心阅读区\n\n"
        "### 1. Agent 工作流开始从脚本集合变成可评测的软件工程系统\n"
        "过去一天的候选源显示，agent 领域的增量不在单个工具发布，而在工作流可验证性：浏览器自动化、沙盒运行、表格端到端 benchmark 和 provider 兼容性问题同时出现。"
        "这说明 agent 工程正在从演示能力转向可复现、可审计、可迁移的系统能力。对我们来说，值得跟进的是哪些能力已经能沉淀成 FDE/个人工作流里的稳定接口，而不是继续追逐单点 demo。\n\n"
        "推荐理由：这条线索把多个候选源合并成一个判断，具体增量是 agent 的评价对象从“能否完成任务”转向“能否在受控环境里稳定完成复杂业务工作流”。这会影响我们后续选择 agent 库、设计本地自动化和构建晨报加工层的方式。\n\n"
        "## 深度阅读区\n\n"
        "### D1. Agent workflow repo [[#E1. Agent 工作流证据|「证据」]]\n"
        "这个来源的价值不在于又提供了一个 agent demo，而在于它把 agent 工作流作为可运行、可复现、可调试的软件对象来组织。它暗示后续 agent 选型不能只看任务完成率，还要看轨迹记录、环境隔离、失败定位和依赖边界是否能被工程化沉淀。\n\n"
        "## 证据区\n\n"
        "### E1. Agent 工作流证据\n"
        "- 来源：https://github.com/example/agent-workflow\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "info_radar.cli",
            "publish",
            "--date",
            "2026-07-01",
            "--final-file",
            str(final_file),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "核心阅读区条目缺少可点击「link」" in result.stderr
    assert not (output_dir / "2026-07-01 信息雷达.md").exists()


def test_cli_publish_rejects_core_entries_linking_directly_to_evidence(tmp_path: Path) -> None:
    final_file = tmp_path / "bad.md"
    output_dir = tmp_path / "obsidian"
    final_file.write_text(
        "# 2026-07-01 信息雷达晨报\n\n"
        "## 核心阅读区\n\n"
        "### 1. Agent 工作流开始从脚本集合变成可评测的软件工程系统 [[#E1. Agent 工作流证据|「link」]]\n"
        "过去一天的候选源显示，agent 领域的增量不在单个工具发布，而在工作流可验证性：浏览器自动化、沙盒运行、表格端到端 benchmark 和 provider 兼容性问题同时出现。"
        "这说明 agent 工程正在从演示能力转向可复现、可审计、可迁移的系统能力。对我们来说，值得跟进的是哪些能力已经能沉淀成 FDE/个人工作流里的稳定接口，而不是继续追逐单点 demo。\n\n"
        "## 深度阅读区\n\n"
        "### D1. Agent workflow repo [[#E1. Agent 工作流证据|「证据」]]\n"
        "这个来源的价值不在于又提供了一个 agent demo，而在于它把 agent 工作流作为可运行、可复现、可调试的软件对象来组织。它暗示后续 agent 选型不能只看任务完成率，还要看轨迹记录、环境隔离、失败定位和依赖边界是否能被工程化沉淀。\n\n"
        "## 证据区\n\n"
        "### E1. Agent 工作流证据\n"
        "- 来源：https://github.com/example/agent-workflow\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "info_radar.cli",
            "publish",
            "--date",
            "2026-07-01",
            "--final-file",
            str(final_file),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "核心阅读区条目必须链接到深度阅读区 D 卡" in result.stderr
    assert not (output_dir / "2026-07-01 信息雷达.md").exists()


def test_cli_publish_rejects_deep_entries_without_evidence_link(tmp_path: Path) -> None:
    final_file = tmp_path / "bad.md"
    output_dir = tmp_path / "obsidian"
    final_file.write_text(
        "# 2026-07-01 信息雷达晨报\n\n"
        "## 核心阅读区\n\n"
        "### 1. Agent 工作流开始从脚本集合变成可评测的软件工程系统 [[#D1. Agent workflow repo|「link」]]\n"
        "过去一天的候选源显示，agent 领域的增量不在单个工具发布，而在工作流可验证性：浏览器自动化、沙盒运行、表格端到端 benchmark 和 provider 兼容性问题同时出现。"
        "这说明 agent 工程正在从演示能力转向可复现、可审计、可迁移的系统能力。对我们来说，值得跟进的是哪些能力已经能沉淀成 FDE/个人工作流里的稳定接口，而不是继续追逐单点 demo。\n\n"
        "## 深度阅读区\n\n"
        "### D1. Agent workflow repo\n"
        "这个来源的价值不在于又提供了一个 agent demo，而在于它把 agent 工作流作为可运行、可复现、可调试的软件对象来组织。它暗示后续 agent 选型不能只看任务完成率，还要看轨迹记录、环境隔离、失败定位和依赖边界是否能被工程化沉淀。\n\n"
        "## 证据区\n\n"
        "### E1. Agent 工作流证据\n"
        "- 来源：https://github.com/example/agent-workflow\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "info_radar.cli",
            "publish",
            "--date",
            "2026-07-01",
            "--final-file",
            str(final_file),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "深度阅读区条目缺少可点击「证据」链接" in result.stderr
    assert not (output_dir / "2026-07-01 信息雷达.md").exists()


def test_cli_web_help_exposes_reader_service_options() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "info_radar.cli",
            "web",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--reports-dir" in result.stdout
    assert "--host" in result.stdout
    assert "--port" in result.stdout
