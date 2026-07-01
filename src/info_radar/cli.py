import argparse
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import datetime

from info_radar.config import load_registry
from info_radar.fetchers import fetch_source
from info_radar.importers import import_items
from info_radar.pipeline import run_pipeline
from info_radar.publish import validate_processed_morning_brief
from info_radar.published_report import parse_published_report, write_published_report_json
from info_radar.render import write_markdown


DEFAULT_OUTPUT_DIR = Path("/Users/paul/Documents/Obsidian/Supcon/信息雷达")
DEFAULT_STAGING_DIR = Path(".info_radar/staging")
DEFAULT_WEB_OUTPUT_DIR = Path(".info_radar/published")
DEFAULT_STATIC_DIR = Path("web")


def main(argv=None):
    load_local_env(Path(".env"))
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            paths, metadata = run_pipeline(
                report_date=args.date or today_shanghai(),
                registry_path=args.registry,
                imports_dir=args.imports_dir,
                staging_dir=args.staging_dir,
                db_path=args.db,
                lookback_days=args.lookback_days,
                fetch_workers=args.fetch_workers,
            )
            print(
                json.dumps(
                    {
                        "candidate_markdown_path": str(paths["candidate_markdown_path"]),
                        "candidate_json_path": str(paths["candidate_json_path"]),
                        "metadata": metadata,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if args.command == "fetch":
            registry = load_registry(args.registry)
            source = registry.get(args.source)
            items = fetch_source(source)
            print(json.dumps([item.__dict__ for item in items], ensure_ascii=False))
            return 0
        if args.command == "import":
            items = import_items(args.file, source_id=args.source)
            print(json.dumps([item.__dict__ for item in items], ensure_ascii=False))
            return 0
        if args.command == "render":
            paths, metadata = run_pipeline(
                report_date=args.date or today_shanghai(),
                registry_path=args.registry,
                imports_dir=args.imports_dir,
                staging_dir=args.staging_dir,
                db_path=args.db,
                lookback_days=args.lookback_days,
                fetch_enabled=False,
            )
            print(
                json.dumps(
                    {
                        "candidate_markdown_path": str(paths["candidate_markdown_path"]),
                        "candidate_json_path": str(paths["candidate_json_path"]),
                        "metadata": metadata,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if args.command == "publish":
            report_date = args.date or today_shanghai()
            final_markdown = args.final_file.read_text(encoding="utf-8")
            validate_processed_morning_brief(final_markdown)
            report_path = write_markdown(args.output_dir, report_date, final_markdown)
            published_report = parse_published_report(
                final_markdown,
                report_date=report_date,
                source_markdown_path=str(args.final_file),
            )
            web_report_path = write_published_report_json(args.web_output_dir, published_report)
            print(
                json.dumps(
                    {
                        "report_path": str(report_path),
                        "web_report_path": str(web_report_path),
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if args.command == "web":
            import uvicorn

            from info_radar.web_app import create_app

            app = create_app(reports_dir=args.reports_dir, static_dir=args.static_dir)
            uvicorn.run(app, host=args.host, port=args.port)
            return 0
        parser.print_help()
        return 2
    except Exception as exc:  # noqa: BLE001 - CLI should return readable failures.
        print(f"info-radar: error: {exc}", file=sys.stderr)
        return 1


def build_parser():
    parser = argparse.ArgumentParser(prog="info-radar")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Fetch/import, score, and write a staging candidate packet.")
    add_common_run_args(run_parser)

    fetch_parser = subparsers.add_parser("fetch", help="Fetch one source and print normalized items as JSON.")
    fetch_parser.add_argument("--source", required=True)
    fetch_parser.add_argument("--registry", type=Path, default=Path("config/source_registry.yml"))

    import_parser = subparsers.add_parser("import", help="Parse a manual JSONL/Markdown import file.")
    import_parser.add_argument("--file", type=Path, required=True)
    import_parser.add_argument("--source", required=True)

    render_parser = subparsers.add_parser("render", help="Write a staging candidate packet from manual imports without network fetch.")
    add_common_run_args(render_parser)

    publish_parser = subparsers.add_parser("publish", help="Publish an already processed Markdown report to Obsidian.")
    publish_parser.add_argument("--date", default=None, help="Report date in YYYY-MM-DD. Defaults to Asia/Shanghai today.")
    publish_parser.add_argument("--final-file", type=Path, required=True)
    publish_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    publish_parser.add_argument("--web-output-dir", type=Path, default=DEFAULT_WEB_OUTPUT_DIR)

    web_parser = subparsers.add_parser("web", help="Serve the reader-facing internal web page and read-only API.")
    web_parser.add_argument("--host", default="127.0.0.1")
    web_parser.add_argument("--port", type=int, default=8787)
    web_parser.add_argument("--reports-dir", type=Path, default=DEFAULT_WEB_OUTPUT_DIR)
    web_parser.add_argument("--static-dir", type=Path, default=DEFAULT_STATIC_DIR)
    return parser


def add_common_run_args(parser):
    parser.add_argument("--date", default=None, help="Report date in YYYY-MM-DD. Defaults to Asia/Shanghai today.")
    parser.add_argument("--registry", type=Path, default=Path("config/source_registry.yml"))
    parser.add_argument("--imports-dir", type=Path, default=Path("imports"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--staging-dir", type=Path, default=DEFAULT_STAGING_DIR)
    parser.add_argument("--db", type=Path, default=Path(".info_radar/radar.sqlite"))
    parser.add_argument("--lookback-days", type=int, default=15, help="Keep dated fetched/imported items from the last N days. Unknown dates are retained.")
    parser.add_argument("--fetch-workers", type=int, default=12, help="Parallel network fetch workers for enabled sources.")


def today_shanghai() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")


def load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _strip_env_value(value.strip())


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
