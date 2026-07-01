const state = {
  report: null,
  reports: [],
  activeQuery: "",
  activeDirection: "all",
};

const nodes = {
  dateSelect: document.querySelector("#dateSelect"),
  searchInput: document.querySelector("#searchInput"),
  categoryTabs: document.querySelector("#categoryTabs"),
  morningTitle: document.querySelector("#morningTitle"),
  overviewTitle: document.querySelector("#overviewTitle"),
  reportMeta: document.querySelector("#reportMeta"),
  summaryChips: document.querySelector("#summaryChips"),
  runStats: document.querySelector("#runStats"),
  coreList: document.querySelector("#coreList"),
  deepList: document.querySelector("#deepList"),
  sectionEnd: document.querySelector("#sectionEnd"),
  readingPath: document.querySelector("#readingPath"),
  sourceList: document.querySelector("#sourceList"),
  drawer: document.querySelector("#evidenceDrawer"),
  drawerTitle: document.querySelector("#drawerTitle"),
  drawerBody: document.querySelector("#drawerBody"),
  closeDrawer: document.querySelector("#closeDrawer"),
  meshCanvas: document.querySelector("#asciiMeshCanvas"),
};

const DIRECTIONS = [
  {
    id: "all",
    label: "全部",
    shortLabel: "全部",
    icon: "grid",
    keywords: [],
  },
  {
    id: "macro",
    label: "宏观AI前沿论点",
    shortLabel: "宏观AI前沿论点",
    icon: "brain",
    keywords: ["LLM", "模型", "风险", "治理", "OpenAI", "AGI", "AI 时代", "agent"],
  },
  {
    id: "timeseries",
    label: "时序智能",
    shortLabel: "时序智能",
    icon: "wave",
    keywords: ["时序", "预测", "TimeGPT", "Moirai", "TSMixer", "序列", "forecast"],
  },
  {
    id: "industrial",
    label: "工业软件+AI",
    shortLabel: "工业软件+AI",
    icon: "factory",
    keywords: ["工业", "工控", "流程", "Siemens", "AVEVA", "AspenTech", "Seeq", "优化"],
  },
  {
    id: "agent",
    label: "AI Agent 生态",
    shortLabel: "AI Agent 生态",
    icon: "bot",
    keywords: ["Agent", "agent", "GitHub", "SDK", "工具", "沙盒", "benchmark", "复现"],
  },
  {
    id: "twin",
    label: "数字孪生",
    shortLabel: "数字孪生",
    icon: "cube",
    keywords: ["数字孪生", "孪生", "个人上下文", "人类", "仿真", "上下文系统"],
  },
  {
    id: "philosophy",
    label: "AI时代的泛哲学讨论",
    shortLabel: "泛哲学讨论",
    icon: "orbit",
    keywords: ["哲学", "自由意志", "责任", "主体", "人机", "意识", "边界"],
  },
];

const DIRECTION_ICONS = {
  grid: '<path d="M4 4h6v6H4z"/><path d="M14 4h6v6h-6z"/><path d="M4 14h6v6H4z"/><path d="M14 14h6v6h-6z"/>',
  brain: '<path d="M9 3a3 3 0 0 0-3 3v.5A3.5 3.5 0 0 0 4 13a3 3 0 0 0 2 5.2"/><path d="M15 3a3 3 0 0 1 3 3v.5A3.5 3.5 0 0 1 20 13a3 3 0 0 1-2 5.2"/><path d="M9 3v18"/><path d="M15 3v18"/><path d="M9 8H6.5"/><path d="M15 8h2.5"/><path d="M9 14H6.2"/><path d="M15 14h2.8"/>',
  wave: '<path d="M4 12h3l2.2-6 4.2 12L16 8h4"/><path d="M4 18h16"/>',
  factory: '<path d="M3 21h18"/><path d="M5 21V9l5 3V9l5 3V6h4v15"/><path d="M8 17h1"/><path d="M12 17h1"/><path d="M16 17h1"/>',
  bot: '<path d="M12 8V4"/><path d="M8 4h8"/><rect x="5" y="8" width="14" height="11" rx="3"/><path d="M9 13h.01"/><path d="M15 13h.01"/><path d="M9 17h6"/><path d="M3 12h2"/><path d="M19 12h2"/>',
  cube: '<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12 4 7.5"/><path d="m12 12 8-4.5"/><path d="M12 12v9"/>',
  orbit: '<circle cx="12" cy="12" r="3"/><path d="M19 5c2.4 2.4-.2 8.8-5.7 14.3"/><path d="M5 19c-2.4-2.4.2-8.8 5.7-14.3"/><path d="M4.5 8.5c1.3-3.2 8.7-2.6 15 1.4"/><path d="M19.5 15.5c-1.3 3.2-8.7 2.6-15-1.4"/>',
};

