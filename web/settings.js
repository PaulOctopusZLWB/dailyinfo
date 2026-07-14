const form = document.querySelector("#credentialForm");
const saveButton = document.querySelector("#saveButton");
const pageNotice = document.querySelector("#pageNotice");
const configuredCount = document.querySelector("#configuredCount");
const readinessFill = document.querySelector("#readinessFill");
const recommendedKeys = ["GITHUB_TOKEN", "OPENALEX_API_KEY"];

let credentialState = {};

init();

async function init() {
  bindEvents();
  await refreshStatus();
}

function bindEvents() {
  form.addEventListener("submit", saveCredentials);

  document.querySelectorAll("[data-reveal]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.querySelector(`#${button.dataset.reveal}`);
      const reveal = input.type === "password";
      input.type = reveal ? "text" : "password";
      button.textContent = reveal ? "隐藏" : "显示";
    });
  });

  document.querySelectorAll("[data-clear]").forEach((button) => {
    button.addEventListener("click", async () => {
      const key = button.dataset.clear;
      if (!window.confirm(`清除本机保存的 ${key}？`)) return;
      await updateCredentials({}, [key], "已清除本机凭据。重新启动时，外部环境变量仍可能继续生效。");
    });
  });
}

async function refreshStatus() {
  try {
    const response = await fetch("/api/settings/credentials", {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) throw new Error(await responseMessage(response));
    const payload = await response.json();
    credentialState = payload.credentials || {};
    renderStatus();
  } catch (error) {
    showNotice(error.message || "无法读取 API 配置状态。", true);
    configuredCount.textContent = "—";
  }
}

async function saveCredentials(event) {
  event.preventDefault();
  const values = {};
  new FormData(form).forEach((rawValue, key) => {
    const value = String(rawValue).trim();
    if (value) values[key] = value;
  });

  if (!Object.keys(values).length) {
    showNotice("没有检测到新填写的密钥；空白字段不会覆盖已有值。", false);
    return;
  }

  await updateCredentials(values, [], `已保存 ${Object.keys(values).length} 项。本页面不会再次显示密钥原值。`);
  form.querySelectorAll("input[type='password'], input[type='text']").forEach((input) => {
    input.value = "";
    input.type = "password";
  });
  document.querySelectorAll("[data-reveal]").forEach((button) => {
    button.textContent = "显示";
  });
}

async function updateCredentials(values, clear, successMessage) {
  saveButton.disabled = true;
  saveButton.textContent = "正在保存…";
  try {
    const response = await fetch("/api/settings/credentials", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ values, clear }),
    });
    if (!response.ok) throw new Error(await responseMessage(response));
    const payload = await response.json();
    credentialState = payload.credentials || {};
    renderStatus();
    showNotice(successMessage, false);
  } catch (error) {
    showNotice(error.message || "保存失败，请检查密钥格式。", true);
  } finally {
    saveButton.disabled = false;
    saveButton.textContent = "保存新填写的密钥";
  }
}

function renderStatus() {
  document.querySelectorAll("[data-credential]").forEach((row) => {
    const key = row.dataset.credential;
    const status = credentialState[key] || {};
    const configured = Boolean(status.configured);
    row.classList.toggle("configured", configured);
    const label = row.querySelector(".credentialStatus");
    const clear = row.querySelector("[data-clear]");
    label.textContent = configured ? `已配置 · ${sourceLabel(status.source)}` : "未配置";
    clear.hidden = !configured || status.source === "environment";
  });

  const completed = recommendedKeys.filter((key) => credentialState[key]?.configured).length;
  configuredCount.textContent = String(completed);
  readinessFill.style.width = `${(completed / recommendedKeys.length) * 100}%`;
}

function sourceLabel(source) {
  if (source === "local_file") return "本机 .env";
  if (source === "environment") return "外部环境变量";
  return "未知来源";
}

function showNotice(message, isError) {
  pageNotice.hidden = false;
  pageNotice.textContent = message;
  pageNotice.classList.toggle("error", isError);
  pageNotice.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function responseMessage(response) {
  try {
    const payload = await response.json();
    return payload.detail || `请求失败（${response.status}）`;
  } catch {
    return `请求失败（${response.status}）`;
  }
}
