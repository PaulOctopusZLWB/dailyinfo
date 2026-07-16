const VISIT_TIMEOUT_MS = 30 * 60 * 1000;
const USER_IDLE_TIMEOUT_MS = 60 * 1000;
const HEARTBEAT_INTERVAL_MS = 15 * 1000;
const initialVisit = getOrCreateVisit();

const state = {
  report: null,
  reports: [],
  activeView: "core",
  activeQuery: "",
  activeDirection: "all",
  activeStrength: "all",
  sessionId: getOrCreateSessionId(),
  visitId: initialVisit.visitId,
  lastInteractionAt: initialVisit.lastActivityAt,
  lastVisitPersistedAt: initialVisit.lastActivityAt,
  eventQueue: [],
  visibleItems: new Map(),
  itemObserver: null,
  lastHeartbeatAt: Date.now(),
  searchTimer: 0,
  selectionTimer: 0,
  currentDeepContext: null,
  fx: null,
};

const nodes = {
  dateSelect: document.querySelector("#dateSelect"),
  prevDate: document.querySelector("#prevDate"),
  nextDate: document.querySelector("#nextDate"),
  morningTitle: document.querySelector("#morningTitle"),
  themeToggle: document.querySelector("#themeToggle"),
  viewTabs: document.querySelector("#viewTabs"),
  statsLine: document.querySelector("#statsLine"),
  categoryTabs: document.querySelector("#categoryTabs"),
  strengthFilters: document.querySelector("#strengthFilters"),
  searchInput: document.querySelector("#searchInput"),
  coreView: document.querySelector("#coreView"),
  deepView: document.querySelector("#deepView"),
  evidenceView: document.querySelector("#evidenceView"),
  archiveView: document.querySelector("#archiveView"),
  coreCount: document.querySelector("#coreCount"),
  deepCount: document.querySelector("#deepCount"),
  evidenceCount: document.querySelector("#evidenceCount"),
  archiveCount: document.querySelector("#archiveCount"),
  coreList: document.querySelector("#coreList"),
  deepList: document.querySelector("#deepList"),
  evidenceList: document.querySelector("#evidenceList"),
  archiveList: document.querySelector("#archiveList"),
  drawerBackdrop: document.querySelector("#drawerBackdrop"),
  deepDrawer: document.querySelector("#deepDrawer"),
  drawerMeta: document.querySelector("#drawerMeta"),
  drawerTitle: document.querySelector("#drawerTitle"),
  drawerBody: document.querySelector("#drawerBody"),
  closeDrawer: document.querySelector("#closeDrawer"),
  entrance: document.querySelector("#entrance"),
  ambientCanvas: document.querySelector("#ambientCanvas"),
  cursorDot: document.querySelector("#cursorDot"),
  cursorRing: document.querySelector("#cursorRing"),
};

const DIRECTIONS = [
  { id: "all", code: "ALL", label: "全部", keywords: [] },
  { id: "macro", code: "MA", label: "宏观 AI 前沿", keywords: ["LLM", "模型", "风险", "治理", "OpenAI", "AGI", "agent"] },
  { id: "timeseries", code: "TS", label: "时序前沿", keywords: ["时序", "预测", "TimeGPT", "Moirai", "TSMixer", "forecast"] },
  { id: "industrial", code: "IN", label: "工业控制 × AI", keywords: ["工业", "工控", "流程", "Siemens", "AVEVA", "AspenTech", "Seeq", "优化"] },
  { id: "agent", code: "AG", label: "Agent 方法论", keywords: ["Agent", "agent", "GitHub", "SDK", "工具", "沙盒", "benchmark", "复现"] },
  { id: "twin", code: "TW", label: "数字孪生", keywords: ["数字孪生", "孪生", "个人上下文", "仿真", "上下文系统"] },
  { id: "philosophy", code: "PH", label: "泛哲学", keywords: ["哲学", "自由意志", "责任", "主体", "人机", "意识", "边界"] },
  {
    id: "dynamical_systems",
    code: "DS",
    label: "动力系统重建",
    keywords: [
      "动力系统重建",
      "动力学重建",
      "系统辨识",
      "状态空间重建",
      "隐状态",
      "部分观测",
      "随机动力学",
      "非线性动力学",
      "混沌动力学",
      "吸引子",
      "dynamical system reconstruction",
      "system identification",
      "latent dynamics",
      "state-space reconstruction",
      "neural ode",
      "neural sde",
      "koopman",
      "sindy",
      "reservoir computing",
    ],
  },
];

const STRENGTHS = [
  { id: "all", label: "全部强度" },
  { id: "high", label: "高" },
  { id: "medium", label: "中" },
  { id: "low", label: "低" },
];

const VIEWS = [
  { id: "core", label: "核心阅读" },
  { id: "deep", label: "深度阅读" },
  { id: "evidence", label: "证据回溯" },
  { id: "archive", label: "归档" },
];

init();

function init() {
  initTheme();
  initEntrance();
  initAmbientFx();
  bindEvents();
  loadInitialReport().catch((error) => renderLoadError(error));
}