const WAVE_GLYPHS = ["□", "▢", "▣", "▤", "▥", "▦", "▧", "▨", "▩", "❏", "❐", "❑", "❒"];
const MESH_CELL_PITCH = 23;
const MESH_SCROLL_SPEED = 18;
const MESH_DPR_CAP = 1.35;
const MESH_ROTATION = (-13 * Math.PI) / 180;
const meshState = {
  canvas: null,
  context: null,
  patternCanvas: null,
  width: 0,
  height: 0,
  patternWidth: 0,
  patternHeight: 0,
  offset: 0,
  lastTime: 0,
  animationId: 0,
  reduceMotion: false,
};

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${url}`);
  }
  return response.json();
}

async function loadInitialReport() {
  const [reports, latest] = await Promise.all([
    fetchJson("/api/reports"),
    fetchJson("/api/reports/latest"),
  ]);
  state.reports = reports;
  state.report = latest;
  renderDateSelect();
  renderReport();
}

function renderDateSelect() {
  nodes.dateSelect.innerHTML = state.reports
    .map((report) => `<option value="${escapeHtml(report.date)}">${escapeHtml(report.date)}</option>`)
    .join("");
  nodes.dateSelect.value = state.report.date;
}

function renderReport() {
  const report = state.report;
  const layerCounts = getLayerCounts(report);
  document.title = `${report.date} 信息雷达`;
  nodes.morningTitle.textContent = `${report.date} 晨报`;
  nodes.overviewTitle.textContent = `${report.date} 信号`;
  nodes.reportMeta.textContent = `${report.title || report.date} · 已整理 ${formatNumber(layerCounts.total)} 条可读线索`;
  renderSummaryChips(report);
  renderReadingPath(report);
  renderCoreItems(report);
  renderDeepItems(report);
  renderRunStats(report);
  renderSources(report);
}

function renderSummaryChips(report) {
  const layerCounts = getLayerCounts(report);
  const sourceCount = new Set(
    report.evidence_items.map((item) => item.source_label || sourceLabelFromUrl(item.url) || item.source_type).filter(Boolean),
  ).size;
  const directionCounts = buildReportDirectionCounts(report);
  const metrics = DIRECTIONS.filter((direction) => direction.id !== "all").map((direction) => ({
    ...direction,
    count: directionCounts.get(direction.id) || 0,
  }));
  nodes.summaryChips.innerHTML = metrics
    .map(
      (metric) => `
        <button
          class="metricCard ${metric.id === state.activeDirection ? "is-active" : ""}"
          type="button"
          data-direction-id="${escapeHtml(metric.id)}"
          aria-pressed="${metric.id === state.activeDirection ? "true" : "false"}"
        >
          <span class="metricIcon" aria-hidden="true">${renderIcon(metric.icon)}</span>
          <span class="metricCopy">
            <span>${escapeHtml(metric.shortLabel)}</span>
            <strong>${formatNumber(metric.count)}</strong>
          </span>
        </button>
      `,
    )
    .join("");
  nodes.summaryChips.dataset.total = String(layerCounts.total);
  nodes.summaryChips.dataset.sources = String(sourceCount);
}

function renderReadingPath(report) {
  const counts = getLayerCounts(report);
  const steps = [
    {
      title: "重点判断",
      detail: `${formatNumber(counts.core)} 条核心判断`,
    },
    {
      title: "来源解读",
      detail: `${formatNumber(counts.deep)} 张来源卡`,
    },
    {
      title: "原始来源",
      detail: `${formatNumber(counts.evidence)} 条证据`,
    },
  ];
  nodes.readingPath.innerHTML = steps
    .map(
      (step, index) => `
        <li>
          <span class="pathIcon">${formatNumber(index + 1)}</span>
          <strong>${escapeHtml(step.title)}</strong>
          <small>${escapeHtml(step.detail)}</small>
        </li>
      `,
    )
    .join("");
}

function renderRunStats(report) {
  const stats = report.run_stats || {};
  const layerCounts = getLayerCounts(report);
  const enabledSources = statNumber(stats.enabled_sources);
  const completedSources = statNumber(stats.completed_sources);
  const failedSources = statNumber(stats.failed_sources);
  const fetchedItems = statNumber(stats.fetched_items);
  const withinWindow = statNumber(stats.within_window_items);
  const lookbackDays = statNumber(stats.lookback_days);
  const dedupedItems = statNumber(stats.deduped_items);
  const renderedCandidates = statNumber(stats.rendered_candidates);

  const rows = [
    {
      label: "源状态",
      value: `${formatNumberOrDash(completedSources)}/${formatNumberOrDash(enabledSources)}`,
      detail: formatFailureDetail(failedSources),
    },
    {
      label: "原始材料",
      value: formatNumberOrDash(fetchedItems),
      detail: "抓取与导入总量",
    },
    {
      label: lookbackDays === null ? "时间窗口" : `${formatNumber(lookbackDays)} 天窗口`,
      value: formatNumberOrDash(withinWindow),
      detail: "按发布时间筛选",
    },
    {
      label: "去重后",
      value: formatNumberOrDash(dedupedItems),
      detail: "URL / 标题 / 内容聚类",
    },
    {
      label: "候选池",
      value: formatNumberOrDash(renderedCandidates),
      detail: "进入加工候选包",
    },
    {
      label: "晨报",
      value: `${formatNumber(layerCounts.core)}/${formatNumber(layerCounts.evidence)}`,
      detail: "核心判断 / 证据卡",
    },
  ];

  nodes.runStats.innerHTML = rows
    .map(
      (row) => `
        <div class="statItem">
          <span class="statLabel">${escapeHtml(row.label)}</span>
          <strong>${escapeHtml(row.value)}</strong>
          <small>${escapeHtml(row.detail)}</small>
        </div>
      `,
    )
    .join("");
}

function renderCoreItems(report) {
  const items = filterItems(report.core_items, ["title", "abstract", "recommendation_reason"]);
  if (!items.length) {
    nodes.coreList.innerHTML = `<div class="emptyState">没有匹配的核心阅读条目。</div>`;
    nodes.sectionEnd.textContent = "当前筛选下没有更多核心判断";
    return;
  }
  nodes.sectionEnd.textContent = `已显示 ${formatNumber(items.length)} 条核心判断`;
  nodes.coreList.innerHTML = items
    .map((item) => {
      const links = item.deep_ids
        .map((id) => `<button class="deepButton" type="button" data-deep-id="${escapeHtml(id)}">来源 ${escapeHtml(id)}</button>`)
        .join("");
      const matchedDirection = bestDirectionForItem(item);
      return `
        <article class="card coreCard" id="${escapeHtml(item.id)}">
          <div class="coreNumber">
            <span>${escapeHtml(item.number)}</span>
          </div>
          <div class="coreBody">
            <div class="cardMeta">${escapeHtml(matchedDirection.shortLabel)}</div>
            <h3>${escapeHtml(item.title)}</h3>
            <p class="abstract">${escapeHtml(item.abstract)}</p>
            <p class="reason">为什么值得读：${escapeHtml(item.recommendation_reason)}</p>
          </div>
          <div class="coreActions">
            <div class="deepLinks">${links}</div>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderDeepItems(report) {
  const items = filterItems(report.deep_items, ["title", "body", "core_argument", "impact", "recommendation_reason", "risk", "source_category"]);
  if (!items.length) {
    nodes.deepList.innerHTML = `<div class="emptyState">没有匹配的深度阅读卡。</div>`;
    return;
  }
  nodes.deepList.innerHTML = items
    .map((item) => {
      const matchedDirection = bestDirectionForItem(item);
      const sourceCategory = item.source_category || sourceCategoryForDeepItem(report, item);
      const coreArgument = item.core_argument || item.body || "";
      const impact = item.impact || item.recommendation_reason || "";
      return `
      <article class="card deepCard" id="${escapeHtml(item.id)}">
        <div class="deepTop">
          <span class="deepBadge">${escapeHtml(item.id)}</span>
          <div>
            <div class="cardMeta">
              <span>${escapeHtml(matchedDirection.shortLabel)}</span>
              <span class="sourceCategory">${escapeHtml(sourceCategory)}</span>
            </div>
            <h3>${escapeHtml(item.title)}</h3>
          </div>
        </div>
        <div class="deepSections">
          <section class="deepSection">
            <h4>核心论点</h4>
            <p>${escapeHtml(coreArgument)}</p>
          </section>
          <section class="deepSection">
            <h4>对我们的影响</h4>
            <p>${escapeHtml(impact)}</p>
          </section>
        </div>
        <div class="deepMeta">
          <span class="tag">证据强度 ${escapeHtml(item.evidence_strength || "unknown")}</span>
          <span class="tag risk">${escapeHtml(item.risk || "未标注风险")}</span>
          <button class="evidenceButton" type="button" data-evidence-id="${escapeHtml(item.evidence_id)}">查看来源</button>
        </div>
      </article>
    `;
    })
    .join("");
}

