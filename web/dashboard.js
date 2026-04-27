const state = {
  hours: 24,
  tab: "overview",
  data: {
    accounts: [],
    usageSummary: null,
    usageLedger: [],
    usageSnapshot: [],
    reconcile: [],
    keys: [],
  },
};

async function fetchJson(url, options = {}) {
  const res = await fetch(url, { credentials: "same-origin", cache: "no-store", ...options });
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    return { error: { message: text || `HTTP ${res.status}` } };
  }
}

function n(v) {
  const x = Number(v || 0);
  return Number.isFinite(x) ? x : 0;
}

function fmt(v) {
  return n(v).toLocaleString("en-US");
}

function setText(id, value) {
  const el = document.querySelector(id);
  if (el) el.textContent = value;
}

function toRows(items, cols) {
  if (!items.length) return '<div class="list-item"><span>暂无数据</span></div>';
  return `<table><thead><tr>${cols.map((c) => `<th>${c.label}</th>`).join("")}</tr></thead><tbody>${items
    .map((it) => `<tr>${cols.map((c) => `<td>${c.render(it)}</td>`).join("")}</tr>`)
    .join("")}</tbody></table>`;
}

function renderSummary() {
  const accounts = state.data.accounts || [];
  const usage = state.data.usageSummary || {};
  setText("#stat-accounts", String(accounts.length));
  setText("#stat-accounts-meta", `active ${accounts.filter((a) => a.status === "active").length}`);
  setText("#stat-warnings", String((usage.data || []).filter((k) => n(k.failure_count) > 0).length));
  setText("#stat-warnings-meta", "key failure > 0");
  setText("#stat-transport", fmt(usage.total_input_tokens || 0));
  setText("#stat-transport-meta", "input tokens");
  setText("#stat-responses-transport", fmt(usage.total_request_count || 0));
  setText("#stat-responses-transport-meta", "requests");
}

function renderAccounts() {
  const list = document.querySelector("#accounts-list");
  if (!list) return;
  list.innerHTML = toRows(state.data.accounts || [], [
    { label: "账号", render: (x) => x.email || x.entry_id || "-" },
    { label: "状态", render: (x) => x.status || "-" },
    { label: "计划", render: (x) => x.plan_type || "-" },
    { label: "请求数", render: (x) => fmt((x.usage || {}).request_count || 0) },
    { label: "输入", render: (x) => fmt((x.usage || {}).input_tokens || 0) },
    { label: "输出", render: (x) => fmt((x.usage || {}).output_tokens || 0) },
    { label: "更新时间", render: (x) => x.updated_at || "-" },
  ]);
}

function renderUsage() {
  const chart = document.querySelector("#usage-chart");
  const feed = document.querySelector("#usage-feed");
  if (chart) {
    chart.innerHTML = toRows(state.data.usageLedger || [], [
      { label: "时间", render: (x) => x.timestamp || "-" },
      { label: "请求", render: (x) => fmt(x.request_count) },
      { label: "输入", render: (x) => fmt(x.input_tokens) },
      { label: "输出", render: (x) => fmt(x.output_tokens) },
    ]);
  }
  if (feed) {
    feed.innerHTML = toRows(state.data.reconcile || [], [
      { label: "时间", render: (x) => x.timestamp || "-" },
      { label: "Δ请求", render: (x) => fmt(x.delta_request_count) },
      { label: "Δ输入", render: (x) => fmt(x.delta_input_tokens) },
      { label: "Δ输出", render: (x) => fmt(x.delta_output_tokens) },
      { label: "偏差", render: (x) => (x.mismatch ? "yes" : "no") },
    ]);
  }
}

function renderKeys() {
  const list = document.querySelector("#api-key-list");
  if (!list) return;
  list.innerHTML = toRows(state.data.keys || [], [
    { label: "名称", render: (x) => x.name || "-" },
    { label: "前缀", render: (x) => `${x.key_prefix || ""}...` },
    { label: "请求", render: (x) => fmt(x.request_count) },
    { label: "输入", render: (x) => fmt(x.input_tokens) },
    { label: "输出", render: (x) => fmt(x.output_tokens) },
    { label: "成功率", render: (x) => `${((n(x.success_count) * 100) / Math.max(1, n(x.request_count))).toFixed(1)}%` },
  ]);
}

async function loadAll() {
  const [accounts, usageSummary, usageLedger, usageSnapshot, reconcile, keys] = await Promise.all([
    fetchJson("/admin/accounts/list"),
    fetchJson(`/admin/usage/summary?hours=${state.hours}`),
    fetchJson(`/admin/usage/history?source=ledger&granularity=hourly&hours=${state.hours}`),
    fetchJson(`/admin/usage/history?source=snapshot&granularity=hourly&hours=${state.hours}`),
    fetchJson(`/admin/usage/reconcile?granularity=hourly&hours=${state.hours}`),
    fetchJson(`/admin/keys/list?hours=${state.hours}`),
  ]);
  state.data.accounts = accounts.data || [];
  state.data.usageSummary = usageSummary.data || {};
  state.data.usageLedger = usageLedger.data || [];
  state.data.usageSnapshot = usageSnapshot.data || [];
  state.data.reconcile = reconcile.data || [];
  state.data.keys = keys.data || [];
}

async function createKey() {
  const input = document.querySelector("#api-key-name");
  const name = (input?.value || "").trim();
  const res = await fetchJson("/admin/keys/create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const out = document.querySelector("#api-key-result");
  if (out) out.textContent = JSON.stringify(res, null, 2);
  if (input) input.value = "";
  await refresh();
}

async function runReconcile() {
  await fetchJson("/admin/usage/reconcile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ hours: state.hours, granularity: "hourly" }),
  });
  await refresh();
}

async function refresh() {
  await loadAll();
  renderSummary();
  renderAccounts();
  renderUsage();
  renderKeys();
}

document.querySelector("#create-api-key")?.addEventListener("click", () => createKey().catch(console.error));
document.querySelector("#refresh-usage")?.addEventListener("click", () => refresh().catch(console.error));
document.querySelectorAll("[data-hours]").forEach((btn) => {
  btn.addEventListener("click", () => {
    state.hours = Number(btn.getAttribute("data-hours") || "24");
    refresh().catch(console.error);
  });
});
document.querySelector("#run-test")?.addEventListener("click", () => runReconcile().catch(console.error));

refresh().catch((err) => {
  document.body.insertAdjacentHTML("beforeend", `<pre>${String(err)}</pre>`);
});