function bindEvents() {
  nodes.dateSelect.addEventListener("change", () => {
    loadReportByDate(nodes.dateSelect.value).catch((error) => renderLoadError(error));
  });

  nodes.prevDate.addEventListener("click", () => shiftReportDate(1));
  nodes.nextDate.addEventListener("click", () => shiftReportDate(-1));

  nodes.themeToggle.addEventListener("click", toggleTheme);

  nodes.searchInput.addEventListener("input", (event) => {
    state.activeQuery = event.target.value;
    renderReport();
    window.clearTimeout(state.searchTimer);
    state.searchTimer = window.setTimeout(() => {
      if (state.activeQuery.trim()) {
        trackEvent("search", { query: state.activeQuery.trim().slice(0, 80) });
      }
    }, 450);
  });

  nodes.viewTabs.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-view-id]");
    if (!button) return;
    state.activeView = button.dataset.viewId;
    if (state.activeView !== "deep") {
      state.activeStrength = "all";
    }
    renderReport();
    trackEvent("filter", { filter_type: "view", filter_value: state.activeView });
  });

  nodes.categoryTabs.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-direction-id]");
    if (!button) return;
    state.activeDirection = button.dataset.directionId;
    renderReport();
    trackEvent("filter", { filter_type: "direction", filter_value: state.activeDirection });
  });

  nodes.strengthFilters.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-strength-id]");
    if (!button) return;
    state.activeStrength = button.dataset.strengthId;
    renderReport();
    trackEvent("filter", { filter_type: "strength", filter_value: state.activeStrength });
  });

  nodes.coreList.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-deep-id]");
    if (button) openDeep(button.dataset.deepId);
  });

  nodes.deepList.addEventListener("click", (event) => {
    const card = event.target.closest("[data-deep-id]");
    if (card) openDeep(card.dataset.deepId);
  });

  nodes.evidenceList.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-evidence-id]");
    if (!link) return;
    trackSourceOpen(link);
  });

  nodes.drawerBody.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-evidence-id]");
    if (!link) return;
    trackSourceOpen(link);
  });

  nodes.archiveList.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-report-date]");
    if (!button) return;
    loadReportByDate(button.dataset.reportDate).catch((error) => renderLoadError(error));
  });

  nodes.drawerBackdrop.addEventListener("click", (event) => {
    if (event.target === nodes.drawerBackdrop) closeDrawer();
  });
  nodes.closeDrawer.addEventListener("click", closeDrawer);
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeDrawer();
  });

  document.addEventListener("selectionchange", () => {
    window.clearTimeout(state.selectionTimer);
    state.selectionTimer = window.setTimeout(trackSelection, 550);
  });

  ["pointerdown", "keydown", "scroll", "touchstart"].forEach((eventName) => {
    window.addEventListener(eventName, markUserActivity, { passive: true });
  });

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      state.lastHeartbeatAt = Date.now();
      return;
    }
    flushVisibleItemDurations();
    flushHeartbeat();
    flushAnalyticsEvents(true);
  });

  window.addEventListener("beforeunload", () => {
    flushVisibleItemDurations();
    flushHeartbeat();
    flushAnalyticsEvents(true);
  });

  window.setInterval(flushHeartbeat, HEARTBEAT_INTERVAL_MS);
}

async function loadInitialReport() {
  const [reports, latest] = await Promise.all([fetchJson("/api/reports"), fetchJson("/api/reports/latest")]);
  state.reports = reports;
  state.report = latest;
  renderDateSelect();
  renderReport();
  trackEvent("page_view", { report_date: latest.date });
}

