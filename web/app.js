const endpoints = {
  status: "/auth/status",
  runtime: "/admin/runtime-status",
  rotation: "/admin/rotation-settings",
  usage: "/admin/usage-stats/summary",
  apiKeys: "/admin/api-keys",
  accounts: "/auth/accounts?quota=fresh",
  proxies: "/api/proxies",
  relays: "/api/relay-providers",
  recentRequests: "/admin/recent-requests?limit=12",
  loginStart: "/auth/login-start",
  codeRelay: "/auth/code-relay",
  codexAppSelect: "/auth/codex-app/select",
};

const uiState = {
  view: "overview",
  accountFilter: "all",
  proxyGroup: "__all__",
  usageGranularity: "hourly",
  usageHours: 24,
  autoRefreshMs: 300000,
  refreshInFlight: false,
  lastRefreshAt: "",
  language: "zh-CN",
  data: null,
  authPopup: null,
};

const LANGUAGE_STORAGE_KEY = "codex2gpt.dashboard.language";

const TRANSLATIONS = {
  "zh-CN": {
    "page.title": "Codex2gpt 控制台",
    "brand.title": "Codex2gpt 控制台",
    "brand.subtitle": "账号、路由与传输的运行控制台",
    "topbar.caption": "操作工作台",
    "topbar.language": "语言",
    "nav.overview": "总览",
    "nav.proxy": "代理设置",
    "nav.usage": "用量统计",
    "summary.accounts": "账号",
    "summary.warnings": "告警",
    "summary.transport": "传输",
    "summary.responses": "Responses",
    "runtime.eyebrow": "实时状态",
    "runtime.title": "运行快照",
    "runtime.subtitle": "当前路由模式、认证状态、WebSocket 就绪情况与告警状态。",
    "overview.accounts.eyebrow": "账号",
    "overview.accounts.title": "账号总览",
    "overview.accounts.subtitle": "一眼查看额度状态、代理分配和 Codex App 占用情况。",
    "overview.tasks.eyebrow": "操作任务",
    "overview.tasks.title": "控制面板",
    "overview.tasks.subtitle": "优先展示核心动作，再补充细节和历史信息。",
    "auth.kicker": "认证",
    "auth.title": "添加账号",
    "auth.subtitle": "为另一个 Codex 账号启动浏览器 OAuth 流程。默认会使用 <code>localhost:1455</code> 的本地回调；如果未能自动完成，可以手动粘贴回调 URL。",
    "auth.start": "添加账号",
    "auth.callbackLabel": "手动回调 URL",
    "auth.callbackPlaceholder": "如有需要，请粘贴 localhost:1455/auth/callback?... 到这里",
    "auth.complete": "完成登录",
    "diagnostics.kicker": "诊断",
    "diagnostics.title": "连接测试",
    "diagnostics.subtitle": "对当前最优可用目标执行一次真实诊断。",
    "diagnostics.run": "运行测试",
    "codexApp.kicker": "身份",
    "codexApp.title": "Codex App",
    "codexApp.subtitle": "选择要写入 <code>~/.codex/auth.json</code> 的已保存账号，供 Codex App 使用。",
    "settings.kicker": "路由",
    "settings.title": "运行设置",
    "settings.subtitle": "无需手改环境变量文件，直接调整默认路由行为。",
    "settings.rotationMode": "轮换模式",
    "settings.responsesTransport": "Responses 传输方式",
    "settings.save": "保存设置",
    "api.kicker": "端点",
    "api.title": "API 接入",
    "api.subtitle": "复制客户端最常用的接口地址。",
    "ops.kicker": "运维",
    "ops.title": "运行控制",
    "ops.subtitle": "需要最新状态时，可按需触发后台任务。",
    "ops.refreshQuota": "刷新额度",
    "ops.checkProxies": "检查代理",
    "ops.refreshFingerprint": "刷新指纹",
    "ops.refreshTokens": "刷新令牌",
    "health.kicker": "健康",
    "health.title": "状态详情",
    "warnings.kicker": "关注",
    "warnings.title": "告警",
    "traffic.kicker": "流量",
    "traffic.title": "最近请求",
    "traffic.subtitle": "显示最近请求实际命中的账号；如果有用量数据，也会显示缓存命中率。",
    "proxy.eyebrow": "路由",
    "proxy.title": "代理设置",
    "proxy.subtitle": "按健康状态查看代理，检查分配模式，并快速审阅账号路由。",
    "proxy.filtersKicker": "筛选",
    "proxy.groupsTitle": "代理分组",
    "proxy.groupsSubtitle": "按默认模式或指定代理目标切分账号分配情况。",
    "proxy.healthKicker": "健康",
    "proxy.healthTitle": "代理健康",
    "proxy.assignmentsKicker": "分配",
    "proxy.assignmentsTitle": "账号分配",
    "proxy.providersKicker": "提供方",
    "proxy.providersTitle": "中继提供方",
    "usage.eyebrow": "分析",
    "usage.title": "用量统计",
    "usage.subtitle": "用更紧凑的视觉层级查看 token 与请求趋势。",
    "usage.refresh": "刷新用量",
    "usage.inputTokens": "输入 Tokens",
    "usage.outputTokens": "输出 Tokens",
    "usage.requests": "请求数",
    "usage.trackedAccounts": "已追踪账号",
    "usage.trackedAccountsMeta": "已有用量快照记录的账号",
    "usage.latestTotal": "已追踪账号的最新总量",
    "usage.timelineKicker": "时间线",
    "usage.timelineTitle": "用量时间线",
    "usage.hourly": "按小时",
    "usage.daily": "按天",
    "usage.feedKicker": "最近点位",
    "usage.feedTitle": "用量明细",
    "common.loading": "加载中...",
    "common.idle": "空闲",
    "common.yes": "是",
    "common.no": "否",
    "common.unknown": "未知",
    "common.none": "无",
    "common.copyUrl": "复制链接",
    "common.copied": "已复制",
    "common.copyFailed": "复制失败",
    "common.refreshed": "刷新时间",
    "common.noData": "无数据",
    "common.limitReached": "已到上限",
    "common.active": "活跃",
    "common.critical": "严重",
    "common.warning": "告警",
    "common.model": "模型",
    "common.prompt": "输入",
    "common.cached": "缓存",
    "common.window": "窗口",
    "common.reset": "重置",
    "common.remaining": "剩余",
    "common.status": "状态",
    "common.plan": "套餐",
    "common.updated": "更新于",
    "common.account": "账号",
    "common.routing": "路由",
    "common.quota": "额度",
    "warning.banner.title": "需要关注额度与运行状态告警",
    "warning.banner.subtitle": "{total} 个活动告警，涉及 {activeCount} 个活跃账号。",
    "warning.banner.warnings": "告警",
    "warning.banner.activeAccounts": "活跃账号",
    "summary.active": "{count} 个活跃",
    "summary.critical": "{count} 个严重",
    "summary.websocket": "{state} websocket",
    "summary.relayProviders": "{count} 个中继提供方",
    "badge.rotation": "轮换",
    "badge.responses": "Responses",
    "badge.backend": "后端",
    "badge.websocket": "WebSocket",
    "badge.proxyHealth": "代理健康",
    "badge.lastHit": "最近命中",
    "badge.allClear": "全部正常",
    "badge.degraded": "{count} 个异常",
    "status.authenticated": "已认证",
    "status.passwordRequired": "需要密码",
    "status.localDashboardBypass": "本地面板绕过",
    "status.accounts": "账号数",
    "status.proxies": "代理数",
    "status.relayProviders": "中继提供方",
    "status.usageDataPoints": "用量点位",
    "status.backgroundJobs": "后台任务",
    "status.enabled": "已启用",
    "status.disabled": "已禁用",
    "status.noneRegistered": "未注册",
    "api.openaiChat": "OpenAI Chat",
    "api.anthropicMessages": "Anthropic Messages",
    "api.gemini": "Gemini",
    "api.codexResponses": "Codex Responses",
    "codexApp.noMatchedAccount": "未匹配到本地账号",
    "codexApp.authFile": "认证文件",
    "codexApp.currentAccount": "当前账号",
    "codexApp.entryId": "Entry ID",
    "codexApp.accountId": "Account ID",
    "codexApp.identityKey": "Identity Key",
    "codexApp.reservedInApiPool": "已在 API 池保留",
    "codexApp.applyMode": "应用方式",
    "codexApp.applyModeValue": "只写入 auth.json，之后请手动重启 Codex App",
    "codexApp.externalChange": "外部变更",
    "codexApp.detected": "已检测到",
    "warnings.empty": "当前没有额度告警。",
    "recentRequests.empty": "还没有请求记录。",
    "recentRequests.cache": "缓存",
    "recentRequests.completed": "已完成",
    "recentRequests.noModel": "—",
    "accountFilter.all": "全部账号",
    "accountFilter.active": "活跃",
    "accountFilter.warned": "告警中",
    "accountFilter.rateLimited": "已限流",
    "accountFilter.expired": "已过期",
    "accountFilter.banned": "已封禁",
    "accountFilter.disabled": "已禁用",
    "accounts.empty": "当前筛选条件下没有账号。",
    "accounts.proxyTrafficChanged": "额度已变化，但这里不跟踪非代理流量",
    "accounts.noUsageYet": "暂无使用",
    "accounts.codexCurrent": "Codex App 当前账号",
    "accounts.codexReserved": "已从 codex2api 保留",
    "accounts.proxyMode": "代理模式: {value}",
    "accounts.assignedProxy": "已分配代理: {value}",
    "accounts.currentCodexButton": "当前 Codex App 账号",
    "accounts.setCodexButton": "设为 Codex App 账号",
    "accounts.proxyTraffic": "代理流量",
    "accounts.quotaWindow": "额度窗口",
    "accounts.secondaryWindow": "次级窗口",
    "accounts.usedPercent": "已使用 {value}%",
    "proxy.summary.proxies": "代理",
    "proxy.summary.active": "活跃",
    "proxy.summary.degraded": "异常",
    "proxy.groups.all": "全部账号",
    "proxy.groups.global": "全局默认",
    "proxy.groups.direct": "直连",
    "proxy.groups.auto": "自动",
    "proxy.groups.accountCount": "{count} 个账号",
    "proxy.empty": "未配置代理。",
    "proxy.exitIp": "出口 IP",
    "proxy.latency": "延迟",
    "proxy.assignments.empty": "当前代理分组下没有账号。",
    "proxy.table.account": "账号",
    "proxy.table.status": "状态",
    "proxy.table.plan": "套餐",
    "proxy.table.routing": "路由",
    "proxy.table.quota": "额度",
    "proxy.table.updated": "更新时间",
    "relays.empty": "未配置中继提供方。",
    "usage.feed.empty": "还没有用量数据。",
    "usage.feed.input": "输入",
    "usage.feed.output": "输出",
    "usage.feed.requests": "请求",
    "usage.chart.empty": "还没有用量历史。",
    "usage.chart.inputLegend": "输入 Tokens",
    "usage.chart.outputLegend": "输出 Tokens",
    "usage.chart.requestsLegend": "请求数",
    "login.starting": "正在启动浏览器登录...",
    "login.redirectUri": "回调地址: {value}",
    "login.callbackReady": "本地回调服务已在 localhost:1455 就绪。",
    "login.callbackUnavailable": "本地回调服务不可用: {error}",
    "login.popupOpen": "将会弹出 OAuth 登录窗口。",
    "login.autoRefresh": "如果弹窗成功完成，账号列表会自动刷新。",
    "login.manualPaste": "如果弹窗无法自动完成，请将回调 URL 粘贴到下方并点击完成登录。",
    "login.popupBlocked": "弹窗被拦截了。请手动打开授权地址，再把回调 URL 粘贴到下方。",
    "login.pasteCallbackFirst": "请先粘贴 localhost 回调 URL。",
    "login.completing": "正在完成登录...",
    "connection.running": "运行中...",
    "settings.saving": "保存中...",
    "jobs.running": "正在运行 {job}...",
    "codexApp.switchFailed": "切换失败",
    "oauth.complete": "OAuth 登录完成，正在刷新账号列表...",
    "oauth.failed": "OAuth 登录失败"
  },
  en: {
    "page.title": "Codex2gpt Dashboard",
    "brand.title": "Codex2gpt Dashboard",
    "brand.subtitle": "Runtime control plane for accounts, routing, and transport",
    "topbar.caption": "Operator Workspace",
    "topbar.language": "Language",
    "nav.overview": "Overview",
    "nav.proxy": "Proxy Settings",
    "nav.usage": "Usage Stats",
    "summary.accounts": "Accounts",
    "summary.warnings": "Warnings",
    "summary.transport": "Transport",
    "summary.responses": "Responses",
    "runtime.eyebrow": "Live State",
    "runtime.title": "Runtime Snapshot",
    "runtime.subtitle": "Current routing mode, authentication posture, websocket readiness, and warning state.",
    "overview.accounts.eyebrow": "Accounts",
    "overview.accounts.title": "Account Overview",
    "overview.accounts.subtitle": "Quota posture, proxy assignments, and Codex App ownership in one scan.",
    "overview.tasks.eyebrow": "Operator Tasks",
    "overview.tasks.title": "Command Surface",
    "overview.tasks.subtitle": "Primary actions first, supporting detail second, historical context last.",
    "auth.kicker": "Authentication",
    "auth.title": "Add Account",
    "auth.subtitle": "Start the browser OAuth flow for another Codex account. The happy path uses a local callback on <code>localhost:1455</code>; if that cannot finish, you can paste the callback URL manually.",
    "auth.start": "Add Account",
    "auth.callbackLabel": "Manual Callback URL",
    "auth.callbackPlaceholder": "Paste localhost:1455/auth/callback?... here if needed",
    "auth.complete": "Complete Login",
    "diagnostics.kicker": "Diagnostics",
    "diagnostics.title": "Connection Test",
    "diagnostics.subtitle": "Runs a real diagnostic against the best available target.",
    "diagnostics.run": "Run Test",
    "codexApp.kicker": "Identity",
    "codexApp.title": "Codex App",
    "codexApp.subtitle": "Select which saved account should be written into <code>~/.codex/auth.json</code> for Codex App.",
    "settings.kicker": "Routing",
    "settings.title": "Runtime Settings",
    "settings.subtitle": "Adjust routing defaults without editing env files by hand.",
    "settings.rotationMode": "Rotation Mode",
    "settings.responsesTransport": "Responses Transport",
    "settings.save": "Save Settings",
    "api.kicker": "Endpoints",
    "api.title": "API Access",
    "api.subtitle": "Copy the endpoints your clients need most often.",
    "ops.kicker": "Operations",
    "ops.title": "Runtime Controls",
    "ops.subtitle": "Run background jobs on demand when you need fresh state.",
    "ops.refreshQuota": "Refresh Quota",
    "ops.checkProxies": "Check Proxies",
    "ops.refreshFingerprint": "Refresh Fingerprint",
    "ops.refreshTokens": "Refresh Tokens",
    "health.kicker": "Health",
    "health.title": "Status Details",
    "warnings.kicker": "Attention",
    "warnings.title": "Warnings",
    "traffic.kicker": "Traffic",
    "traffic.title": "Recent Requests",
    "traffic.subtitle": "Shows which account each recent request actually hit, plus cache hit rate when usage data is available.",
    "proxy.eyebrow": "Routing",
    "proxy.title": "Proxy Settings",
    "proxy.subtitle": "Group proxies by health, inspect assignment modes, and review account routing at a glance.",
    "proxy.filtersKicker": "Filters",
    "proxy.groupsTitle": "Proxy Groups",
    "proxy.groupsSubtitle": "Slice account assignments by default mode or by a specific proxy target.",
    "proxy.healthKicker": "Health",
    "proxy.healthTitle": "Proxy Health",
    "proxy.assignmentsKicker": "Assignments",
    "proxy.assignmentsTitle": "Account Assignments",
    "proxy.providersKicker": "Providers",
    "proxy.providersTitle": "Relay Providers",
    "usage.eyebrow": "Analytics",
    "usage.title": "Usage Stats",
    "usage.subtitle": "Token and request history with a tighter visual hierarchy for trend reading.",
    "usage.refresh": "Refresh Usage",
    "usage.inputTokens": "Input Tokens",
    "usage.outputTokens": "Output Tokens",
    "usage.requests": "Requests",
    "usage.trackedAccounts": "Tracked Accounts",
    "usage.trackedAccountsMeta": "Accounts with recorded usage snapshots",
    "usage.latestTotal": "Latest total across tracked accounts",
    "usage.timelineKicker": "Timeline",
    "usage.timelineTitle": "Usage Timeline",
    "usage.hourly": "Hourly",
    "usage.daily": "Daily",
    "usage.feedKicker": "Recent Points",
    "usage.feedTitle": "Usage Feed",
    "common.loading": "Loading...",
    "common.idle": "Idle",
    "common.yes": "yes",
    "common.no": "no",
    "common.unknown": "unknown",
    "common.none": "none",
    "common.copyUrl": "Copy URL",
    "common.copied": "Copied",
    "common.copyFailed": "Copy failed",
    "common.refreshed": "Refreshed",
    "common.noData": "No data",
    "common.limitReached": "Limit reached",
    "common.active": "active",
    "common.critical": "critical",
    "common.warning": "warning",
    "common.model": "Model",
    "common.prompt": "Prompt",
    "common.cached": "Cached",
    "common.window": "Window",
    "common.reset": "Reset",
    "common.remaining": "In",
    "common.status": "Status",
    "common.plan": "Plan",
    "common.updated": "Updated",
    "common.account": "Account",
    "common.routing": "Routing",
    "common.quota": "Quota",
    "warning.banner.title": "Quota and runtime warnings need attention",
    "warning.banner.subtitle": "{total} active warning(s) across {activeCount} active account(s).",
    "warning.banner.warnings": "Warnings",
    "warning.banner.activeAccounts": "Active Accounts",
    "summary.active": "{count} active",
    "summary.critical": "{count} critical",
    "summary.websocket": "{state} websocket",
    "summary.relayProviders": "{count} relay provider(s)",
    "badge.rotation": "Rotation",
    "badge.responses": "Responses",
    "badge.backend": "Backend",
    "badge.websocket": "WebSocket",
    "badge.proxyHealth": "Proxy Health",
    "badge.lastHit": "Last Hit",
    "badge.allClear": "all clear",
    "badge.degraded": "{count} degraded",
    "status.authenticated": "Authenticated",
    "status.passwordRequired": "Password Required",
    "status.localDashboardBypass": "Local Dashboard Bypass",
    "status.accounts": "Accounts",
    "status.proxies": "Proxies",
    "status.relayProviders": "Relay Providers",
    "status.usageDataPoints": "Usage Data Points",
    "status.backgroundJobs": "Background Jobs",
    "status.enabled": "enabled",
    "status.disabled": "disabled",
    "status.noneRegistered": "none registered",
    "api.openaiChat": "OpenAI Chat",
    "api.anthropicMessages": "Anthropic Messages",
    "api.gemini": "Gemini",
    "api.codexResponses": "Codex Responses",
    "codexApp.noMatchedAccount": "No matched local account",
    "codexApp.authFile": "Auth File",
    "codexApp.currentAccount": "Current Account",
    "codexApp.entryId": "Entry ID",
    "codexApp.accountId": "Account ID",
    "codexApp.identityKey": "Identity Key",
    "codexApp.reservedInApiPool": "Reserved In API Pool",
    "codexApp.applyMode": "Apply Mode",
    "codexApp.applyModeValue": "Write auth.json only, then restart Codex App manually",
    "codexApp.externalChange": "External Change",
    "codexApp.detected": "Detected",
    "warnings.empty": "No quota warnings right now.",
    "recentRequests.empty": "No requests recorded yet.",
    "recentRequests.cache": "Cache",
    "recentRequests.completed": "completed",
    "recentRequests.noModel": "—",
    "accountFilter.all": "All Accounts",
    "accountFilter.active": "Active",
    "accountFilter.warned": "Warned",
    "accountFilter.rateLimited": "Rate Limited",
    "accountFilter.expired": "Expired",
    "accountFilter.banned": "Banned",
    "accountFilter.disabled": "Disabled",
    "accounts.empty": "No accounts match the current filter.",
    "accounts.proxyTrafficChanged": "Quota changed, but proxy traffic is not tracked here",
    "accounts.noUsageYet": "No usage yet",
    "accounts.codexCurrent": "Codex App Current",
    "accounts.codexReserved": "Reserved From codex2api",
    "accounts.proxyMode": "Proxy Mode: {value}",
    "accounts.assignedProxy": "Assigned Proxy: {value}",
    "accounts.currentCodexButton": "Current Codex App Account",
    "accounts.setCodexButton": "Set As Codex App Account",
    "accounts.proxyTraffic": "Proxy Traffic",
    "accounts.quotaWindow": "Quota Window",
    "accounts.secondaryWindow": "Secondary Window",
    "accounts.usedPercent": "{value}% used",
    "proxy.summary.proxies": "Proxies",
    "proxy.summary.active": "Active",
    "proxy.summary.degraded": "Degraded",
    "proxy.groups.all": "All Accounts",
    "proxy.groups.global": "Global Default",
    "proxy.groups.direct": "Direct",
    "proxy.groups.auto": "Auto",
    "proxy.groups.accountCount": "{count} account(s)",
    "proxy.empty": "No proxies configured.",
    "proxy.exitIp": "Exit IP",
    "proxy.latency": "Latency",
    "proxy.assignments.empty": "No accounts in the current proxy group.",
    "proxy.table.account": "Account",
    "proxy.table.status": "Status",
    "proxy.table.plan": "Plan",
    "proxy.table.routing": "Routing",
    "proxy.table.quota": "Quota",
    "proxy.table.updated": "Updated",
    "relays.empty": "No relay providers configured.",
    "usage.feed.empty": "No usage data yet.",
    "usage.feed.input": "Input",
    "usage.feed.output": "Output",
    "usage.feed.requests": "Requests",
    "usage.chart.empty": "No usage history yet.",
    "usage.chart.inputLegend": "Input Tokens",
    "usage.chart.outputLegend": "Output Tokens",
    "usage.chart.requestsLegend": "Requests",
    "login.starting": "Starting browser login...",
    "login.redirectUri": "Redirect URI: {value}",
    "login.callbackReady": "Local callback server is ready on localhost:1455.",
    "login.callbackUnavailable": "Local callback server unavailable: {error}",
    "login.popupOpen": "A popup should open for OAuth login.",
    "login.autoRefresh": "If the popup completes, the account list will refresh automatically.",
    "login.manualPaste": "If the popup cannot finish automatically, paste the callback URL below and click Complete Login.",
    "login.popupBlocked": "Popup was blocked. Open the authorize URL manually, then paste the callback URL below.",
    "login.pasteCallbackFirst": "Paste the localhost callback URL first.",
    "login.completing": "Completing login...",
    "connection.running": "Running...",
    "settings.saving": "Saving...",
    "jobs.running": "Running {job}...",
    "codexApp.switchFailed": "Switch Failed",
    "oauth.complete": "OAuth login complete. Refreshing account list...",
    "oauth.failed": "OAuth login failed"
  },
};

