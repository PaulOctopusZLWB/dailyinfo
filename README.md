# Info Radar

Info Radar v0 是一个本地优先的手动决策雷达。它读取候选源池和手工导入材料，去重、评分、按六个方向分组，并生成 staging 候选包。

正式 Obsidian 日报不由 `run` 直接生成。日报必须经过 Codex/LLM/人工二次加工后，再用 `publish` 写入：

`/Users/paul/Documents/Obsidian/Supcon/信息雷达/YYYY-MM-DD 信息雷达.md`

## Run

```bash
uv run info-radar run --date 2026-07-01
```

这会写入：

- `.info_radar/staging/2026-07-01-candidates.md`
- `.info_radar/staging/2026-07-01-candidates.json`

加工后的 Markdown 才能发布到 Obsidian：

```bash
uv run info-radar publish --date 2026-07-01 --final-file path/to/processed.md
```

`publish` 会校验正式晨报格式：

- 必须包含 `## 核心阅读区`、`## 深度阅读区` 和 `## 证据区`，顺序不能颠倒。
- 核心阅读区必须是中文加工稿，不能含 `初步核心论述`、`原始摘录`、`材料主张` 等候选包痕迹。
- 核心阅读区面向早晨快速阅读，只放加工后的重点判断；不设固定条数上限。
- 核心阅读区必须在每个方向内优先离散不同论点，不要把 8-10 个来源硬合并成一个大判断。
- 深度阅读区面向高价值源，一源一卡，提炼单个核心源的核心论述、推荐理由、证据强度和风险提示。
- 证据区只做回溯，保留原始 URL、来源类型、发布时间、软文风险和重复/聚类信息。
- 链接链路必须是 `核心阅读区 -> 深度阅读区 -> 证据区 -> 原文 URL`：核心标题用 `[[#D1. ...|「link」]]` 指向深读卡，深读标题用 `[[#E1. ...|「证据」]]` 指向证据卡。
- 每条核心判断最多显性关联 3 个深度阅读 D 卡；超过 3 个时必须拆成多个核心判断。

只渲染手工导入、不做网络抓取：

```bash
uv run info-radar render --date 2026-07-01
```

解析单个手工导入文件：

```bash
uv run info-radar import --file imports/example.jsonl --source manual-cn
```

抓取单个源并输出 JSON：

```bash
uv run info-radar fetch --source arxiv-ai
```

## Authenticated Sources

X 源默认不会抓取登录态内容，也不会从 Chrome 或浏览器 cookie 中抽取隐藏 token。推荐流程是：

1. 用 Chrome 登录 X Developer Console，进入 Project/App 的 `Keys and tokens`。
2. 复制官方 `Bearer Token`。
3. 在本机创建 `.env`，或直接在 shell 中 export：

```bash
cp .env.example .env
# 编辑 .env，把 token 写入 X_BEARER_TOKEN 或 TWITTER_BEARER_TOKEN
uv run info-radar fetch --source tnd-karpathy-twitter
```

CLI 会自动读取当前目录 `.env`，但不会覆盖已经在 shell 中 export 的环境变量。`.env` 已被 `.gitignore` 排除，不应提交真实 token。

## Web Reader

发布后的 JSON 默认写入 `.info_radar/published`。本机读者页启动方式：

```bash
uv run info-radar web --host 127.0.0.1 --port 8787
```

如果希望在本机临时挂着读者页，可以用项目脚本配合 `tmux`：

```bash
tmux new-session -d -s info-radar-web -c /Users/paul/Documents/info_radar './ops/bin/run-web.sh'
```

`ops/bin/run-web.sh` 默认绑定 `0.0.0.0:8787`，但应用层只允许本机和 `10.0.0.0/8` 客户端访问：

```bash
INFO_RADAR_ALLOWED_CLIENT_NETS=127.0.0.0/8,::1/128,10.0.0.0/8 ./ops/bin/run-web.sh
```

常驻服务使用 launchd：

```bash
mkdir -p ~/Library/LaunchAgents .info_radar/logs
cp ops/launchd/com.paul.info-radar-web.plist ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.paul.info-radar-web.plist
launchctl kickstart -k "gui/$(id -u)/com.paul.info-radar-web"
```

当前服务地址：

`http://127.0.0.1:8787/`

内网访问地址示例：

`http://10.10.172.168:8787/`

读者页会记录匿名阅读行为，用于改进信息质量和源权重。事件写入 `.info_radar/analytics/events.jsonl`，默认只保存匿名 session、页面/卡片停留、来源打开、筛选搜索和最多 120 字的划取摘要，不保存用户姓名或完整鼠标轨迹。

## v0 Boundaries

- 定时任务由 Codex automation 负责触发；`run` 和 `publish` 仍保持可手动复跑。
- `run` 和 `render` 只生成候选包，不写正式 Obsidian 日报。
- 写入 Obsidian 前必须经过 Codex/LLM/人工二次加工；未加工候选包不能直接发布。
- 不绕过平台权限、paywall、DRM 或付费社群限制。
- Bilibili、知识星球先走手工导入或预留入口；X 只通过官方 API token 抓公开时间线。
- 目标是每个方向最多 10 个候选；新增方向后候选包目标会按方向数动态计算，但质量优先于硬凑数量。
- 没有 LLM API key 也能运行；后续可把 LLM 接到摘要、方向分类和软文判断环节。
- 当前日报主输出是“核心观点/论述”和“推荐理由”，不是原始摘录列表。
- 当前核心阅读区是观点沉淀层：同方向内优先拆出不同机制链、不同证据类型和不同决策含义，每条最多显性关联 3 个深读证据。
- 当前候选包内置四段式 LLM 加工协议：`Evidence Extractor`、`Single Source Distiller`、`Ad / Bias Auditor`、`Morning Brief Renderer`。没有 LLM 时仍可手工按同一协议加工。
- 当前观点抽象是本地规则层：会清洗 HTML、抽取 claim 句、用中文结构说明推荐理由；正式发布前需要按三层晨报协议做人工或 LLM 二次加工。
- 网络抓取统一带 User-Agent，并对短时 SSL/超时失败做重试；失败源仍会显式写入日报。

## Directions

- 宏观 AI 前沿论点
- 时序模型、时序算法、时序认知、时序应用前沿
- 工业控制软件 + AI 结合前沿
- 最佳使用 AI agent 的 GitHub 库、方法论、认知、讨论、重要观点
- 面向人类的数字孪生
- AI 时代的泛哲学讨论