function renderSources(report) {
  const groups = new Map();
  visibleEvidenceItems(report).forEach((item) => {
    const key = item.source_label || sourceLabelFromUrl(item.url) || item.source_type || "未标注来源";
    const entry = groups.get(key) || { count: 0, types: new Set() };
    entry.count += 1;
    if (item.source_type) {
      entry.types.add(item.source_type);
    }
    groups.set(key, entry);
  });
  if (!groups.size) {
    nodes.sourceList.innerHTML = `<div class="emptyState compact">当前筛选下没有来源。</div>`;
    return;
  }
  nodes.sourceList.innerHTML = Array.from(groups.entries())
    .sort((a, b) => b[1].count - a[1].count || a[0].localeCompare(b[0]))
    .map(
      ([source, entry]) => `
        <div class="sourceItem">
          <span class="sourceName">
            <strong>${escapeHtml(source)}</strong>
            <small>${escapeHtml(Array.from(entry.types).join(" / ") || "来源")}</small>
          </span>
          <span class="sourceCount">${formatNumber(entry.count)}</span>
        </div>
      `,
    )
    .join("");
}

function filterItems(items, fields) {
  const query = state.activeQuery.trim().toLowerCase();
  return items.filter((item) => {
    const matchesQuery =
      !query || fields.some((field) => String(item[field] || "").toLowerCase().includes(query));
    const matchesDirection =
      state.activeDirection === "all" || itemMatchesDirection(item, state.activeDirection);
    return matchesQuery && matchesDirection;
  });
}