function normalizeLanguage(value) {
  return value === "en" ? "en" : "zh-CN";
}

function t(key, vars = {}) {
  const language = normalizeLanguage(uiState.language);
  const messages = TRANSLATIONS[language] || TRANSLATIONS["zh-CN"];
  const fallback = TRANSLATIONS.en || {};
  let template = messages[key] ?? fallback[key] ?? key;
  Object.entries(vars).forEach(([name, value]) => {
    template = template.replaceAll(`{${name}}`, String(value));
  });
  return template;
}

function applyStaticTranslations() {
  document.documentElement.lang = normalizeLanguage(uiState.language);
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.getAttribute("data-i18n") || "");
  });
  document.querySelectorAll("[data-i18n-html]").forEach((node) => {
    node.innerHTML = t(node.getAttribute("data-i18n-html") || "");
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.setAttribute("placeholder", t(node.getAttribute("data-i18n-placeholder") || ""));
  });
  const titleNode = document.querySelector("title[data-i18n]");
  if (titleNode) {
    titleNode.textContent = t(titleNode.getAttribute("data-i18n") || "");
  }
  const selector = document.querySelector("#language-select");
  if (selector instanceof HTMLSelectElement) {
    selector.value = normalizeLanguage(uiState.language);
  }
}

function preferredLanguage() {
  try {
    return normalizeLanguage(window.localStorage.getItem(LANGUAGE_STORAGE_KEY) || "zh-CN");
  } catch {
    return "zh-CN";
  }
}