async function loadReportByDate(date) {
  const report = await fetchJson(`/api/reports/${encodeURIComponent(date)}`);
  state.report = report;
  state.activeView = "core";
  state.activeDirection = "all";
  state.activeStrength = "all";
  state.activeQuery = "";
  nodes.searchInput.value = "";
  renderDateSelect();
  renderReport();
  trackEvent("page_view", { report_date: report.date });
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${url}`);
  }
  return response.json();
}

function renderDateSelect() {
  nodes.dateSelect.innerHTML = state.reports
    .map((report) => `<option value="${escapeHtml(report.date)}">${escapeHtml(report.date)}</option>`)
    .join("");
  if (state.report) {
    nodes.dateSelect.value = state.report.date;
    const index = currentReportIndex();
    nodes.prevDate.disabled = index < 0 || index >= state.reports.length - 1;
    nodes.nextDate.disabled = index <= 0;
  }
}

function renderReport() {
  if (!state.report) return;
  const report = state.report;
  const counts = getVisibleCounts(report);
  const layerCounts = getLayerCounts(report);

  document.title = `${report.date} 信息雷达`;
  nodes.morningTitle.textContent = `${formatWeekday(report.date)} · 晨报`;
  nodes.statsLine.textContent = formatStatsLine(report, layerCounts);
  nodes.coreCount.textContent = `${formatNumber(counts.core)} 条`;
  nodes.deepCount.textContent = `${formatNumber(counts.deep)} 张`;
  nodes.evidenceCount.textContent = `${formatNumber(counts.evidence)} 条`;
  nodes.archiveCount.textContent = `${formatNumber(state.reports.length)} 天`;

  renderTabs(layerCounts);
  renderFilters();
  renderViews();
  renderCoreGroups(report);
  renderDeepList(report);
  renderEvidenceList(report);
  renderArchiveList();
  setupItemTracking();
}

function renderTabs(layerCounts) {
  const counts = {
    core: layerCounts.core,
    deep: layerCounts.deep,
    evidence: layerCounts.evidence,
    archive: state.reports.length,
  };
  nodes.viewTabs.innerHTML = VIEWS.map((view) => {
    const active = state.activeView === view.id;
    return `
      <button class="${active ? "is-active" : ""}" type="button" data-view-id="${escapeHtml(view.id)}" aria-pressed="${active ? "true" : "false"}">
        ${escapeHtml(view.label)} ${formatNumber(counts[view.id] || 0)}
      </button>
    `;
  }).join("");
}

function renderFilters() {
  const directionCounts = directionCountsForActiveView();
  nodes.categoryTabs.innerHTML = DIRECTIONS.map((direction) => {
    const active = state.activeDirection === direction.id;
    const count = direction.id === "all" ? activeViewItems().length : directionCounts.get(direction.id) || 0;
    const label = direction.id === "all" ? `全部 ${formatNumber(count)}` : `${direction.code} ${direction.label} ${formatNumber(count)}`;
    return `
      <button class="${active ? "is-active" : ""}" type="button" data-direction-id="${escapeHtml(direction.id)}" aria-pressed="${active ? "true" : "false"}" title="${escapeHtml(label)}">
        ${escapeHtml(label)}
      </button>
    `;
  }).join("");

  nodes.strengthFilters.hidden = state.activeView !== "deep";
  nodes.strengthFilters.innerHTML = STRENGTHS.map((strength) => {
    const active = state.activeStrength === strength.id;
    return `
      <button class="${active ? "is-active" : ""}" type="button" data-strength-id="${escapeHtml(strength.id)}" aria-pressed="${active ? "true" : "false"}">
        ${escapeHtml(strength.label)}
      </button>
    `;
  }).join("");
}

function shiftReportDate(offset) {
  const index = currentReportIndex();
  if (index < 0) return;
  const next = state.reports[index + offset];
  if (!next) return;
  loadReportByDate(next.date).catch((error) => renderLoadError(error));
}

function currentReportIndex() {
  if (!state.report) return -1;
  return state.reports.findIndex((report) => report.date === state.report.date);
}

function activeViewItems() {
  if (!state.report) return [];
  if (state.activeView === "deep") return state.report.deep_items || [];
  if (state.activeView === "evidence") return state.report.evidence_items || [];
  if (state.activeView === "archive") return state.reports;
  return state.report.core_items || [];
}

function directionCountsForActiveView() {
  const counts = new Map();
  DIRECTIONS.filter((direction) => direction.id !== "all").forEach((direction) => counts.set(direction.id, 0));
  activeViewItems().forEach((item) => {
    if (!item || item.date) return;
    const direction = bestDirectionForItem(item);
    counts.set(direction.id, (counts.get(direction.id) || 0) + 1);
  });
  return counts;
}

function renderViews() {
  const views = {
    core: nodes.coreView,
    deep: nodes.deepView,
    evidence: nodes.evidenceView,
    archive: nodes.archiveView,
  };
  Object.entries(views).forEach(([id, node]) => {
    node.hidden = state.activeView !== id;
  });
}

function renderCoreGroups(report) {
  const items = filterItems(report.core_items || [], ["title", "abstract", "recommendation_reason"]);
  if (!items.length) {
    nodes.coreList.innerHTML = `<div class="emptyState">当前筛选下无核心判断</div>`;
    return;
  }

  const grouped = new Map();
  items.forEach((item) => {
    const direction = bestDirectionForItem(item);
    if (!grouped.has(direction.id)) grouped.set(direction.id, { direction, items: [] });
    grouped.get(direction.id).items.push(item);
  });

  nodes.coreList.innerHTML = DIRECTIONS.filter((direction) => direction.id !== "all" && grouped.has(direction.id))
    .map((direction) => {
      const group = grouped.get(direction.id);
      return `
        <section class="directionGroup">
          <div class="groupHead">
            <span class="code">${escapeHtml(direction.code)}</span>
            <span class="label">${escapeHtml(direction.label)}</span>
            <span class="count">${formatNumber(group.items.length)}</span>
          </div>
          <div class="coreGrid">
            ${group.items.map((item) => renderCoreCard(report, item, direction)).join("")}
          </div>
        </section>
      `;
    })
    .join("");
}

function renderCoreCard(report, item, direction) {
  const links = (item.deep_ids || [])
    .slice(0, 3)
    .map((deepId) => {
      const deep = findDeep(report, deepId);
      const title = deep ? deep.title : deepId;
      return `<button class="deepLink" type="button" data-deep-id="${escapeHtml(deepId)}" title="${escapeHtml(title)}">${escapeHtml(deepId)}</button>`;
    })
    .join("");
  return `
    <article class="card coreCard" id="${escapeHtml(item.id || "")}">
      <span class="trackTarget" data-track-layer="core" data-track-id="${escapeHtml(item.id || "")}" data-track-direction="${escapeHtml(direction.id)}" data-track-source-category=""></span>
      <div class="cardTitleRow">
        <span class="coreId">${escapeHtml(item.id || `C${item.number || ""}`)}</span>
        <h3>${escapeHtml(item.title || "未命名判断")}</h3>
      </div>
      <p class="abstract">${escapeHtml(item.abstract || "")}</p>
      <p class="reason"><span class="sectionLabel">行动</span>${escapeHtml(item.recommendation_reason || "")}</p>
      <div class="deepLinks">
        <span class="sectionLabel">深读</span>
        ${links || `<span class="cardMeta">暂无关联深读</span>`}
      </div>
    </article>
  `;
}

function renderDeepList(report) {
  const items = filterItems(report.deep_items || [], [
    "title",
    "body",
    "core_argument",
    "impact",
    "recommendation_reason",
    "risk",
    "source_category",
  ]);
  if (!items.length) {
    nodes.deepList.innerHTML = `<div class="emptyState">当前筛选下无深读卡</div>`;
    return;
  }
  nodes.deepList.innerHTML = items.map((item) => renderDeepCard(report, item)).join("");
}

function renderDeepCard(report, item) {
  const direction = bestDirectionForItem(item);
  const sourceCategory = item.source_category || sourceCategoryForDeepItem(report, item);
  const strength = normalizeStrength(item.evidence_strength);
  return `
    <article class="card deepCard" id="${escapeHtml(item.id || "")}" data-deep-id="${escapeHtml(item.id || "")}" data-cursor="1">
      <span class="trackTarget" data-track-layer="deep" data-track-id="${escapeHtml(item.id || "")}" data-track-direction="${escapeHtml(direction.id)}" data-track-source-category="${escapeHtml(sourceCategory)}"></span>
      <div class="deepTop">
        <span class="deepId">${escapeHtml(item.id || "")}</span>
        <span class="strengthBadge ${escapeHtml(strength.className)}">${escapeHtml(strength.label)}</span>
        <span class="sourceCategory">${escapeHtml(sourceCategory)}</span>
        <span class="cardMeta">${escapeHtml(direction.code)}</span>
      </div>
      <h3>${escapeHtml(item.title || "未命名深读卡")}</h3>
      <p>${escapeHtml(item.core_argument || item.body || "")}</p>
    </article>
  `;
}

function renderEvidenceList(report) {
  const items = visibleEvidenceItems(report);
  if (!items.length) {
    nodes.evidenceList.innerHTML = `<div class="emptyState">当前筛选下无证据条目</div>`;
    return;
  }
  nodes.evidenceList.innerHTML = items
    .map((item) => {
      const direction = bestDirectionForItem(item);
      const meta = [item.source_label || sourceLabelFromUrl(item.url), item.source_category || item.source_type, direction.code]
        .filter(Boolean)
        .join(" / ");
      const risk = item.ad_risk ? ` · ${item.ad_risk}` : "";
      return `
        <a class="evidenceRow" href="${escapeAttribute(item.url || "#")}" target="_blank" rel="noopener" data-evidence-id="${escapeHtml(item.id || "")}" data-source-category="${escapeHtml(item.source_category || "")}">
          <span class="evId">${escapeHtml(item.id || "")}</span>
          <span>
            <span class="evTitle">${escapeHtml(item.title || item.url || "未命名来源")}</span>
            <span class="evMeta">${escapeHtml(meta)}<span class="riskText">${escapeHtml(risk)}</span></span>
          </span>
          <span class="evDate">${escapeHtml(formatShortDate(item.published_at))}</span>
        </a>
      `;
    })
    .join("");
}

function renderArchiveList() {
  if (!state.reports.length) {
    nodes.archiveList.innerHTML = `<div class="emptyState">暂无归档</div>`;
    return;
  }
  nodes.archiveList.innerHTML = state.reports
    .map(
      (report) => `
        <button class="archiveRow" type="button" data-report-date="${escapeHtml(report.date)}">
          <span class="archiveDate">${escapeHtml(report.date)}</span>
          <span class="archiveTitle">${escapeHtml(report.title || `${report.date} 信息雷达晨报`)}</span>
          <span class="archiveMeta">${formatNumber(report.core_count || 0)} / ${formatNumber(report.deep_count || 0)} / ${formatNumber(report.evidence_count || 0)}</span>
          <span class="archiveAction">阅读 -></span>
        </button>
      `,
    )
    .join("");
}

function openDeep(deepId) {
  const report = state.report;
  const item = findDeep(report, deepId);
  if (!item) return;
  const evidence = findEvidence(report, item.evidence_id);
  const direction = bestDirectionForItem(item);
  const sourceCategory = item.source_category || sourceCategoryForDeepItem(report, item);
  const strength = normalizeStrength(item.evidence_strength);

  nodes.drawerMeta.textContent = `${item.id || "DEEP"} · ${direction.code} · ${strength.label} · ${sourceCategory}`;
  nodes.drawerTitle.textContent = item.title || "未命名深读卡";
  nodes.drawerBody.innerHTML = `
    <section class="drawerBlock primary">
      <h3>核心论述</h3>
      <p>${escapeHtml(item.core_argument || item.body || "")}</p>
    </section>
    <section class="drawerBlock">
      <h3>对我们的影响</h3>
      <p>${escapeHtml(item.impact || "")}</p>
    </section>
    <section class="drawerBlock">
      <h3>推荐理由</h3>
      <p>${escapeHtml(item.recommendation_reason || "")}</p>
    </section>
    <section class="drawerBlock warn">
      <h3>风险提示</h3>
      <p>${escapeHtml(item.risk || "未标注风险")}</p>
    </section>
    ${renderEvidenceBox(evidence, item.id, direction.id)}
  `;

  nodes.drawerBackdrop.hidden = false;
  nodes.deepDrawer.setAttribute("aria-hidden", "false");
  state.currentDeepContext = {
    item_layer: "deep",
    item_id: item.id,
    direction_id: direction.id,
    source_category: sourceCategory,
  };
  trackEvent("deep_open", {
    item_layer: "deep",
    item_id: item.id,
    direction_id: direction.id,
    source_category: sourceCategory,
  });
}

function renderEvidenceBox(evidence, contextItemId = "", directionId = "") {
  if (!evidence) {
    return `
      <section class="evidenceBox">
        <div class="evidenceBoxTop">
          <span class="evId">E?</span>
          <span class="sectionLabel">证据回溯</span>
        </div>
        <div class="evidenceBoxTitle">未找到关联证据</div>
      </section>
    `;
  }
  const sourceLine = [evidence.source_label || sourceLabelFromUrl(evidence.url), evidence.source_category || evidence.source_type]
    .filter(Boolean)
    .join(" / ");
  return `
    <section class="evidenceBox">
      <div class="evidenceBoxTop">
        <span class="evId">${escapeHtml(evidence.id || "")}</span>
        <span class="sectionLabel">证据回溯</span>
      </div>
      <div class="evidenceBoxTitle">${escapeHtml(evidence.title || evidence.url || "未命名来源")}</div>
      <div class="evidenceBoxMeta">${escapeHtml(sourceLine)} · ${escapeHtml(formatShortDate(evidence.published_at))}</div>
      <p class="abstract">${escapeHtml(evidence.usage || "")}</p>
      <p class="abstract riskText">${escapeHtml(evidence.ad_risk || "")}</p>
      <a class="sourceButton" href="${escapeAttribute(evidence.url || "#")}" target="_blank" rel="noopener" data-evidence-id="${escapeHtml(evidence.id || "")}" data-context-item-id="${escapeHtml(contextItemId)}" data-direction-id="${escapeHtml(directionId)}" data-source-category="${escapeHtml(evidence.source_category || "")}">打开原文 ↗</a>
    </section>
  `;
}

function closeDrawer() {
  nodes.drawerBackdrop.hidden = true;
  nodes.deepDrawer.setAttribute("aria-hidden", "true");
}

function renderLoadError(error) {
  const message = error && error.message ? error.message : "未知错误";
  nodes.coreList.innerHTML = `<div class="errorState">晨报加载失败：${escapeHtml(message)}</div>`;
}

function filterItems(items, fields) {
  const query = state.activeQuery.trim().toLowerCase();
  return items.filter((item) => {
    const matchesQuery = !query || fields.some((field) => String(item[field] || "").toLowerCase().includes(query));
    const matchesDirection = state.activeDirection === "all" || itemMatchesDirection(item, state.activeDirection);
    const matchesStrength =
      state.activeStrength === "all" ||
      !Object.prototype.hasOwnProperty.call(item, "evidence_strength") ||
      normalizeStrength(item.evidence_strength).id === state.activeStrength;
    return matchesQuery && matchesDirection && matchesStrength;
  });
}

function trackSourceOpen(link) {
  trackEvent("source_open", {
    item_layer: "evidence",
    item_id: link.dataset.evidenceId,
    context_item_id: link.dataset.contextItemId || "",
    direction_id: link.dataset.directionId || "",
    source_category: link.dataset.sourceCategory || "",
  });
}

function visibleEvidenceItems(report) {
  const query = state.activeQuery.trim().toLowerCase();
  return (report.evidence_items || []).filter((item) => {
    const matchesQuery =
      !query ||
      ["title", "source_label", "source_type", "source_category", "usage", "url", "ad_risk"].some((field) =>
        String(item[field] || "").toLowerCase().includes(query),
      );
    const matchesDirection = state.activeDirection === "all" || itemMatchesDirection(item, state.activeDirection);
    return matchesQuery && matchesDirection;
  });
}

function getVisibleCounts(report) {
  return {
    core: filterItems(report.core_items || [], ["title", "abstract", "recommendation_reason"]).length,
    deep: filterItems(report.deep_items || [], ["title", "body", "core_argument", "impact", "recommendation_reason", "risk"]).length,
    evidence: visibleEvidenceItems(report).length,
  };
}

function getLayerCounts(report) {
  const stats = report.run_stats || {};
  const core = statNumber(stats.final_core_items) ?? (report.core_items || []).length;
  const deep = statNumber(stats.final_deep_items) ?? (report.deep_items || []).length;
  const evidence = statNumber(stats.final_evidence_items) ?? (report.evidence_items || []).length;
  return { core, deep, evidence, total: core + deep + evidence };
}

function formatStatsLine(report, counts) {
  const stats = report.run_stats || {};
  const totalSources = statNumber(stats.total_sources) ?? statNumber(stats.enabled_sources);
  const fetched = statNumber(stats.fetched_items);
  const deduped = statNumber(stats.deduped_items);
  const failed = statNumber(stats.failed_sources);
  return [
    totalSources === null ? "" : `${formatNumber(totalSources)} 源`,
    fetched === null ? "" : `${formatNumber(fetched)} 抓取`,
    deduped === null ? "" : `${formatNumber(deduped)} 去重`,
    `${formatNumber(counts.core)} 核心`,
    failed === null ? "" : `${formatNumber(failed)} 失败`,
  ]
    .filter(Boolean)
    .join(" / ");
}

function findDeep(report, deepId) {
  return (report.deep_items || []).find((item) => item.id === deepId);
}

function findEvidence(report, evidenceId) {
  return (report.evidence_items || []).find((item) => item.id === evidenceId);
}

function bestDirectionForItem(item) {
  return bestDirectionsForItem(item)[0] || DIRECTIONS[1];
}

function bestDirectionsForItem(item) {
  if (item.direction_id) {
    const direction = directionById(item.direction_id);
    if (direction) return [direction];
  }
  if (item.direction_label) {
    const direction = directionByLabel(item.direction_label);
    if (direction) return [direction];
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
    "数据驱动的动力系统重建与系统辨识": "dynamical_systems",
    "动力系统重建与系统辨识": "dynamical_systems",
    "动力系统重建": "dynamical_systems",
  };
  return directionById(aliases[normalizeDirectionLabel(label)]);
}

function normalizeDirectionLabel(label) {
  return String(label || "")
    .toLowerCase()
    .replace(/[\s+＋、，,·/／\-—_×]/g, "");
}

function itemMatchesDirection(item, directionId) {
  return bestDirectionsForItem(item).some((direction) => direction.id === directionId);
}

function itemText(item) {
  return [
    item.title,
    item.abstract,
    item.body,
    item.core_argument,
    item.impact,
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

function sourceCategoryForDeepItem(report, deepItem) {
  const evidence = findEvidence(report, deepItem.evidence_id);
  if (!evidence) return deepItem.source_category || "未分类来源";
  return evidence.source_category || evidence.source_type || "未分类来源";
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

function normalizeStrength(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (["高", "high", "strong"].includes(raw)) return { id: "high", label: "高", className: "high" };
  if (["中", "medium", "mid"].includes(raw)) return { id: "medium", label: "中", className: "medium" };
  if (["低", "low", "weak"].includes(raw)) return { id: "low", label: "低", className: "low" };
  return { id: "low", label: "低", className: "low" };
}

function statNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function formatNumber(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return numeric.toLocaleString("zh-CN");
}

function formatShortDate(value) {
  if (!value || value === "未知") return "—";
  const date = new Date(value);
  if (!Number.isNaN(date.getTime())) {
    return `${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  }
  const match = String(value).match(/\d{4}-(\d{2})-(\d{2})/);
  return match ? `${match[1]}-${match[2]}` : "—";
}