function renderCategoryTabs() {
  nodes.categoryTabs.innerHTML = DIRECTIONS.map(
    (direction) => `
      <button
        class="categoryTab ${direction.id === state.activeDirection ? "is-active" : ""}"
        type="button"
        data-direction-id="${escapeHtml(direction.id)}"
        aria-pressed="${direction.id === state.activeDirection ? "true" : "false"}"
      >
        <span class="categoryGlyph" aria-hidden="true">${renderIcon(direction.icon)}</span>
        <span>${escapeHtml(direction.label)}</span>
      </button>
    `,
  ).join("");
}

function buildReportDirectionCounts(report) {
  const counts = new Map();
  DIRECTIONS.filter((direction) => direction.id !== "all").forEach((direction) => {
    counts.set(direction.id, 0);
  });

  const counted = new Set();
  const add = (itemType, item, direction) => {
    const key = `${itemType}:${item.id}`;
    if (counted.has(key)) {
      return;
    }
    counted.add(key);
    counts.set(direction.id, (counts.get(direction.id) || 0) + 1);
  };

  report.core_items.forEach((coreItem) => {
    add("core", coreItem, bestDirectionForItem(coreItem));
  });

  report.deep_items.forEach((deepItem) => {
    add("deep", deepItem, bestDirectionForItem(deepItem));
  });
  report.evidence_items.forEach((evidenceItem) => {
    add("evidence", evidenceItem, bestDirectionForItem(evidenceItem));
  });
  return counts;
}

