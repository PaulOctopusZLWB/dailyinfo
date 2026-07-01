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
  reportMeta: document.querySelector("#reportMeta"),
  summaryChips: document.querySelector("#summaryChips"),
  runStats: document.querySelector("#runStats"),
  coreList: document.querySelector("#coreList"),
  deepList: document.querySelector("#deepList"),
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
    icon: "A",
    keywords: [],
  },
  {
    id: "macro",
    label: "宏观AI前沿论点",
    shortLabel: "宏观AI前沿论点",
    icon: "M",
    keywords: ["LLM", "模型", "风险", "治理", "OpenAI", "AGI", "AI 时代", "agent"],
  },
  {
    id: "timeseries",
    label: "时序智能",
    shortLabel: "时序智能",
    icon: "T",
    keywords: ["时序", "预测", "TimeGPT", "Moirai", "TSMixer", "序列", "forecast"],
  },
  {
    id: "industrial",
    label: "工业软件+AI",
    shortLabel: "工业软件+AI",
    icon: "I",
    keywords: ["工业", "工控", "流程", "Siemens", "AVEVA", "AspenTech", "Seeq", "优化"],
  },
  {
    id: "agent",
    label: "AI Agent 生态",
    shortLabel: "AI Agent 生态",
    icon: "G",
    keywords: ["Agent", "agent", "GitHub", "SDK", "工具", "沙盒", "benchmark", "复现"],
  },
  {
    id: "twin",
    label: "数字孪生",
    shortLabel: "数字孪生",
    icon: "D",
    keywords: ["数字孪生", "孪生", "个人上下文", "人类", "仿真", "上下文系统"],
  },
  {
    id: "philosophy",
    label: "AI时代的泛哲学讨论",
    shortLabel: "泛哲学讨论",
    icon: "P",
    keywords: ["哲学", "自由意志", "责任", "主体", "人机", "意识", "边界"],
  },
];

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
  const totalCandidates = report.core_items.length + report.deep_items.length + report.evidence_items.length;
  document.title = `${report.date} 信息雷达`;
  nodes.reportMeta.textContent = `${report.date} · 已整理 ${totalCandidates} 条可读线索`;
  renderSummaryChips(report);
  renderCoreItems(report);
  renderDeepItems(report);
  renderRunStats(report);
  renderSources(report);
}

function renderSummaryChips(report) {
  const sourceCount = new Set(report.evidence_items.map((item) => item.source_type).filter(Boolean)).size;
  const directionCounts = buildDirectionCounts(report.core_items.concat(report.deep_items));
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
          <span class="metricIcon">${escapeHtml(metric.icon)}</span>
          <span class="metricCopy">
            <span>${escapeHtml(metric.shortLabel)}</span>
            <strong>${metric.count}</strong>
          </span>
        </button>
      `,
    )
    .join("");
  nodes.summaryChips.dataset.total = String(report.core_items.length + report.deep_items.length + report.evidence_items.length);
  nodes.summaryChips.dataset.sources = String(sourceCount);
}

function renderRunStats(report) {
  const stats = report.run_stats || {};
  const enabledSources = numberOrDash(stats.enabled_sources);
  const completedSources = numberOrDash(stats.completed_sources);
  const failedSources = Number(stats.failed_sources || 0);
  const fetchedItems = numberOrDash(stats.fetched_items);
  const withinWindow = numberOrDash(stats.within_window_items);
  const lookbackDays = Number(stats.lookback_days || 15);
  const dedupedItems = numberOrDash(stats.deduped_items);
  const renderedCandidates = numberOrDash(stats.rendered_candidates);
  const finalEvidence = Number(stats.final_evidence_items || report.evidence_items.length);
  const finalCore = Number(stats.final_core_items || report.core_items.length);

  const rows = [
    {
      label: "源状态",
      value: `${completedSources}/${enabledSources}`,
      detail: failedSources ? `${failedSources} 个失败` : "无失败源",
    },
    {
      label: "原始材料",
      value: fetchedItems,
      detail: "抓取与导入总量",
    },
    {
      label: `${lookbackDays} 天窗口`,
      value: withinWindow,
      detail: "按发布时间筛选",
    },
    {
      label: "去重后",
      value: dedupedItems,
      detail: "URL / 标题 / 内容聚类",
    },
    {
      label: "候选池",
      value: renderedCandidates,
      detail: "进入加工候选包",
    },
    {
      label: "晨报",
      value: `${finalCore}/${finalEvidence}`,
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
    return;
  }
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
  const items = filterItems(report.deep_items, ["title", "body", "recommendation_reason", "risk"]);
  if (!items.length) {
    nodes.deepList.innerHTML = `<div class="emptyState">没有匹配的深度阅读卡。</div>`;
    return;
  }
  nodes.deepList.innerHTML = items
    .map((item) => {
      const matchedDirection = bestDirectionForItem(item);
      return `
      <article class="card deepCard" id="${escapeHtml(item.id)}">
        <div class="deepTop">
          <span class="deepBadge">${escapeHtml(item.id)}</span>
          <div>
            <div class="cardMeta">${escapeHtml(matchedDirection.shortLabel)}</div>
            <h3>${escapeHtml(item.title)}</h3>
          </div>
        </div>
        <p class="abstract">${escapeHtml(item.body)}</p>
        <p class="reason">${escapeHtml(item.recommendation_reason)}</p>
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
          <span class="sourceCount">${entry.count}</span>
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
        <span class="categoryGlyph">${escapeHtml(direction.icon)}</span>
        <span>${escapeHtml(direction.label)}</span>
      </button>
    `,
  ).join("");
}

function buildDirectionCounts(items) {
  const counts = new Map();
  DIRECTIONS.filter((direction) => direction.id !== "all").forEach((direction) => {
    counts.set(direction.id, 0);
  });
  items.forEach((item) => {
    bestDirectionsForItem(item).forEach((direction) => {
      counts.set(direction.id, (counts.get(direction.id) || 0) + 1);
    });
  });
  return counts;
}

function bestDirectionForItem(item) {
  return bestDirectionsForItem(item)[0] || DIRECTIONS[1];
}

function bestDirectionsForItem(item) {
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

function numberOrDash(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return String(value);
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