function formatWeekday(value) {
  const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return "晨报";
  const date = new Date(`${match[1]}-${match[2]}-${match[3]}T00:00:00+08:00`);
  if (Number.isNaN(date.getTime())) return "晨报";
  return `周${["日", "一", "二", "三", "四", "五", "六"][date.getDay()]}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replace(/`/g, "&#96;");
}

function initTheme() {
  let theme = "dark";
  try {
    theme = window.localStorage.getItem("inforadar-theme") || "dark";
  } catch {
    theme = "dark";
  }
  document.body.dataset.theme = theme;
  nodes.themeToggle.textContent = theme === "light" ? "深色" : "浅色";
}

function toggleTheme() {
  const next = document.body.dataset.theme === "light" ? "dark" : "light";
  document.body.dataset.theme = next;
  nodes.themeToggle.textContent = next === "light" ? "深色" : "浅色";
  try {
    window.localStorage.setItem("inforadar-theme", next);
  } catch {
    // Ignore storage errors in private contexts.
  }
}

function initEntrance() {
  const skip = () => nodes.entrance.classList.add("is-hidden");
  nodes.entrance.addEventListener("click", skip);
  window.setTimeout(skip, 3150);
}

function trackSelection() {
  const selection = window.getSelection ? window.getSelection() : null;
  const selected = String(selection || "").trim();
  if (!selected || selected.length < 8) return;
  const anchorElement = selection?.anchorNode?.nodeType === 1 ? selection.anchorNode : selection?.anchorNode?.parentElement;
  const cardTarget = anchorElement?.closest?.(".card")?.querySelector?.(".trackTarget");
  const itemContext = cardTarget
    ? {
        item_layer: cardTarget.dataset.trackLayer || "",
        item_id: cardTarget.dataset.trackId || "",
        direction_id: cardTarget.dataset.trackDirection || "",
        source_category: cardTarget.dataset.trackSourceCategory || "",
      }
    : state.currentDeepContext || {};
  trackEvent("text_select", {
    ...itemContext,
    selected_text_excerpt: selected.slice(0, 120),
    selected_text_length: selected.length,
  });
}