function bestDirectionForItem(item) {
  return bestDirectionsForItem(item)[0] || DIRECTIONS[1];
}

function bestDirectionsForItem(item) {
  if (item.direction_id) {
    const direction = directionById(item.direction_id);
    if (direction) {
      return [direction];
    }
  }
  if (item.direction_label) {
    const direction = directionByLabel(item.direction_label);
    if (direction) {
      return [direction];
    }
  }
  const text = itemText(item).toLowerCase();
  const matches = DIRECTIONS.filter((direction) => direction.id !== "all")
    .map((direction) => ({
      direction,
      score: direction.keywords.filter((keyword) => text.includes(keyword.toLowerCase())).length,
    }))
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score)
    .map((entry) => entry.direction);
  return matches.length ? matches : [DIRECTIONS[1]];
}

function directionById(directionId) {
  return DIRECTIONS.find((direction) => direction.id === directionId);
}

function directionByLabel(label) {
  const normalized = normalizeDirectionLabel(label);
  const aliases = {
    "宏观ai前沿论点": "macro",
    "时序智能": "timeseries",
    "时序模型时序算法时序认知时序应用前沿": "timeseries",
    "工业软件ai": "industrial",
    "工业控制软件ai结合前沿": "industrial",
    "aiagent生态": "agent",
    "最佳使用aiagent的github库方法论认知讨论重要观点": "agent",
    "数字孪生": "twin",
    "面向人类的数字孪生": "twin",
    "ai时代的泛哲学讨论": "philosophy",
    "泛哲学讨论": "philosophy",
  };
  return directionById(aliases[normalized]);
}

function normalizeDirectionLabel(label) {
  return String(label || "")
    .toLowerCase()
    .replace(/[\s+＋、，,·/／\-—_]/g, "");
}

function itemMatchesDirection(item, directionId) {
  return bestDirectionsForItem(item).some((direction) => direction.id === directionId);
}

function itemText(item) {
  return [
    item.title,
    item.abstract,
    item.body,
    item.recommendation_reason,
    item.risk,
    item.evidence_strength,
    item.direction_id,
    item.direction_label,
    item.source_category,
    item.source_label,
    item.source_type,
    item.usage,
    item.url,
  ]
    .filter(Boolean)
    .join(" ");
}

function visibleEvidenceItems(report) {
  const query = state.activeQuery.trim().toLowerCase();
  const hasActiveFilter = query || state.activeDirection !== "all";
  if (!hasActiveFilter) {
    return report.evidence_items;
  }

  const ids = new Set();
  filterItems(report.deep_items, ["title", "body", "recommendation_reason", "risk"]).forEach((item) => {
    if (item.evidence_id) {
      ids.add(item.evidence_id);
    }
  });
  filterItems(report.evidence_items, ["title", "source_label", "source_type", "usage", "url"]).forEach((item) => {
    ids.add(item.id);
  });
  return report.evidence_items.filter((item) => ids.has(item.id));
}

function sourceLabelFromUrl(url) {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    if (host.includes("arxiv.org")) return "arXiv";
    if (host.includes("github.com")) return "GitHub";
    if (host.includes("cisa.gov")) return "CISA ICS";
    if (host.includes("seeq.com")) return "Seeq";
    return host;
  } catch {
    return "";
  }
}

function sourceCategoryForDeepItem(report, deepItem) {
  const evidence = report.evidence_items.find((item) => item.id === deepItem.evidence_id);
  if (!evidence) {
    return deepItem.source_category || "未分类来源";
  }
  return evidence.source_category || evidence.source_type || "未分类来源";
}

function renderIcon(iconName) {
  const paths = DIRECTION_ICONS[iconName] || DIRECTION_ICONS.grid;
  return `<svg class="directionIcon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" focusable="false">${paths}</svg>`;
}

