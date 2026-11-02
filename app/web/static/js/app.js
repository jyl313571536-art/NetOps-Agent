/**
 * NetOps Agent Web 测试控制台前端逻辑。
 *
 * 只通过 /api/v1 后端接口与业务层交互：
 * 不直接调用 MiMo API，不直接访问 SQLite / Chroma。
 */

"use strict";

// ---------- 通用工具 ----------

/** 安全转义，防止把接口返回内容当 HTML 注入。 */
function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** 统一请求封装：返回 JSON，失败时抛出可展示的错误信息。 */
async function api(path, options) {
  let resp;
  try {
    resp = await fetch(path, options);
  } catch (err) {
    throw new Error("网络请求失败：" + err.message);
  }
  let data = null;
  try {
    data = await resp.json();
  } catch (err) {
    throw new Error("响应不是合法 JSON（HTTP " + resp.status + "）");
  }
  if (!resp.ok) {
    const msg = (data && (data.message || data.detail)) || ("HTTP " + resp.status);
    throw new Error(msg);
  }
  return data;
}

function showError(id, err) {
  const box = document.getElementById(id);
  box.textContent = String(err.message || err);
  box.hidden = false;
}

function hideError(id) {
  document.getElementById(id).hidden = true;
}

// ---------- 页面切换 ----------

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("page-" + btn.dataset.page).classList.add("active");
  });
});

// ---------- Dashboard ----------

async function loadDashboard() {
  const set = (id, text) => { document.getElementById(id).textContent = text; };
  try {
    const health = await api("/health");
    set("ds-api", "正常 (" + health.app + " v" + health.version + ")");
  } catch (err) {
    set("ds-api", "不可用：" + err.message);
  }
  try {
    const p = await api("/api/v1/agent/providers");
    set("ds-model",
      p.model + " | Key 已配置：" + (p.api_key_configured ? "是" : "否") +
      " | 超时 " + p.timeout + "s");
  } catch (err) {
    set("ds-model", "不可用：" + err.message);
  }
  try {
    const k = await api("/api/v1/knowledge/status");
    set("ds-rag", "已索引片段：" + k.indexed_chunks);
  } catch (err) {
    set("ds-rag", "不可用：" + err.message);
  }
  try {
    const h = await api("/api/v1/history?limit=1");
    set("ds-history", "记录总数：" + h.total);
  } catch (err) {
    set("ds-history", "不可用：" + err.message);
  }
}

// ---------- Agent Chat（SSE 流式） ----------

document.getElementById("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  hideError("chat-error");
  const resultBox = document.getElementById("chat-result");
  resultBox.hidden = true;

  const message = document.getElementById("chat-message").value.trim();
  if (!message) {
    showError("chat-error", new Error("请输入故障描述"));
    return;
  }
  const btn = document.getElementById("chat-submit");
  btn.disabled = true;
  btn.textContent = "诊断中...";
  const progress = document.getElementById("chat-progress");
  progress.hidden = false;
  progress.textContent = "已提交，开始诊断...";
  try {
    await streamChat(message, progress);
  } catch (err) {
    showError("chat-error", err);
  } finally {
    btn.disabled = false;
    btn.textContent = "发送";
    progress.hidden = true;
  }
});

/** SSE 流式诊断：逐步接收节点进度，最终接收完整结果。 */
async function streamChat(message, progressEl) {
  const resp = await fetch("/api/v1/agent/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: message }),
  });
  if (!resp.ok || !resp.body) {
    throw new Error("流式请求失败（HTTP " + resp.status + "）");
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop();
    for (const part of parts) {
      const evt = parseSse(part);
      if (!evt) continue;
      if (evt.event === "node") {
        progressEl.textContent = evt.data.summary || evt.data.node;
      } else if (evt.event === "result") {
        renderChat(evt.data);
        document.getElementById("chat-result").hidden = false;
      } else if (evt.event === "error") {
        throw new Error(evt.data.message || "诊断失败");
      }
    }
  }
}

/** 解析单个 SSE 块（event: x \n data: {...}）。 */
function parseSse(chunk) {
  let event = "message";
  let data = "";
  for (const line of chunk.split("\n")) {
    if (line.startsWith("event: ")) event = line.slice(7).trim();
    else if (line.startsWith("data: ")) data += line.slice(6);
  }
  if (!data) return null;
  try {
    return { event: event, data: JSON.parse(data) };
  } catch (err) {
    return null;
  }
}

function statusBadge(status) {
  const cls = status === "confirmed" ? "" :
    status === "failed" ? "fail" : "warn";
  return '<span class="badge ' + cls + '">' + esc(status) + "</span>";
}

function renderChat(data) {
  document.getElementById("chat-status").innerHTML = statusBadge(data.diagnosis_status);
  document.getElementById("chat-answer").textContent = data.answer || "（无）";

  const toolsWrap = document.getElementById("chat-tools-wrap");
  const tools = data.tool_results || [];
  toolsWrap.hidden = tools.length === 0;
  document.getElementById("chat-tools").innerHTML = tools.map((t) =>
    "<li><code>" + esc(t.tool_name) + "</code> [" + esc(t.source) + "] " +
    (t.success ? "成功" : "失败") + "：" + esc(t.summary || t.error || "") + "</li>"
  ).join("");

  const citesWrap = document.getElementById("chat-citations-wrap");
  const cites = data.citations || [];
  citesWrap.hidden = cites.length === 0;
  document.getElementById("chat-citations").innerHTML = cites.map((c) =>
    "<li>[" + esc(c.marker) + "] 来源 <code>" + esc(c.source) + "</code>" +
    "（verified=" + esc(c.verified) + "）：" + esc(c.snippet) + "</li>"
  ).join("");

  const stepsWrap = document.getElementById("chat-steps-wrap");
  const steps = data.next_steps || [];
  stepsWrap.hidden = steps.length === 0;
  document.getElementById("chat-steps").innerHTML =
    steps.map((s) => "<li>" + esc(s) + "</li>").join("");
}