async function loadJson(url) {
  const response = await fetch(url, { credentials: "same-origin", cache: "no-store" });
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    return { ok: response.ok, status: response.status, error: text || `HTTP ${response.status}` };
  }
}

async function postJson(url, payload = {}) {
  const response = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    return { ok: response.ok, status: response.status, error: text || `HTTP ${response.status}` };
  }
}

async function deleteJson(url) {
  const response = await fetch(url, {
    method: "DELETE",
    credentials: "same-origin",
  });
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    return { ok: response.ok, status: response.status, error: text || `HTTP ${response.status}` };
  }
}

function prettyJson(value) {
  return JSON.stringify(value, null, 2);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatNumber(value) {
  const number = Number(value || 0);
  if (!Number.isFinite(number)) {
    return "-";
  }
  if (Math.abs(number) >= 1_000_000) {
    return `${(number / 1_000_000).toFixed(1)}M`;
  }
  if (Math.abs(number) >= 1_000) {
    return `${(number / 1_000).toFixed(1)}K`;
  }
  return String(Math.round(number));
}

function formatDateTime(value) {
  if (!value) {
    return "—";
  }
  const numeric = typeof value === "number" ? value : Number(value);
  const timestamp = Number.isFinite(numeric) && String(value).trim() !== "" ? (numeric < 1_000_000_000_000 ? numeric * 1000 : numeric) : value;
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return new Intl.DateTimeFormat(uiState.language === "en" ? "en-US" : "zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatDurationCompact(value) {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return "—";
  }
  const totalSeconds = Math.round(numeric);
  const units =
    uiState.language === "en"
      ? { day: "d", hour: "h", minute: "m", second: "s" }
      : { day: "天", hour: "小时", minute: "分", second: "秒" };
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  if (days > 0) {
    return hours > 0 ? `${days}${units.day} ${hours}${units.hour}` : `${days}${units.day}`;
  }
  if (hours > 0) {
    return minutes > 0 ? `${hours}${units.hour} ${minutes}${units.minute}` : `${hours}${units.hour}`;
  }
  if (minutes > 0) {
    return `${minutes}${units.minute}`;
  }
  return `${totalSeconds}${units.second}`;
}

function formatTimeOnly(value) {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return new Intl.DateTimeFormat(uiState.language === "en" ? "en-US" : "zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function statusTone(status) {
  if (["active", "ok", "enabled"].includes(status)) {
    return "good";
  }
  if (["rate_limited", "warning", "unreachable", "refreshing"].includes(status)) {
    return "warn";
  }
  if (["expired", "banned", "error", "disabled"].includes(status)) {
    return "danger";
  }
  return "";
}

function quotaSummary(account) {
  const quota = account?.quota || {};
  const limit = quota?.rate_limit || {};
  const primary = limit?.primary_window || limit;
  const secondary = quota?.secondary_rate_limit || limit?.secondary_window || {};
  const usedPercentRaw = primary?.used_percent ?? quota?.used_percent ?? limit?.used_percent;
  const secondaryUsedPercentRaw = secondary?.used_percent;
  const usedPercent = Number(usedPercentRaw);
  const secondaryUsedPercent = Number(secondaryUsedPercentRaw);
  const isValid = Number.isFinite(usedPercent);
  const isSecondaryValid = Number.isFinite(secondaryUsedPercent);
  const tone = !isValid ? "" : usedPercent >= 90 ? "danger" : usedPercent >= 60 ? "warn" : "";
  return {
    usedPercent: isValid ? Math.max(0, Math.min(100, Math.round(usedPercent * (usedPercent > 1 ? 1 : 100)))) : null,
    secondaryUsedPercent: isSecondaryValid
      ? Math.max(0, Math.min(100, Math.round(secondaryUsedPercent * (secondaryUsedPercent > 1 ? 1 : 100))))
      : null,
    tone,
    resetAt: primary?.reset_at || limit?.reset_at || "",
    resetAfterSeconds: primary?.reset_after_seconds ?? quota?.reset_after_seconds ?? limit?.reset_after_seconds ?? "",
    limitWindowSeconds: primary?.limit_window_seconds ?? quota?.limit_window_seconds ?? limit?.limit_window_seconds ?? "",
    secondaryResetAt: secondary?.reset_at || "",
    secondaryResetAfterSeconds: secondary?.reset_after_seconds ?? "",
    secondaryLimitWindowSeconds: secondary?.limit_window_seconds ?? "",
    limitReached: Boolean(primary?.limit_reached || limit?.limit_reached),
    allowed: quota?.allowed ?? limit?.allowed,
    planType: quota?.plan_type || account?.plan_type || "",
  };
}

function accountUsageSummary(account) {
  const usage = account?.usage || {};
  const input = Number(usage.input_tokens || usage.window_input_tokens || 0);
  const output = Number(usage.output_tokens || usage.window_output_tokens || 0);
  const requests = Number(usage.request_count || usage.window_request_count || 0);
  return {
    requests,
    tokens: input + output,
    input,
    output,
  };
}

function summarizeStatus(status, runtime) {
  return {
    authenticated: status.authenticated,
    password_required: status.password_required,
    local_dashboard_bypass: status.local_dashboard_bypass,
    accounts: status.accounts,
    proxies: status.proxies,
    relay_providers: status.relay_providers,
    rotation_mode: status.rotation_mode,
    responses_transport: status.responses_transport,
    transport_backend: status.transport_backend,
    websocket_transport_available: status.websocket_transport_available,
    warnings: status.warnings,
    account_statuses: status.account_statuses,
    background_jobs: runtime.background?.jobs || {},
  };
}

function currentBaseUrl() {
  return window.location.origin.replace(/\/$/, "");
}

function setHtml(selector, html) {
  const node = document.querySelector(selector);
  if (node) {
    node.innerHTML = html;
  }
}

function setText(selector, text) {
  const node = document.querySelector(selector);
  if (node) {
    node.textContent = text;
  }
}

function renderBadge(label, value, tone = "") {
  return `<span class="badge ${tone}">${escapeHtml(label)}: ${escapeHtml(value)}</span>`;
}

function renderEmpty(message) {
  return `<div class="list-item"><span>${escapeHtml(message)}</span></div>`;
}

function applyViewFromHash() {
  const hash = window.location.hash || "#/";
  if (hash === "#/proxy-settings") {
    uiState.view = "proxy-settings";
  } else if (hash === "#/usage-stats") {
    uiState.view = "usage-stats";
  } else {
    uiState.view = "overview";
  }

  document.querySelectorAll("[data-view-panel]").forEach((panel) => {
    panel.classList.toggle("is-active", panel.getAttribute("data-view-panel") === uiState.view);
  });
  document.querySelectorAll("[data-view-link]").forEach((link) => {
    link.classList.toggle("is-active", link.getAttribute("data-view-link") === uiState.view);
  });
}

function renderWarningBanner(status) {
  const total = Number(status?.warnings?.total || 0);
  if (!total) {
    setHtml("#warning-banner", "");
    return;
  }
  const activeCount = Number(status?.account_statuses?.active || 0);
  setHtml(
    "#warning-banner",
    `<article class="warning-banner">
      <div>
        <h2>${escapeHtml(t("warning.banner.title"))}</h2>
        <p class="subcopy small">${escapeHtml(t("warning.banner.subtitle", { total, activeCount }))}</p>
      </div>
      <div class="badge-row">
        ${renderBadge(t("warning.banner.warnings"), total, "warn")}
        ${renderBadge(t("warning.banner.activeAccounts"), activeCount, "good")}
      </div>
    </article>`,
  );
}

function applySummary(status, runtime, usage, accountsPayload, proxiesPayload, relaysPayload, recentRequestsPayload) {
  const summary = summarizeStatus(status, runtime);
  const accounts = accountsPayload.data || [];
  const proxies = proxiesPayload.data || [];
  const relayProviders = relaysPayload.data || [];
  const recentRequests = recentRequestsPayload.data || [];
  const activeAccounts = accounts.filter((account) => account.status === "active").length;
  const unhealthyProxies = proxies.filter((proxy) => proxy.status && proxy.status !== "active").length;
  const websocketLabel = summary.websocket_transport_available ? (uiState.language === "en" ? "ready" : "就绪") : (uiState.language === "en" ? "fallback" : "回退");
  const latestRequest = recentRequests[0] || null;

  setText("#stat-accounts", String(summary.accounts ?? 0));
  setText("#stat-accounts-meta", t("summary.active", { count: activeAccounts }));
  setText("#stat-warnings", String(summary.warnings?.total ?? 0));
  setText("#stat-warnings-meta", t("summary.critical", { count: summary.warnings?.critical ?? 0 }));
  setText("#stat-transport", String(summary.transport_backend ?? "-"));
  setText("#stat-transport-meta", t("summary.websocket", { state: websocketLabel }));
  setText("#stat-responses-transport", String(summary.responses_transport ?? "-"));
  setText("#stat-responses-transport-meta", t("summary.relayProviders", { count: relayProviders.length }));

  setHtml(
    "#runtime-badges",
    [
      renderBadge(t("badge.rotation"), summary.rotation_mode || "-", "good"),
      renderBadge(t("badge.responses"), summary.responses_transport || "-", summary.responses_transport === "websocket" ? "good" : ""),
      renderBadge(t("badge.backend"), summary.transport_backend || "direct", ""),
      renderBadge(t("badge.websocket"), websocketLabel, summary.websocket_transport_available ? "good" : "warn"),
      renderBadge(t("badge.proxyHealth"), unhealthyProxies ? t("badge.degraded", { count: unhealthyProxies }) : t("badge.allClear"), unhealthyProxies ? "warn" : "good"),
      latestRequest ? renderBadge(t("badge.lastHit"), latestRequest.account_name || t("common.unknown"), "good") : "",
      uiState.lastRefreshAt ? renderBadge(t("common.refreshed"), formatTimeOnly(uiState.lastRefreshAt), "") : "",
    ].join(""),
  );

  const detailRows = [
    [t("status.authenticated"), summary.authenticated ? t("common.yes") : t("common.no")],
    [t("status.passwordRequired"), summary.password_required ? t("common.yes") : t("common.no")],
    [t("status.localDashboardBypass"), summary.local_dashboard_bypass ? t("status.enabled") : t("status.disabled")],
    [t("status.accounts"), `${summary.accounts || 0}`],
    [t("status.proxies"), `${summary.proxies || 0}`],
    [t("status.relayProviders"), `${summary.relay_providers || 0}`],
    ["Managed API Keys", `${status.managed_api_keys || 0}`],
    ["API Key Required", status.api_key_required ? t("common.yes") : t("common.no")],
    [t("status.usageDataPoints"), `${usage.data_points || 0}`],
    [t("status.backgroundJobs"), Object.keys(summary.background_jobs || {}).length ? Object.keys(summary.background_jobs).join(", ") : t("status.noneRegistered")],
  ];
  setHtml(
    "#status-details",
    detailRows
      .map(
        ([label, value]) =>
          `<div class="detail-item"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(value)}</span></div>`,
      )
      .join(""),
  );

  renderWarningBanner(status);
  renderApiConfig();
}

function applySettings(rotation) {
  const rotationMode = rotation.rotation_mode || "least_used";
  const responsesTransport = rotation.responses_transport || "auto";
  const rotationField = document.querySelector("#rotation-mode");
  const responsesField = document.querySelector("#responses-transport");
  if (rotationField) {
    rotationField.value = rotationMode;
  }
  if (responsesField) {
    responsesField.value = responsesTransport;
  }
}

function renderApiConfig() {
  const baseUrl = currentBaseUrl();
  const items = [
    {
      label: t("api.openaiChat"),
      path: `${baseUrl}/v1/chat/completions`,
      snippet: `curl ${baseUrl}/v1/chat/completions`,
    },
    {
      label: t("api.anthropicMessages"),
      path: `${baseUrl}/v1/messages`,
      snippet: `curl ${baseUrl}/v1/messages`,
    },
    {
      label: t("api.gemini"),
      path: `${baseUrl}/v1beta/models/gemini-2.5-pro:generateContent`,
      snippet: `curl ${baseUrl}/v1beta/models/gemini-2.5-pro:generateContent`,
    },
    {
      label: t("api.codexResponses"),
      path: `${baseUrl}/v1/responses`,
      snippet: `curl ${baseUrl}/v1/responses`,
    },
  ];

  setHtml(
    "#api-config",
    items
      .map(
        (item) => `
          <article class="endpoint-item">
            <div class="endpoint-head">
              <strong>${escapeHtml(item.label)}</strong>
              <button class="copy-button" data-copy="${escapeHtml(item.path)}">${escapeHtml(t("common.copyUrl"))}</button>
            </div>
            <code>${escapeHtml(item.path)}</code>
            <code>${escapeHtml(item.snippet)}</code>
          </article>
        `,
      )
      .join(""),
  );
}

function renderCodexAppCard(accountsPayload) {
  const codexApp = accountsPayload.codex_app || {};
  const currentEntryId = codexApp.current_entry_id || "";
  const currentAccount = (accountsPayload.data || []).find((account) => account.entry_id === currentEntryId) || null;
  const selectionLabel = currentAccount
    ? currentAccount.email || currentAccount.entry_id
    : currentEntryId || t("codexApp.noMatchedAccount");
  const identifierRows = [
    [t("codexApp.entryId"), currentEntryId || "—"],
    [t("codexApp.accountId"), codexApp.current_account_id || "—"],
    [t("codexApp.identityKey"), codexApp.current_identity_key || "—"],
  ];
  const warning = codexApp.external_override_detected
    ? `<div class="badge-row inline-feedback">${renderBadge(t("codexApp.externalChange"), t("codexApp.detected"), "warn")}</div>`
    : "";

  setHtml(
    "#codex-app-card",
    `
      <div class="detail-item"><strong>${escapeHtml(t("codexApp.authFile"))}</strong><span>${escapeHtml(codexApp.auth_path || "~/.codex/auth.json")}</span></div>
      <div class="detail-item"><strong>${escapeHtml(t("codexApp.currentAccount"))}</strong><span>${escapeHtml(selectionLabel)}</span></div>
      ${identifierRows
        .map(
          ([label, value]) =>
            `<div class="detail-item"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(value)}</span></div>`,
        )
        .join("")}
      <div class="detail-item"><strong>${escapeHtml(t("codexApp.reservedInApiPool"))}</strong><span>${escapeHtml(currentEntryId ? t("common.yes") : t("common.no"))}</span></div>
      <div class="detail-item"><strong>${escapeHtml(t("codexApp.applyMode"))}</strong><span>${escapeHtml(t("codexApp.applyModeValue"))}</span></div>
      ${warning}
    `,
  );
}

function renderWarnings(accountsPayload) {
  const items = accountsPayload.warnings || [];
  if (!items.length) {
    setHtml("#warnings-list", renderEmpty(t("warnings.empty")));
    return;
  }
  setHtml(
    "#warnings-list",
    items
      .map((item) => {
        const warning = item.warning || item;
        const tone = warning.level === "error" ? "danger" : "warn";
        return `
          <article class="list-item">
            <div class="badge-row">
              ${renderBadge(item.account_id || "account", warning.warning_type || "warning", tone)}
            </div>
            <strong>${escapeHtml(warning.message || t("common.warning"))}</strong>
            <span>${escapeHtml(item.created_at || "")}</span>
          </article>
        `;
      })
      .join(""),
  );
}

function renderRecentRequests(recentRequestsPayload) {
  const items = recentRequestsPayload.data || [];
  if (!items.length) {
    setHtml("#recent-requests", renderEmpty(t("recentRequests.empty")));
    return;
  }
  setHtml(
    "#recent-requests",
    items
      .map((item) => {
        const rate =
          typeof item.cache_hit_rate === "number"
            ? `${item.cache_hit_rate.toFixed(2)}%`
            : item.prompt_tokens
              ? "0.00%"
              : "—";
        return `
          <article class="list-item">
            <div class="badge-row">
              ${renderBadge(item.account_name || t("common.unknown"), item.status || t("recentRequests.completed"), statusTone(item.status))}
              ${renderBadge(t("recentRequests.cache"), rate, typeof item.cache_hit_rate === "number" && item.cache_hit_rate > 0 ? "good" : "")}
            </div>
            <strong>${escapeHtml(item.path || "/")}</strong>
            <span>${escapeHtml(t("common.model"))}: ${escapeHtml(item.requested_model || t("recentRequests.noModel"))}</span>
            <span>${escapeHtml(t("common.prompt"))}: ${escapeHtml(formatNumber(item.prompt_tokens || 0))} | ${escapeHtml(t("common.cached"))}: ${escapeHtml(formatNumber(item.cached_tokens || 0))}</span>
            <span>${escapeHtml(formatDateTime(item.timestamp))}</span>
          </article>
        `;
      })
      .join(""),
  );
}

function renderAccountFilters(accountsPayload) {
  const accounts = accountsPayload.data || [];
  const warningsByAccount = new Set((accountsPayload.warnings || []).map((item) => item.account_id));
  const counts = new Map([["all", accounts.length], ["warned", 0]]);
  accounts.forEach((account) => {
    counts.set(account.status || "unknown", (counts.get(account.status || "unknown") || 0) + 1);
    if (warningsByAccount.has(account.entry_id)) {
      counts.set("warned", (counts.get("warned") || 0) + 1);
    }
  });

  const labels = [
    ["all", t("accountFilter.all")],
    ["active", t("accountFilter.active")],
    ["warned", t("accountFilter.warned")],
    ["rate_limited", t("accountFilter.rateLimited")],
    ["expired", t("accountFilter.expired")],
    ["banned", t("accountFilter.banned")],
    ["disabled", t("accountFilter.disabled")],
  ];

  setHtml(
    "#account-filters",
    labels
      .filter(([key]) => key === "all" || (counts.get(key) || 0) > 0)
      .map(
        ([key, label]) => `
          <button class="chip ${uiState.accountFilter === key ? "is-active" : ""}" data-account-filter="${escapeHtml(key)}">
            ${escapeHtml(label)}
            <strong>${escapeHtml(counts.get(key) || 0)}</strong>
          </button>
        `,
      )
      .join(""),
  );
}

function renderAccounts(accountsPayload) {
  renderCodexAppCard(accountsPayload);
  renderAccountFilters(accountsPayload);
  const accounts = accountsPayload.data || [];
  const warningsByAccount = new Set((accountsPayload.warnings || []).map((item) => item.account_id));
  const filtered = accounts.filter((account) => {
    if (uiState.accountFilter === "all") {
      return true;
    }
    if (uiState.accountFilter === "warned") {
      return warningsByAccount.has(account.entry_id);
    }
    return (account.status || "unknown") === uiState.accountFilter;
  });

  if (!filtered.length) {
    setHtml("#accounts-list", renderEmpty(t("accounts.empty")));
    return;
  }

  setHtml(
    "#accounts-list",
    filtered
      .map((account) => {
        const usage = accountUsageSummary(account);
        const quota = quotaSummary(account);
        const proxyAssignment = account.proxy_assignment?.proxy_id || account.proxy_id || "—";
        const proxyMode = account.proxy_mode || "global";
        const proxyTrafficText =
          usage.requests || usage.tokens
            ? `${formatNumber(usage.requests)} req / ${formatNumber(usage.tokens)} tok`
            : quota.usedPercent && quota.usedPercent > 0
              ? t("accounts.proxyTrafficChanged")
              : t("accounts.noUsageYet");
        return `
          <article class="account-card">
            <div class="account-card-header">
              <div>
                <strong>${escapeHtml(account.email || account.entry_id)}</strong>
                <small>${escapeHtml(account.entry_id)}</small>
              </div>
              ${renderBadge(account.status || "unknown", account.plan_type || "free", statusTone(account.status))}
            </div>

            <div class="meta-row">
              ${account.is_codex_app_current ? `<span class="soft-pill">${escapeHtml(t("accounts.codexCurrent"))}</span>` : ""}
              ${account.is_codex_app_reserved ? `<span class="soft-pill">${escapeHtml(t("accounts.codexReserved"))}</span>` : ""}
              <span class="soft-pill">${escapeHtml(t("accounts.proxyMode", { value: proxyMode }))}</span>
              <span class="soft-pill">${escapeHtml(t("accounts.assignedProxy", { value: proxyAssignment }))}</span>
              <span class="muted">${escapeHtml(t("common.updated"))} ${escapeHtml(formatDateTime(account.updated_at))}</span>
            </div>

            <div class="meta-row">
              <button
                class="action secondary"
                type="button"
                data-codex-app-select="${escapeHtml(account.entry_id)}"
                ${account.is_codex_app_current ? "disabled" : ""}
              >${account.is_codex_app_current ? escapeHtml(t("accounts.currentCodexButton")) : escapeHtml(t("accounts.setCodexButton"))}</button>
            </div>

            <div class="metric-grid">
              <div class="metric">
                <span>${escapeHtml(t("common.plan"))}</span>
                <strong>${escapeHtml(quota.planType || account.plan_type || "—")}</strong>
              </div>
              <div class="metric">
                <span>${escapeHtml(t("accounts.proxyTraffic"))}</span>
                <strong>${escapeHtml(proxyTrafficText)}</strong>
              </div>
            </div>

            <div class="meter">
              <div class="meter-head">
                <span>${escapeHtml(t("accounts.quotaWindow"))}</span>
                <strong>${quota.limitReached ? escapeHtml(t("common.limitReached")) : quota.usedPercent == null ? escapeHtml(t("common.noData")) : escapeHtml(t("accounts.usedPercent", { value: quota.usedPercent }))}</strong>
              </div>
              <div class="meter-track">
                <div class="meter-fill ${quota.tone}" style="width: ${quota.usedPercent ?? 8}%"></div>
              </div>
              <div class="muted meter-meta">${escapeHtml(t("common.window"))}: ${escapeHtml(formatDurationCompact(quota.limitWindowSeconds))} • ${escapeHtml(t("common.reset"))}: ${escapeHtml(formatDateTime(quota.resetAt))} • ${escapeHtml(t("common.remaining"))}: ${escapeHtml(formatDurationCompact(quota.resetAfterSeconds))}</div>
            </div>

            ${
              quota.secondaryUsedPercent == null
                ? ""
                : `
              <div class="meter">
                <div class="meter-head">
                  <span>${escapeHtml(t("accounts.secondaryWindow"))}</span>
                  <strong>${escapeHtml(t("accounts.usedPercent", { value: quota.secondaryUsedPercent }))}</strong>
                </div>
                <div class="meter-track">
                  <div class="meter-fill" style="width: ${quota.secondaryUsedPercent}%"></div>
                </div>
                <div class="muted meter-meta">${escapeHtml(t("common.window"))}: ${escapeHtml(formatDurationCompact(quota.secondaryLimitWindowSeconds))} • ${escapeHtml(t("common.reset"))}: ${escapeHtml(formatDateTime(quota.secondaryResetAt))} • ${escapeHtml(t("common.remaining"))}: ${escapeHtml(formatDurationCompact(quota.secondaryResetAfterSeconds))}</div>
              </div>
            `
            }
          </article>
        `;
      })
      .join(""),
  );
}

function renderProxySummary(proxiesPayload) {
  const proxies = proxiesPayload.data || [];
  const active = proxies.filter((proxy) => proxy.status === "active").length;
  const unhealthy = proxies.filter((proxy) => proxy.status !== "active").length;
  setHtml(
    "#proxy-summary-badges",
    [
      renderBadge(t("proxy.summary.proxies"), proxies.length, "good"),
      renderBadge(t("proxy.summary.active"), active, active ? "good" : ""),
      renderBadge(t("proxy.summary.degraded"), unhealthy, unhealthy ? "warn" : ""),
    ].join(""),
  );
}

function renderProxyGroups(accountsPayload, proxiesPayload) {
  const accounts = accountsPayload.data || [];
  const proxies = proxiesPayload.data || [];
  const countForGroup = (group) =>
    accounts.filter((account) => proxyGroupMatches(account, group)).length;
  const groups = [
    { id: "__all__", label: t("proxy.groups.all"), count: accounts.length },
    { id: "global", label: t("proxy.groups.global"), count: countForGroup("global") },
    { id: "direct", label: t("proxy.groups.direct"), count: countForGroup("direct") },
    { id: "auto", label: t("proxy.groups.auto"), count: countForGroup("auto") },
    ...proxies.map((proxy) => ({
      id: proxy.proxy_id,
      label: proxy.name || proxy.proxy_id,
      count: countForGroup(proxy.proxy_id),
      meta: proxy.health?.exit_ip || proxy.health?.exitIp || proxy.status || "",
    })),
  ];
  setHtml(
    "#proxy-groups",
    groups
      .map(
        (group) => `
          <button class="group-button ${uiState.proxyGroup === group.id ? "is-active" : ""}" data-proxy-group="${escapeHtml(group.id)}">
            <span>
              <strong>${escapeHtml(group.label)}</strong>
              <small>${escapeHtml(group.meta || t("proxy.groups.accountCount", { count: group.count }))}</small>
            </span>
            <strong>${escapeHtml(group.count)}</strong>
          </button>
        `,
      )
      .join(""),
  );
}

function proxyGroupMatches(account, group) {
  if (group === "__all__") {
    return true;
  }
  const proxyMode = account.proxy_mode || "global";
  const assignedProxy = account.proxy_assignment?.proxy_id || account.proxy_id || "";
  if (["global", "direct", "auto"].includes(group)) {
    return proxyMode === group;
  }
  return assignedProxy === group;
}

function renderProxies(proxyPayload) {
  renderProxySummary(proxyPayload);
  renderProxyGroups(uiState.data.accounts, proxyPayload);
  const proxies = proxyPayload.data || [];
  if (!proxies.length) {
    setHtml("#proxies-list", renderEmpty(t("proxy.empty")));
    return;
  }
  setHtml(
    "#proxies-list",
    proxies
      .map((proxy) => {
        const exitIp = proxy.health?.exit_ip || proxy.health?.exitIp || "—";
        const latency = proxy.health?.latency_ms ?? "—";
        const detail = proxy.health?.error || proxy.url || "";
        return `
          <article class="proxy-card">
            <div class="proxy-card-header">
              <div>
                <strong>${escapeHtml(proxy.name || proxy.proxy_id)}</strong>
                <small>${escapeHtml(proxy.proxy_id)}</small>
              </div>
              ${renderBadge(t("common.status"), proxy.status || t("common.unknown"), statusTone(proxy.status))}
            </div>
            <div class="metric-grid">
              <div class="metric">
                <span>${escapeHtml(t("proxy.exitIp"))}</span>
                <strong>${escapeHtml(exitIp)}</strong>
              </div>
              <div class="metric">
                <span>${escapeHtml(t("proxy.latency"))}</span>
                <strong>${escapeHtml(`${latency} ms`)}</strong>
              </div>
            </div>
            <div class="meta-row">
              <span class="muted">${escapeHtml(proxy.url || "")}</span>
              <span class="muted">${escapeHtml(detail)}</span>
            </div>
          </article>
        `;
      })
      .join(""),
  );
}

function renderProxyAssignments(accountsPayload) {
  const accounts = (accountsPayload.data || []).filter((account) => proxyGroupMatches(account, uiState.proxyGroup));
  if (!accounts.length) {
    setHtml("#proxy-accounts-table", renderEmpty(t("proxy.assignments.empty")));
    return;
  }

  setHtml(
    "#proxy-accounts-table",
    `<table>
      <thead>
        <tr>
          <th>${escapeHtml(t("proxy.table.account"))}</th>
          <th>${escapeHtml(t("proxy.table.status"))}</th>
          <th>${escapeHtml(t("proxy.table.plan"))}</th>
          <th>${escapeHtml(t("proxy.table.routing"))}</th>
          <th>${escapeHtml(t("proxy.table.quota"))}</th>
          <th>${escapeHtml(t("proxy.table.updated"))}</th>
        </tr>
      </thead>
      <tbody>
        ${accounts
          .map((account) => {
            const quota = quotaSummary(account);
            const routing = `${account.proxy_mode || "global"} / ${account.proxy_assignment?.proxy_id || account.proxy_id || "—"}`;
            return `
              <tr>
                <td>
                  <strong>${escapeHtml(account.email || account.entry_id)}</strong><br />
                  <span class="muted">${escapeHtml(account.entry_id)}</span>
                </td>
                <td>${renderBadge(t("common.status"), account.status || t("common.unknown"), statusTone(account.status))}</td>
                <td>${escapeHtml(account.plan_type || "—")}</td>
                <td>${escapeHtml(routing)}</td>
                <td>${escapeHtml(quota.usedPercent == null ? t("common.noData") : `${quota.usedPercent}%`)}</td>
                <td>${escapeHtml(formatDateTime(account.updated_at))}</td>
              </tr>
            `;
          })
          .join("")}
      </tbody>
    </table>`,
  );
}

function renderRelays(relaysPayload) {
  const relays = relaysPayload.data || [];
  if (!relays.length) {
    setHtml("#relay-list", renderEmpty(t("relays.empty")));
    return;
  }
  setHtml(
    "#relay-list",
    relays
      .map(
        (relay) => `
          <article class="list-item">
            <div class="badge-row">
              ${renderBadge(relay.name || relay.provider_id, relay.format || "responses", relay.enabled ? "good" : "danger")}
            </div>
            <strong>${escapeHtml(relay.base_url || "")}</strong>
            <span>${escapeHtml(relay.provider_id || "")}</span>
          </article>
        `,
      )
      .join(""),
  );
}

function renderApiKeys(apiKeysPayload) {
  const items = apiKeysPayload?.data || [];
  if (!items.length) {
    setHtml("#api-key-list", renderEmpty("暂无 API Key。创建后将自动启用鉴权。"));
    return;
  }
  setHtml(
    "#api-key-list",
    items
      .map(
        (item) => `
          <article class="list-item">
            <div class="badge-row">
              ${renderBadge(item.name || item.key_id, item.enabled ? "enabled" : "disabled", item.enabled ? "good" : "warn")}
              ${renderBadge("Requests", formatNumber(item.request_count || 0), "")}
            </div>
            <strong>${escapeHtml(item.key_prefix || "")}…</strong>
            <span>Key: <code>${escapeHtml(item.api_key || "")}</code></span>
            <span>Input: ${escapeHtml(formatNumber(item.input_tokens || 0))} | Output: ${escapeHtml(formatNumber(item.output_tokens || 0))}</span>
            <span>Success: ${escapeHtml(formatNumber(item.success_count || 0))} | Failed: ${escapeHtml(formatNumber(item.failure_count || 0))}</span>
            <span>Last Used: ${escapeHtml(formatDateTime(item.last_used_at || ""))}</span>
            <div class="meta-row">
              <button class="action secondary" type="button" data-api-key-delete="${escapeHtml(item.key_id)}">删除</button>
            </div>
          </article>
        `,
      )
      .join(""),
  );
}

function applyUsageSummary(usage) {
  setText("#usage-total-input", formatNumber(usage.total_input_tokens || 0));
  setText("#usage-total-output", formatNumber(usage.total_output_tokens || 0));
  setText("#usage-total-requests", formatNumber(usage.total_request_count || 0));
  setText("#usage-account-count", formatNumber(usage.account_count || 0));
}

function renderUsageFeed(points) {
  if (!points.length) {
    setHtml("#usage-feed", renderEmpty(t("usage.feed.empty")));
    return;
  }
  setHtml(
    "#usage-feed",
    points
      .slice(-8)
      .reverse()
      .map(
        (point) => `
          <article class="list-item">
            <strong>${escapeHtml(formatDateTime(point.timestamp))}</strong>
            <span>${escapeHtml(t("usage.feed.input"))}: ${escapeHtml(formatNumber(point.input_tokens || 0))}</span>
            <span>${escapeHtml(t("usage.feed.output"))}: ${escapeHtml(formatNumber(point.output_tokens || 0))}</span>
            <span>${escapeHtml(t("usage.feed.requests"))}: ${escapeHtml(formatNumber(point.request_count || 0))}</span>
          </article>
        `,
      )
      .join(""),
  );
}

function renderUsageControls() {
  document.querySelectorAll("[data-granularity]").forEach((button) => {
    button.classList.toggle("is-active", button.getAttribute("data-granularity") === uiState.usageGranularity);
  });
  document.querySelectorAll("[data-hours]").forEach((button) => {
    button.classList.toggle("is-active", Number(button.getAttribute("data-hours")) === uiState.usageHours);
  });
}

function buildPolyline(points, width, height, getter) {
  if (!points.length) {
    return "";
  }
  const values = points.map((point) => Number(getter(point) || 0));
  const maxValue = Math.max(...values, 1);
  const xStep = points.length === 1 ? 0 : width / (points.length - 1);
  return points
    .map((point, index) => {
      const value = Number(getter(point) || 0);
      const x = index * xStep;
      const y = height - (value / maxValue) * height;
      return `${x},${y}`;
    })
    .join(" ");
}

function renderUsageChart(points) {
  if (!points.length) {
    setHtml("#usage-chart", `<div class="chart-empty">${escapeHtml(t("usage.chart.empty"))}</div>`);
    return;
  }

  const width = 720;
  const height = 220;
  const requestHeight = 150;
  const inputLine = buildPolyline(points, width, height, (point) => point.input_tokens);
  const outputLine = buildPolyline(points, width, height, (point) => point.output_tokens);
  const requestLine = buildPolyline(points, width, requestHeight, (point) => point.request_count);
  const labelStep = Math.max(1, Math.floor(points.length / 5));
  const xLabels = points
    .map((point, index) => ({ point, index }))
    .filter(({ index }) => index % labelStep === 0 || index === points.length - 1)
    .map(({ point, index }) => {
      const x = (index / Math.max(points.length - 1, 1)) * width;
      return `<text x="${x}" y="${height - 4}" text-anchor="middle" fill="#73847d" font-size="10">${escapeHtml(formatDateTime(point.timestamp))}</text>`;
    })
    .join("");

  setHtml(
    "#usage-chart",
    `<div class="chart-legend">
      <span><span class="legend-line input"></span> ${escapeHtml(t("usage.chart.inputLegend"))}</span>
      <span><span class="legend-line output"></span> ${escapeHtml(t("usage.chart.outputLegend"))}</span>
      <span><span class="legend-line requests"></span> ${escapeHtml(t("usage.chart.requestsLegend"))}</span>
    </div>
    <svg viewBox="0 0 ${width} ${height}" class="chart-svg">
      <polyline points="${inputLine}" fill="none" stroke="#3b82f6" stroke-width="3" stroke-linejoin="round"></polyline>
      <polyline points="${outputLine}" fill="none" stroke="#10b981" stroke-width="3" stroke-linejoin="round"></polyline>
      ${xLabels}
    </svg>
    <svg viewBox="0 0 ${width} ${requestHeight}" class="chart-svg-secondary">
      <polyline points="${requestLine}" fill="none" stroke="#f59e0b" stroke-width="3" stroke-linejoin="round"></polyline>
    </svg>`,
  );
}

async function loadDashboardData() {
  const historyUrl = `/admin/usage-stats/history?granularity=${encodeURIComponent(uiState.usageGranularity)}&hours=${encodeURIComponent(
    String(uiState.usageHours),
  )}`;
  const [status, runtime, rotation, usage, apiKeys, accounts, proxies, relays, usageHistory, recentRequests] = await Promise.all([
    loadJson(endpoints.status),
    loadJson(endpoints.runtime),
    loadJson(endpoints.rotation),
    loadJson(endpoints.usage),
    loadJson(endpoints.apiKeys),
    loadJson(endpoints.accounts),
    loadJson(endpoints.proxies),
    loadJson(endpoints.relays),
    loadJson(historyUrl),
    loadJson(endpoints.recentRequests),
  ]);
  uiState.lastRefreshAt = new Date().toISOString();
  uiState.data = { status, runtime, rotation, usage, apiKeys, accounts, proxies, relays, usageHistory, recentRequests };
  return uiState.data;
}

function renderDashboard() {
  const { status, runtime, rotation, usage, apiKeys, accounts, proxies, relays, usageHistory, recentRequests } = uiState.data;
  applyViewFromHash();
  applySummary(status, runtime, usage, accounts, proxies, relays, recentRequests);
  applySettings(rotation);
  renderWarnings(accounts);
  renderRecentRequests(recentRequests);
  renderAccounts(accounts);
  renderApiKeys(apiKeys);
  renderProxies(proxies);
  renderProxyAssignments(accounts);
  renderRelays(relays);
  applyUsageSummary(usage);
  renderUsageControls();
  renderUsageFeed(usageHistory.data || []);
  renderUsageChart(usageHistory.data || []);
}

async function render() {
  await loadDashboardData();
  renderDashboard();
}

async function refreshDashboardSilently() {
  if (uiState.refreshInFlight || document.hidden) {
    return;
  }
  uiState.refreshInFlight = true;
  try {
    await loadDashboardData();
    renderDashboard();
  } finally {
    uiState.refreshInFlight = false;
  }
}

async function startOAuthLogin() {
  const button = document.querySelector("#start-login");
  const output = document.querySelector("#login-result");
  button.disabled = true;
  output.textContent = t("login.starting");
  try {
    const result = await postJson(endpoints.loginStart, { source: "dashboard" });
    if (result?.error) {
      output.textContent = prettyJson(result);
      return;
    }
    const callbackStatus = result.callback_server || {};
    const lines = [
      t("login.redirectUri", { value: result.redirect_uri || "—" }),
      callbackStatus.ok ? t("login.callbackReady") : t("login.callbackUnavailable", { error: callbackStatus.error || t("common.unknown") }),
      t("login.popupOpen"),
      callbackStatus.ok
        ? t("login.autoRefresh")
        : t("login.manualPaste"),
      "",
      `Authorize URL: ${result.authorize_url || ""}`,
    ];
    output.textContent = lines.join("\n");
    const popup = window.open(result.authorize_url, "codex2gpt-oauth", "popup=yes,width=560,height=760");
    if (!popup) {
      output.textContent += `\n\n${t("login.popupBlocked")}`;
    } else {
      uiState.authPopup = popup;
    }
  } catch (error) {
    output.textContent = prettyJson({ ok: false, error: String(error) });
  } finally {
    button.disabled = false;
  }
}

async function submitCallbackUrl() {
  const input = document.querySelector("#callback-url");
  const output = document.querySelector("#login-result");
  const callbackUrl = (input?.value || "").trim();
  if (!callbackUrl) {
    output.textContent = t("login.pasteCallbackFirst");
    return;
  }
  output.textContent = t("login.completing");
  try {
    const result = await postJson(endpoints.codeRelay, { callbackUrl });
    output.textContent = prettyJson(result);
    if (!result.error) {
      if (input) {
        input.value = "";
      }
      await render();
    }
  } catch (error) {
    output.textContent = prettyJson({ ok: false, error: String(error) });
  }
}

async function runConnectionTest() {
  const button = document.querySelector("#run-test");
  const output = document.querySelector("#connection-test");
  button.disabled = true;
  output.textContent = t("connection.running");
  try {
    const result = await postJson("/admin/test-connection", {});
    output.textContent = JSON.stringify(result, null, 2);
  } catch (error) {
    output.textContent = JSON.stringify({ ok: false, error: String(error) }, null, 2);
  } finally {
    button.disabled = false;
  }
}

async function saveRuntimeSettings(event) {
  event.preventDefault();
  const output = document.querySelector("#settings-result");
  output.textContent = t("settings.saving");
  const payload = {
    rotation_mode: document.querySelector("#rotation-mode").value,
    responses_transport: document.querySelector("#responses-transport").value,
  };
  const result = await postJson("/admin/rotation-settings", payload);
  output.textContent = JSON.stringify(result, null, 2);
  await render();
}

async function runJob(job) {
  const output = document.querySelector("#job-result");
  output.textContent = t("jobs.running", { job });
  const result = await postJson("/admin/runtime-jobs/run", { job });
  output.textContent = JSON.stringify(result, null, 2);
  await render();
}

async function createApiKey() {
  const nameInput = document.querySelector("#api-key-name");
  const output = document.querySelector("#api-key-result");
  const name = (nameInput?.value || "").trim();
  output.textContent = "正在创建 API Key...";
  const result = await postJson(endpoints.apiKeys, { name });
  output.textContent = JSON.stringify(result, null, 2);
  if (!result?.error) {
    if (nameInput) {
      nameInput.value = "";
    }
    await render();
  }
}

async function deleteApiKey(keyId) {
  const output = document.querySelector("#api-key-result");
  output.textContent = `正在删除 API Key: ${keyId}`;
  const result = await deleteJson(`/admin/api-keys/${encodeURIComponent(keyId)}`);
  output.textContent = JSON.stringify(result, null, 2);
  await render();
}

async function selectCodexAppAccount(entryId) {
  const result = await postJson(endpoints.codexAppSelect, { entry_id: entryId });
  const message = document.querySelector("#codex-app-card");
  if (result?.error) {
    if (message) {
      message.insertAdjacentHTML(
        "beforeend",
        `<div class="badge-row inline-feedback">${renderBadge(t("codexApp.switchFailed"), result.error.message || t("common.unknown"), "danger")}</div>`,
      );
    }
    return;
  }
  await render();
}

async function refreshUsage() {
  if (!uiState.data) {
    await render();
    return;
  }
  const historyUrl = `/admin/usage-stats/history?granularity=${encodeURIComponent(uiState.usageGranularity)}&hours=${encodeURIComponent(
    String(uiState.usageHours),
  )}`;
  uiState.data.usage = await loadJson(endpoints.usage);
  uiState.data.usageHistory = await loadJson(historyUrl);
  renderDashboard();
}

function wireEvents() {
  window.addEventListener("hashchange", () => {
    applyViewFromHash();
  });

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      refreshDashboardSilently().catch(() => {});
    }
  });

  window.setInterval(() => {
    refreshDashboardSilently().catch(() => {});
  }, uiState.autoRefreshMs);

  window.addEventListener("message", (event) => {
    const payload = event?.data;
    if (!payload || typeof payload !== "object") {
      return;
    }
    if (payload.type === "oauth-callback-success") {
      setText("#login-result", t("oauth.complete"));
      if (uiState.authPopup && !uiState.authPopup.closed) {
        try {
          uiState.authPopup.close();
        } catch (error) {}
      }
      uiState.authPopup = null;
      render().catch((error) => {
        setText("#login-result", prettyJson({ ok: false, error: String(error) }));
      });
      return;
    }
    if (payload.type === "oauth-callback-error") {
      setText("#login-result", prettyJson({ ok: false, error: payload.error || t("oauth.failed") }));
      return;
    }
  });

  document.querySelector("#run-test")?.addEventListener("click", () => {
    runConnectionTest().catch((error) => {
      document.querySelector("#connection-test").textContent = JSON.stringify({ ok: false, error: String(error) }, null, 2);
    });
  });

  document.querySelector("#start-login")?.addEventListener("click", () => {
    startOAuthLogin().catch((error) => {
      setText("#login-result", prettyJson({ ok: false, error: String(error) }));
    });
  });

  document.querySelector("#submit-callback-url")?.addEventListener("click", () => {
    submitCallbackUrl().catch((error) => {
      setText("#login-result", prettyJson({ ok: false, error: String(error) }));
    });
  });

  document.querySelector("#runtime-settings")?.addEventListener("submit", (event) => {
    saveRuntimeSettings(event).catch((error) => {
      document.querySelector("#settings-result").textContent = JSON.stringify({ ok: false, error: String(error) }, null, 2);
    });
  });

  document.querySelectorAll("[data-job]").forEach((button) => {
    button.addEventListener("click", () => {
      const job = button.getAttribute("data-job");
      runJob(job).catch((error) => {
        document.querySelector("#job-result").textContent = JSON.stringify({ ok: false, error: String(error) }, null, 2);
      });
    });
  });

  document.body.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    const accountFilter = target.closest("[data-account-filter]");
    if (accountFilter) {
      uiState.accountFilter = accountFilter.getAttribute("data-account-filter") || "all";
      renderAccounts(uiState.data.accounts);
      return;
    }

    const proxyGroup = target.closest("[data-proxy-group]");
    if (proxyGroup) {
      uiState.proxyGroup = proxyGroup.getAttribute("data-proxy-group") || "__all__";
      renderProxyGroups(uiState.data.accounts, uiState.data.proxies);
      renderProxyAssignments(uiState.data.accounts);
      return;
    }

    const copyButton = target.closest("[data-copy]");
    if (copyButton) {
      const value = copyButton.getAttribute("data-copy") || "";
      const copyPromise =
        navigator.clipboard && typeof navigator.clipboard.writeText === "function"
          ? navigator.clipboard.writeText(value)
          : Promise.reject(new Error("Clipboard unavailable"));
      copyPromise
        .then(() => {
          copyButton.textContent = t("common.copied");
          window.setTimeout(() => {
            copyButton.textContent = t("common.copyUrl");
          }, 1200);
        })
        .catch(() => {
          copyButton.textContent = t("common.copyFailed");
          window.setTimeout(() => {
            copyButton.textContent = t("common.copyUrl");
          }, 1200);
        });
      return;
    }

    const codexAppButton = target.closest("[data-codex-app-select]");
    if (codexAppButton) {
      const entryId = codexAppButton.getAttribute("data-codex-app-select") || "";
      selectCodexAppAccount(entryId).catch((error) => {
        setHtml("#codex-app-card", `<div class="chart-empty">${escapeHtml(String(error))}</div>`);
      });
      return;
    }

    const granularityButton = target.closest("[data-granularity]");
    if (granularityButton) {
      uiState.usageGranularity = granularityButton.getAttribute("data-granularity") || "hourly";
      refreshUsage().catch((error) => {
        setHtml("#usage-chart", `<div class="chart-empty">${escapeHtml(String(error))}</div>`);
      });
      return;
    }

    const hoursButton = target.closest("[data-hours]");
    if (hoursButton) {
      uiState.usageHours = Number(hoursButton.getAttribute("data-hours")) || 24;
      refreshUsage().catch((error) => {
        setHtml("#usage-chart", `<div class="chart-empty">${escapeHtml(String(error))}</div>`);
      });
    }
  });

  document.querySelector("#refresh-usage")?.addEventListener("click", () => {
    refreshUsage().catch((error) => {
      setHtml("#usage-chart", `<div class="chart-empty">${escapeHtml(String(error))}</div>`);
    });
  });

  document.querySelector("#language-select")?.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLSelectElement)) {
      return;
    }
    uiState.language = normalizeLanguage(target.value);
    try {
      window.localStorage.setItem(LANGUAGE_STORAGE_KEY, uiState.language);
    } catch {}
    applyStaticTranslations();
    if (uiState.data) {
      renderDashboard();
    }
  });

  document.querySelector("#create-api-key")?.addEventListener("click", () => {
    createApiKey().catch((error) => {
      setText("#api-key-result", prettyJson({ ok: false, error: String(error) }));
    });
  });

  document.body.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const deleteButton = target.closest("[data-api-key-delete]");
    if (!deleteButton) {
      return;
    }
    const keyId = deleteButton.getAttribute("data-api-key-delete") || "";
    if (!keyId) {
      return;
    }
    deleteApiKey(keyId).catch((error) => {
      setText("#api-key-result", prettyJson({ ok: false, error: String(error) }));
    });
  });
}

uiState.language = preferredLanguage();
applyStaticTranslations();
wireEvents();
render().catch((error) => {
  document.body.insertAdjacentHTML("beforeend", `<pre>${escapeHtml(String(error))}</pre>`);
});