function getLayerCounts(report) {
  const stats = report.run_stats || {};
  const core = statNumber(stats.final_core_items) ?? report.core_items.length;
  const deep = statNumber(stats.final_deep_items) ?? report.deep_items.length;
  const evidence = statNumber(stats.final_evidence_items) ?? report.evidence_items.length;
  return {
    core,
    deep,
    evidence,
    total: core + deep + evidence,
  };
}

function statNumber(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return null;
  }
  return numeric;
}

function formatNumber(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "—";
  }
  return numeric.toLocaleString("zh-CN");
}

function formatNumberOrDash(value) {
  if (value === null || value === undefined) {
    return "—";
  }
  return formatNumber(value);
}

function formatFailureDetail(failedSources) {
  if (failedSources === null) {
    return "失败源未记录";
  }
  if (failedSources === 0) {
    return "无失败源";
  }
  return `${formatNumber(failedSources)} 个失败`;
}

function initAsciiMesh() {
  if (!nodes.meshCanvas) {
    return;
  }
  const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  const rebuild = () => {
    buildAsciiMeshPattern(nodes.meshCanvas);
    drawAsciiMeshFrame();
  };
  const updateMotion = () => {
    meshState.reduceMotion = motionQuery.matches;
    if (meshState.animationId) {
      cancelAnimationFrame(meshState.animationId);
      meshState.animationId = 0;
    }
    meshState.lastTime = 0;
    if (meshState.reduceMotion) {
      drawAsciiMeshFrame();
      return;
    }
    meshState.animationId = requestAnimationFrame(animateAsciiMesh);
  };

  let resizeTimer = 0;
  window.addEventListener("resize", () => {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => {
      rebuild();
      updateMotion();
    }, 120);
  });
  if (typeof motionQuery.addEventListener === "function") {
    motionQuery.addEventListener("change", updateMotion);
  } else if (typeof motionQuery.addListener === "function") {
    motionQuery.addListener(updateMotion);
  }

  rebuild();
  updateMotion();
}

function buildAsciiMeshPattern(canvas) {
  const viewportWidth = Math.max(document.documentElement.clientWidth, window.innerWidth || 0, 960);
  const viewportHeight = Math.max(document.documentElement.clientHeight, window.innerHeight || 0, 760);
  const dpr = Math.min(window.devicePixelRatio || 1, MESH_DPR_CAP);
  const context = canvas.getContext("2d", { alpha: true });
  canvas.width = Math.ceil(viewportWidth * dpr);
  canvas.height = Math.ceil(viewportHeight * dpr);
  canvas.style.width = `${viewportWidth}px`;
  canvas.style.height = `${viewportHeight}px`;
  context.setTransform(dpr, 0, 0, dpr, 0, 0);

  const patternWidth = Math.ceil(viewportWidth * 1.36 + 280);
  const patternHeight = Math.ceil(viewportHeight * 1.62 + 180);
  const patternCanvas = document.createElement("canvas");
  patternCanvas.width = Math.ceil(patternWidth * dpr);
  patternCanvas.height = Math.ceil(patternHeight * dpr);
  const patternContext = patternCanvas.getContext("2d", { alpha: true });
  patternContext.setTransform(dpr, 0, 0, dpr, 0, 0);
  patternContext.clearRect(0, 0, patternWidth, patternHeight);
  patternContext.textAlign = "center";
  patternContext.textBaseline = "middle";
  patternContext.font = '700 11px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace';

  const rows = Math.ceil(patternHeight / MESH_CELL_PITCH);
  const cols = Math.ceil(patternWidth / MESH_CELL_PITCH);
  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < cols; col += 1) {
      const cell = buildWaveMeshCell(row, col, rows, cols);
      const x = col * MESH_CELL_PITCH + MESH_CELL_PITCH / 2;
      const y = row * MESH_CELL_PITCH + MESH_CELL_PITCH / 2;
      drawMeshCell(patternContext, cell, x, y);
    }
  }

  meshState.canvas = canvas;
  meshState.context = context;
  meshState.patternCanvas = patternCanvas;
  meshState.width = viewportWidth;
  meshState.height = viewportHeight;
  meshState.patternWidth = patternWidth;
  meshState.patternHeight = patternHeight;
}