function getOrCreateSessionId() {
  const key = "info_radar_session_id";
  try {
    const existing = window.localStorage.getItem(key);
    if (existing) return existing;
    const created = `s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
    window.localStorage.setItem(key, created);
    return created;
  } catch {
    return `s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
  }
}

function createAnonymousId(prefix) {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

function getOrCreateVisit() {
  const key = "info_radar_visit";
  const now = Date.now();
  try {
    const stored = JSON.parse(window.localStorage.getItem(key) || "null");
    if (stored?.visitId && now - Number(stored.lastActivityAt || 0) < VISIT_TIMEOUT_MS) {
      return { visitId: stored.visitId, lastActivityAt: now };
    }
  } catch {
    // Fall through to a fresh anonymous visit.
  }
  const visit = { visitId: createAnonymousId("v"), lastActivityAt: now };
  persistVisit(visit);
  return visit;
}

function persistVisit(visit) {
  try {
    window.localStorage.setItem("info_radar_visit", JSON.stringify(visit));
  } catch {
    // Analytics remains best-effort when localStorage is unavailable.
  }
}

function markUserActivity() {
  const now = Date.now();
  if (now - state.lastInteractionAt >= VISIT_TIMEOUT_MS) {
    state.visitId = createAnonymousId("v");
  }
  state.lastInteractionAt = now;
  if (now - state.lastVisitPersistedAt >= 5000) {
    state.lastVisitPersistedAt = now;
    persistVisit({ visitId: state.visitId, lastActivityAt: now });
  }
}

function trackEvent(eventType, payload = {}) {
  if (!state.report) return;
  const event = {
    event_type: eventType,
    event_id: createAnonymousId("e"),
    session_id: state.sessionId,
    visit_id: state.visitId,
    report_date: state.report.date,
    created_at: new Date().toISOString(),
    scroll_depth: currentScrollDepth(),
    ...payload,
  };
  state.eventQueue.push(event);
  if (state.eventQueue.length >= 8) flushAnalyticsEvents();
}

function flushAnalyticsEvents(useBeacon = false) {
  if (!state.eventQueue.length) return;
  const events = state.eventQueue.splice(0, state.eventQueue.length);
  const body = JSON.stringify({ events });
  if (useBeacon && navigator.sendBeacon) {
    navigator.sendBeacon("/api/analytics/events", new Blob([body], { type: "application/json" }));
    return;
  }
  fetch("/api/analytics/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
  }).catch(() => {
    state.eventQueue.unshift(...events.slice(-20));
  });
}