// ---------- Network Diagnostics ----------

let toolSpecs = [];

async function loadTools() {
  try {
    toolSpecs = await api("/api/v1/diagnostics/tools");
    const select = document.getElementById("diag-tool");
    select.innerHTML = toolSpecs.map((t) =>
      '<option value="' + esc(t.name) + '">' + esc(t.name) + " [" + esc(t.source) + "]</option>"
    ).join("");
    renderToolFields();
  } catch (err) {
    showError("diag-error", err);
  }
}

function renderToolFields() {
  const name = document.getElementById("diag-tool").value;
  const spec = toolSpecs.find((t) => t.name === name);
  const container = document.getElementById("diag-fields");
  if (!spec) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = (spec.fields || []).map((f) => {
    const label = esc(f.name) + (f.required ? " *" : "");
    const def = f.default == null ? "" : f.default;
    return '<label>' + label + "（" + esc(f.description) + "）" +
      '<input type="text" data-field="' + esc(f.name) + '" value="' + esc(def) + '"></label>';
  }).join("");
}

document.getElementById("diag-tool").addEventListener("change", renderToolFields);

document.getElementById("diag-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  hideError("diag-error");
  document.getElementById("diag-result").hidden = true;

  const toolName = document.getElementById("diag-tool").value;
  const spec = toolSpecs.find((t) => t.name === toolName);
  const args = {};
  if (spec) {
    for (const f of spec.fields || []) {
      const input = document.querySelector('[data-field="' + f.name + '"]');
      const raw = input ? input.value.trim() : "";
      if (raw !== "") {
        args[f.name] = f.type === "integer" ? Number(raw) : raw;
      }
    }
  }
  const btn = document.getElementById("diag-submit");
  btn.disabled = true;
  try {
    const data = await api("/api/v1/diagnostics/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tool_name: toolName, args: args }),
    });
    document.getElementById("diag-source").textContent = data.source;
    const ok = document.getElementById("diag-success");
    ok.textContent = data.success ? "成功" : "失败";
    ok.className = "badge " + (data.success ? "" : "fail");
    document.getElementById("diag-summary").textContent = data.summary || "（无）";
    const errRow = document.getElementById("diag-error-row");
    errRow.hidden = !data.error;
    document.getElementById("diag-error-text").textContent = data.error || "";
    document.getElementById("diag-detail").textContent =
      JSON.stringify(data.detail || {}, null, 2);
    document.getElementById("diag-result").hidden = false;
  } catch (err) {
    showError("diag-error", err);
  } finally {
    btn.disabled = false;
  }
});

// ---------- Knowledge Base ----------

document.getElementById("kb-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  hideError("kb-error");
  const query = document.getElementById("kb-query").value.trim();
  if (!query) {
    showError("kb-error", new Error("请输入检索内容"));
    return;
  }
  const btn = document.getElementById("kb-submit");
  btn.disabled = true;
  try {
    const data = await api("/api/v1/knowledge/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: query }),
    });
    const hits = data.hits || [];
    document.getElementById("kb-results").innerHTML =
      hits.length === 0
        ? '<p class="hint">无检索结果</p>'
        : hits.map((h) =>
            '<div class="result-box">' +
            "<p><strong>来源：</strong><code>" + esc(h.source) + "</code>" +
            "（score=" + esc(h.score) + "）</p><p>" + esc(h.content) + "</p></div>"
          ).join("");
  } catch (err) {
    showError("kb-error", err);
  } finally {
    btn.disabled = false;
  }
});

async function loadKnowledgeStatus() {
  try {
    const k = await api("/api/v1/knowledge/status");
    document.getElementById("kb-status").textContent =
      "知识库已索引片段：" + k.indexed_chunks;
  } catch (err) {
    document.getElementById("kb-status").textContent = "状态不可用：" + err.message;
  }
}

// ---------- History ----------

async function loadHistory() {
  hideError("history-error");
  try {
    const data = await api("/api/v1/history?limit=50");
    const records = data.records || [];
    document.getElementById("history-body").innerHTML =
      records.length === 0
        ? '<tr><td colspan="6">暂无诊断记录</td></tr>'
        : records.map((r) =>
            "<tr><td>" + esc(r.created_at) + "</td>" +
            "<td>" + esc(r.user_message) + "</td>" +
            "<td>" + esc(r.issue_category) + "</td>" +
            "<td>" + statusBadge(r.diagnosis_status) + "</td>" +
            "<td>" + esc((r.executed_tools || []).join(", ") || "无") + "</td>" +
            "<td>" + esc(r.duration_ms) + "</td></tr>"
          ).join("");
  } catch (err) {
    showError("history-error", err);
  }
}

document.getElementById("history-refresh").addEventListener("click", loadHistory);

// ---------- 初始化 ----------

loadDashboard();
loadTools();
loadKnowledgeStatus();
loadHistory();