function drawMeshCell(context, cell, x, y) {
  context.save();
  context.globalAlpha = cell.alpha;
  if (cell.variant !== "void") {
    const size = cell.variant === "crest" ? 15 : 14;
    context.fillStyle = cell.fill;
    context.strokeStyle = cell.stroke;
    context.lineWidth = 1;
    context.beginPath();
    addRoundedRect(context, x - size / 2, y - size / 2, size, size, 2.5);
    context.fill();
    context.stroke();
  }
  context.fillStyle = cell.color;
  context.fillText(cell.glyph, x, y + 0.5);
  context.restore();
}

function addRoundedRect(context, x, y, width, height, radius) {
  if (typeof context.roundRect === "function") {
    context.roundRect(x, y, width, height, radius);
    return;
  }
  const right = x + width;
  const bottom = y + height;
  context.moveTo(x + radius, y);
  context.lineTo(right - radius, y);
  context.quadraticCurveTo(right, y, right, y + radius);
  context.lineTo(right, bottom - radius);
  context.quadraticCurveTo(right, bottom, right - radius, bottom);
  context.lineTo(x + radius, bottom);
  context.quadraticCurveTo(x, bottom, x, bottom - radius);
  context.lineTo(x, y + radius);
  context.quadraticCurveTo(x, y, x + radius, y);
}

function animateAsciiMesh(timestamp) {
  if (!meshState.lastTime) {
    meshState.lastTime = timestamp;
  }
  const delta = Math.min((timestamp - meshState.lastTime) / 1000, 0.05);
  meshState.lastTime = timestamp;
  meshState.offset = (meshState.offset + MESH_SCROLL_SPEED * delta) % meshState.patternWidth;
  drawAsciiMeshFrame();
  meshState.animationId = requestAnimationFrame(animateAsciiMesh);
}

function drawAsciiMeshFrame() {
  const { context, patternCanvas, width, height, patternWidth, patternHeight } = meshState;
  if (!context || !patternCanvas) {
    return;
  }
  context.clearRect(0, 0, width, height);
  context.save();
  context.globalAlpha = 0.98;
  context.translate(width * 0.52, height * 0.52);
  context.rotate(MESH_ROTATION);
  const startX = -patternWidth * 0.72 - meshState.offset;
  const y = -patternHeight * 0.5;
  for (let x = startX - patternWidth; x < width * 1.45 + patternWidth; x += patternWidth) {
    context.drawImage(patternCanvas, x, y, patternWidth, patternHeight);
  }
  context.restore();
}

function buildWaveMeshCell(row, col, rows, cols) {
  const waveA =
    rows * 0.28 +
    Math.sin(col * 0.08) * 4.6 +
    Math.sin(col * 0.021 + row * 0.16) * 2.8;
  const waveB =
    rows * 0.5 +
    Math.sin(col * 0.064 + 1.9) * 6.2 +
    Math.sin(col * 0.018 + row * 0.11) * 3.4;
  const waveC =
    rows * 0.72 +
    Math.sin(col * 0.052 + 4.1) * 5.4 +
    Math.sin(col * 0.026 + row * 0.09) * 2.6;
  const distance = Math.min(
    Math.abs(row - waveA),
    Math.abs(row - waveB),
    Math.abs(row - waveC),
  );
  const grain =
    Math.sin(col * 0.37 + row * 0.73) +
    Math.sin(col * 0.13) +
    Math.cos((row / rows) * Math.PI * 2);
  const openWater = (col + row * 3) % 17 > 11 && grain < 0.8;
  let variant = "void";
  if (distance < 0.72) {
    variant = "crest";
  } else if (distance < 1.7) {
    variant = "swell";
  } else if (distance < 3.1 || (grain > 1.08 && !openWater)) {
    variant = "ripple";
  } else if (distance < 4.2) {
    variant = "soft";
  }
  const glyphIndex = Math.abs(Math.floor(col * 3 + row * 7 + distance * 5 + cols)) % WAVE_GLYPHS.length;
  const glyph = variant === "void" ? "·" : WAVE_GLYPHS[glyphIndex];
  const palette = {
    crest: {
      alpha: 0.7,
      fill: "rgba(212, 228, 45, 0.28)",
      stroke: "rgba(93, 118, 24, 0.2)",
      color: "rgba(54, 80, 18, 0.62)",
    },
    swell: {
      alpha: 0.58,
      fill: "rgba(0, 143, 140, 0.17)",
      stroke: "rgba(0, 143, 140, 0.16)",
      color: "rgba(0, 92, 90, 0.54)",
    },
    ripple: {
      alpha: 0.42,
      fill: "rgba(172, 217, 209, 0.13)",
      stroke: "rgba(0, 143, 140, 0.09)",
      color: "rgba(0, 96, 92, 0.36)",
    },
    soft: {
      alpha: 0.3,
      fill: "rgba(221, 233, 82, 0.12)",
      stroke: "rgba(116, 135, 32, 0.08)",
      color: "rgba(82, 101, 24, 0.28)",
    },
    void: {
      alpha: 0.16,
      fill: "transparent",
      stroke: "transparent",
      color: "rgba(78, 93, 22, 0.18)",
    },
  };
  return { glyph, variant, ...palette[variant] };
}