function flushHeartbeat() {
  const now = Date.now();
  const duration = now - state.lastHeartbeatAt;
  state.lastHeartbeatAt = now;
  if (document.hidden || now - state.lastInteractionAt > USER_IDLE_TIMEOUT_MS || duration < 1000) return;
  trackEvent("page_heartbeat", { duration_ms: Math.min(duration, HEARTBEAT_INTERVAL_MS) });
}

function setupItemTracking() {
  if (state.itemObserver) {
    state.itemObserver.disconnect();
    state.itemObserver = null;
  }
  flushVisibleItemDurations();
  if (!("IntersectionObserver" in window)) return;
  state.itemObserver = new IntersectionObserver(handleItemIntersections, { threshold: [0, 0.35, 0.7] });
  document.querySelectorAll(".trackTarget").forEach((target) => {
    const card = target.closest(".card");
    if (card) state.itemObserver.observe(card);
  });
}

function handleItemIntersections(entries) {
  const now = Date.now();
  entries.forEach((entry) => {
    const target = entry.target.querySelector(".trackTarget");
    if (!target) return;
    const itemKey = `${target.dataset.trackLayer}:${target.dataset.trackId}`;
    if (entry.isIntersecting && entry.intersectionRatio >= 0.35) {
      if (!state.visibleItems.has(itemKey)) {
        state.visibleItems.set(itemKey, {
          startedAt: now,
          item_layer: target.dataset.trackLayer,
          item_id: target.dataset.trackId,
          direction_id: target.dataset.trackDirection,
          source_category: target.dataset.trackSourceCategory,
        });
      }
      return;
    }
    flushVisibleItemDuration(itemKey, now);
  });
}