function openEvidence(evidenceId) {
  const evidence = state.report.evidence_items.find((item) => item.id === evidenceId);
  if (!evidence) {
    return;
  }
  nodes.drawerTitle.textContent = evidence.title;
  nodes.drawerBody.innerHTML = `
    <p class="evidenceLine">来源：${escapeHtml(evidence.source_label || sourceLabelFromUrl(evidence.url) || "未知")}</p>
    <p class="evidenceLine">来源分类：${escapeHtml(evidence.source_category || evidence.source_type || "未分类来源")}</p>
    <p class="evidenceLine">来源类型：${escapeHtml(evidence.source_type || "未知")}</p>
    <p class="evidenceLine">发布时间：${escapeHtml(evidence.published_at || "未知")}</p>
    <p class="evidenceLine">软文风险：${escapeHtml(evidence.ad_risk || "未标注")}</p>
    <p>${escapeHtml(evidence.usage || "")}</p>
    <p><a href="${escapeAttribute(evidence.url)}" target="_blank" rel="noreferrer">打开原文</a></p>
  `;
  nodes.drawer.classList.add("is-open");
  nodes.drawer.setAttribute("aria-hidden", "false");
}

function focusDeepCard(deepId) {
  const card = document.getElementById(deepId);
  if (!card) {
    return;
  }
  document.querySelectorAll(".deepCard").forEach((node) => node.classList.remove("is-focused"));
  card.classList.add("is-focused");
  card.scrollIntoView({ behavior: "smooth", block: "center" });
}

nodes.dateSelect.addEventListener("change", async (event) => {
  state.report = await fetchJson(`/api/reports/${event.target.value}`);
  renderReport();
});

nodes.searchInput.addEventListener("input", (event) => {
  state.activeQuery = event.target.value;
  renderReport();
});

nodes.categoryTabs.addEventListener("click", (event) => {
  const button = event.target.closest("[data-direction-id]");
  if (!button) {
    return;
  }
  state.activeDirection = button.dataset.directionId;
  renderCategoryTabs();
  renderReport();
});

document.addEventListener("click", (event) => {
  const metricButton = event.target.closest(".metricCard[data-direction-id]");
  if (metricButton) {
    state.activeDirection = metricButton.dataset.directionId;
    renderCategoryTabs();
    renderReport();
  }
  const deepButton = event.target.closest("[data-deep-id]");
  if (deepButton) {
    focusDeepCard(deepButton.dataset.deepId);
  }
  const evidenceButton = event.target.closest("[data-evidence-id]");
  if (evidenceButton) {
    openEvidence(evidenceButton.dataset.evidenceId);
  }
});

nodes.closeDrawer.addEventListener("click", () => {
  nodes.drawer.classList.remove("is-open");
  nodes.drawer.setAttribute("aria-hidden", "true");
});

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}

initAsciiMesh();
renderCategoryTabs();

loadInitialReport().catch((error) => {
  nodes.reportMeta.textContent = "暂时无法载入日报。";
  nodes.coreList.innerHTML = `<div class="emptyState">${escapeHtml(error.message)}</div>`;
});