function flushVisibleItemDurations() {
  const now = Date.now();
  Array.from(state.visibleItems.keys()).forEach((itemKey) => flushVisibleItemDuration(itemKey, now));
}

function flushVisibleItemDuration(itemKey, now = Date.now()) {
  const visible = state.visibleItems.get(itemKey);
  if (!visible) return;
  state.visibleItems.delete(itemKey);
  const duration = now - visible.startedAt;
  if (duration < 900) return;
  trackEvent("item_view", {
    item_layer: visible.item_layer,
    item_id: visible.item_id,
    direction_id: visible.direction_id,
    source_category: visible.source_category,
    duration_ms: duration,
  });
}

function currentScrollDepth() {
  const scrollable = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
  return Math.round(Math.min(100, Math.max(0, window.scrollY / scrollable) * 100));
}

function initAmbientFx() {
  const canvas = nodes.ambientCanvas;
  const dot = nodes.cursorDot;
  const ring = nodes.cursorRing;
  const context = canvas ? canvas.getContext("2d") : null;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = window.matchMedia("(pointer:fine)").matches;
  document.body.dataset.cfx = finePointer ? "1" : "0";
  if (!finePointer) {
    dot.style.display = "none";
    ring.style.display = "none";
  }

  const fx = {
    mx: -500,
    my: -500,
    rx: -500,
    ry: -500,
    rs: 1,
    hover: false,
    seen: false,
    parts: [],
    width: 0,
    height: 0,
    frame: 0,
    gold: "201,169,110",
  };
  state.fx = fx;

  const makePart = (anywhere) => {
    const depth = 0.25 + Math.random() * 0.75;
    return {
      x: anywhere ? Math.random() * fx.width : -12,
      y: Math.random() * fx.height,
      r: 0.5 + depth * 1.4,
      s: 0.1 + depth * 0.5,
      a: 0.06 + depth * 0.2,
      tw: Math.random() * 6.28,
      twS: 0.004 + Math.random() * 0.02,
    };
  };

  const resize = () => {
    if (!canvas || !context) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    fx.width = window.innerWidth;
    fx.height = window.innerHeight;
    canvas.width = fx.width * dpr;
    canvas.height = fx.height * dpr;
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    const count = Math.min(150, Math.round((fx.width * fx.height) / 11000));
    fx.parts = Array.from({ length: count }, () => makePart(true));
  };

  const readGold = () => {
    const value = getComputedStyle(document.body).getPropertyValue("--gold").trim();
    const match = value.match(/^#([0-9a-fA-F]{6})$/);
    if (!match) return;
    const hex = match[1];
    fx.gold = `${parseInt(hex.slice(0, 2), 16)},${parseInt(hex.slice(2, 4), 16)},${parseInt(hex.slice(4, 6), 16)}`;
  };

  const onMove = (event) => {
    fx.mx = event.clientX;
    fx.my = event.clientY;
    fx.seen = true;
    fx.hover = !!event.target.closest("a,button,input,select,[data-cursor]");
  };

  const onLeave = () => {
    fx.mx = -500;
    fx.my = -500;
  };

  window.addEventListener("resize", resize);
  window.addEventListener("mousemove", onMove);
  document.documentElement.addEventListener("mouseleave", onLeave);
  resize();
  readGold();

  const loop = () => {
    fx.raf = requestAnimationFrame(loop);
    fx.frame += 1;
    if (fx.frame % 90 === 0) readGold();

    if (finePointer && fx.seen) {
      dot.style.transform = `translate(${fx.mx}px, ${fx.my}px)`;
      fx.rx += (fx.mx - fx.rx) * 0.16;
      fx.ry += (fx.my - fx.ry) * 0.16;
      const targetScale = fx.hover ? 0.55 : 1;
      fx.rs += (targetScale - fx.rs) * 0.2;
      ring.style.transform = `translate(${fx.rx.toFixed(1)}px, ${fx.ry.toFixed(1)}px) scale(${fx.rs.toFixed(3)})`;
      ring.style.opacity = fx.hover ? "0.9" : "0.5";
    }

    if (!context || document.hidden) return;
    context.clearRect(0, 0, fx.width, fx.height);

    if (fx.mx > -100) {
      const glow = context.createRadialGradient(fx.mx, fx.my, 0, fx.mx, fx.my, 240);
      glow.addColorStop(0, `rgba(${fx.gold},0.055)`);
      glow.addColorStop(1, `rgba(${fx.gold},0)`);
      context.fillStyle = glow;
      context.fillRect(fx.mx - 240, fx.my - 240, 480, 480);
    }

    fx.parts.forEach((part) => {
      if (!reduceMotion) {
        part.x += part.s;
        part.tw += part.twS;
        part.y += Math.sin(part.tw) * 0.06;
        if (part.x > fx.width + 12) {
          part.x = -12;
          part.y = Math.random() * fx.height;
        }
      }
      const dx = part.x - fx.mx;
      const dy = part.y - fx.my;
      const distance = Math.sqrt(dx * dx + dy * dy);
      const boost = distance < 200 ? 1 - distance / 200 : 0;
      const alpha = Math.max(0, Math.min(0.85, part.a + boost * 0.5 + Math.sin(part.tw * 2) * 0.02));
      context.beginPath();
      context.arc(part.x, part.y, part.r + boost * 0.7, 0, 6.2832);
      context.fillStyle = `rgba(${fx.gold},${alpha.toFixed(3)})`;
      context.fill();
    });
  };

  loop();
}
