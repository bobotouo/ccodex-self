const endpoints = {
  status: "/auth/status",
  runtime: "/admin/runtime-status",
  rotation: "/admin/rotation-settings",
  usage: "/admin/usage-stats/summary",
  apiKeys: "/admin/api-keys",
  /** 后端按 refresh_interval_seconds 自动刷新缺失/过期额度；手动按钮仍可强制 fresh */
  accounts: "/auth/accounts?quota=auto",
  proxies: "/api/proxies",
  relays: "/api/relay-providers",
  recentRequests: "/admin/recent-requests?limit=12",
  loginStart: "/auth/login-start",
  codeRelay: "/auth/code-relay",
  codexAppSelect: "/auth/codex-app/select",
  connectorSessionCreate: "/admin/connector/session/create",
  accountDelete: (id) => `/auth/accounts/batch-delete`,
  accountBatchStatus: "/auth/accounts/batch-status",
  accountImport: "/auth/accounts/import",
  accountResetUsage: (id) => `/auth/accounts/${encodeURIComponent(id)}/reset-usage`,
};

const uiState = {
  view: "overview",
  accountFilter: "all",
  accountSearch: "",
  selectedAccounts: new Set(),
  proxyGroup: "__all__",
  usageGranularity: "hourly",
  usageHours: 24,
  autoRefreshMs: 300000,
  refreshInFlight: false,
  lastRefreshAt: "",
  language: "zh-CN",
  data: null,
  authPopup: null,
  connectorPollTimer: null,
};

const LANGUAGE_STORAGE_KEY = "codex2gpt.dashboard.language";
function accountsLoadUrl() {
  return endpoints.accounts;
}

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
    "common.expired": "已恢复",
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
    "api.openaiChatHint": "支持图像生成：将 model 设为 gpt-image-2 即可生图，无需切换接口",
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
    "accounts.searchPlaceholder": "搜索账号...",
    "accounts.refresh": "刷新额度",
    "accounts.delete": "删除",
    "accounts.copyId": "复制 ID",
    "accounts.selectAll": "全选",
    "accounts.selected": "已选 {count} 个",
    "accounts.bulkDelete": "批量删除",
    "accounts.bulkRefresh": "批量刷新",
    "accounts.bulkEnable": "批量启用",
    "accounts.bulkDisable": "批量禁用",
    "accounts.import": "导入账号",
    "accounts.importHint": "每行一个 token（access_token 或 session_key），或粘贴 JSON 数组",
    "accounts.importConfirm": "导入",
    "accounts.importCancel": "取消",
    "accounts.export": "导出账号",
    "accounts.confirmDelete": "确定要删除此账号吗？",
    "accounts.confirmBulkDelete": "确定要删除选中的 {count} 个账号吗？",
    "accounts.refreshing": "刷新中...",
    "accounts.deleted": "已删除",
    "accounts.copied": "已复制",
    "accounts.imageQuota": "图像额度",
    "accounts.imageQuotaRemaining": "剩余额度",
    "accounts.imageQuotaRestore": "恢复时间",
    "accounts.imageQuotaUnknown": "未知",
    "accounts.imageQuotaInfinity": "无限制",
    "accounts.imageCount": "图像数",
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
    "common.expired": "Expired",
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
    "api.openaiChatHint": "Supports image generation: set model to gpt-image-2 to generate images, no endpoint switch needed",
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
    "accounts.searchPlaceholder": "Search accounts...",
    "accounts.refresh": "Refresh Quota",
    "accounts.delete": "Delete",
    "accounts.copyId": "Copy ID",
    "accounts.selectAll": "Select All",
    "accounts.selected": "{count} selected",
    "accounts.bulkDelete": "Bulk Delete",
    "accounts.bulkRefresh": "Bulk Refresh",
    "accounts.bulkEnable": "Bulk Enable",
    "accounts.bulkDisable": "Bulk Disable",
    "accounts.import": "Import Accounts",
    "accounts.importHint": "One token per line (access_token or session_key), or paste a JSON array",
    "accounts.importConfirm": "Import",
    "accounts.importCancel": "Cancel",
    "accounts.export": "Export Accounts",
    "accounts.confirmDelete": "Delete this account?",
    "accounts.confirmBulkDelete": "Delete {count} selected accounts?",
    "accounts.refreshing": "Refreshing...",
    "accounts.deleted": "Deleted",
    "accounts.copied": "Copied",
    "accounts.imageQuota": "Image Quota",
    "accounts.imageQuotaRemaining": "Remaining",
    "accounts.imageQuotaRestore": "Restores At",
    "accounts.imageQuotaUnknown": "Unknown",
    "accounts.imageQuotaInfinity": "Unlimited",
    "accounts.imageCount": "Images",
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

function formatRestoreTime(restoreAt) {
  if (!restoreAt) return "";
  const date = new Date(restoreAt);
  if (Number.isNaN(date.getTime())) return restoreAt;
  const now = Date.now();
  const diffMs = date.getTime() - now;
  if (diffMs <= 0) return t("common.expired") || "已恢复";
  const diffSec = Math.round(diffMs / 1000);
  return formatDurationCompact(diffSec);
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

/**
 * 与 app.py 中 quota_used_percent_fraction 一致：>1 视为 0..100 的「百分数」；否则视为 0..1 分位。
 * 与 extract_quota_summary 存库结构配合：优先后端写入的 quota.used_percent，避免空对象 primary_window 抢优先级。
 */
function normalizeQuotaUsedPercentValue(raw) {
  if (raw === undefined || raw === null || raw === "") {
    return { value: null, valid: false };
  }
  const n = Number(raw);
  if (!Number.isFinite(n)) {
    return { value: null, valid: false };
  }
  let fraction = n;
  if (fraction > 1) {
    fraction /= 100.0;
  }
  fraction = Math.max(0, Math.min(1, fraction));
  return { value: Math.round(fraction * 100), valid: true };
}

function quotaSummary(account) {
  const quota = account?.quota || {};
  const limit = quota?.rate_limit || {};
  const rawPrimaryWindow = limit?.primary_window;
  const primaryWindowIsEmpty =
    !rawPrimaryWindow || typeof rawPrimaryWindow !== "object" || !Object.keys(rawPrimaryWindow).length;
  const primary = primaryWindowIsEmpty ? limit : rawPrimaryWindow;
  const secondary = quota?.secondary_rate_limit || limit?.secondary_window || {};
  const usedPercentRaw = quota?.used_percent ?? primary?.used_percent ?? limit?.used_percent;
  const secondaryRaw = secondary?.used_percent;
  const p = normalizeQuotaUsedPercentValue(usedPercentRaw);
  const s = normalizeQuotaUsedPercentValue(secondaryRaw);
  const usedPercent = p.valid ? p.value : null;
  const secondaryUsedPercent = s.valid ? s.value : null;
  const tone =
    !p.valid
      ? ""
      : usedPercent >= 90
        ? "danger"
        : usedPercent >= 60
          ? "warn"
          : "";
  return {
    usedPercent,
    secondaryUsedPercent: s.valid ? s.value : null,
    tone,
    resetAt: primary?.reset_at || quota?.reset_at || limit?.reset_at || "",
    resetAfterSeconds:
      primary?.reset_after_seconds ?? quota?.reset_after_seconds ?? limit?.reset_after_seconds ?? "",
    limitWindowSeconds:
      primary?.limit_window_seconds ?? quota?.limit_window_seconds ?? limit?.limit_window_seconds ?? "",
    secondaryResetAt: secondary?.reset_at || "",
    secondaryResetAfterSeconds: secondary?.reset_after_seconds ?? "",
    secondaryLimitWindowSeconds: secondary?.limit_window_seconds ?? "",
    limitReached: Boolean(primary?.limit_reached || limit?.limit_reached),
    allowed: quota?.allowed ?? limit?.allowed,
    planType: quota?.plan_type || account?.plan_type || "",
    imageGenRemaining: quota?.image_gen_remaining ?? null,
    imageGenRestoreAt: quota?.image_gen_restore_at || "",
    imageGenLimit: quota?.image_gen_limit ?? null,
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

function applySummary(status, runtime, usage, accountsPayload, proxiesPayload, relaysPayload, recentRequestsPayload, apiKeysPayload) {
  const summary = summarizeStatus(status, runtime);
  const accounts = accountsPayload.data || [];
  const proxies = proxiesPayload.data || [];
  const relayProviders = relaysPayload.data || [];
  const recentRequests = recentRequestsPayload.data || [];
  const keyStats = apiKeysPayload && typeof apiKeysPayload === "object" ? apiKeysPayload : {};
  const activeAccounts = accounts.filter((account) => account.status === "active").length;
  const unhealthyProxies = proxies.filter((proxy) => proxy.status && proxy.status !== "active").length;
  const websocketLabel = summary.websocket_transport_available ? (uiState.language === "en" ? "ready" : "就绪") : (uiState.language === "en" ? "fallback" : "回退");
  const latestRequest = recentRequests[0] || null;

  /** 顶部指标：以「对外 API Key = 一个用户」的累计用量为准，避免与池内 GPT 账号状态混淆 */
  setText("#stat-accounts", String(keyStats.key_count ?? 0));
  setText(
    "#stat-accounts-meta",
    uiState.language === "en" ? `active keys ${keyStats.active_key_count ?? 0}` : `活跃 Key ${keyStats.active_key_count ?? 0}`,
  );
  setText("#stat-warnings", formatNumber(keyStats.total_request_count || 0));
  setText("#stat-warnings-meta", uiState.language === "en" ? "requests (all keys)" : "对外总请求数");
  setText("#stat-transport", formatNumber(keyStats.total_input_tokens || 0));
  setText("#stat-transport-meta", uiState.language === "en" ? "key input tokens" : "Key 输入 tokens");
  setText("#stat-responses-transport", formatNumber(keyStats.total_output_tokens || 0));
  setText("#stat-responses-transport-meta", uiState.language === "en" ? "key output tokens" : "Key 输出 tokens");

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

  if ((keyStats.key_count === 0 || keyStats.key_count === undefined) && !k?.total_request_count) {
    setText("#stat-accounts", String(summary.accounts ?? 0));
    setText("#stat-accounts-meta", t("summary.active", { count: activeAccounts }));
    setText("#stat-warnings", String(summary.warnings?.total ?? 0));
    setText("#stat-warnings-meta", t("summary.critical", { count: summary.warnings?.critical ?? 0 }));
    setText("#stat-transport", String(summary.transport_backend ?? "-"));
    setText("#stat-transport-meta", t("summary.websocket", { state: websocketLabel }));
    setText("#stat-responses-transport", String(summary.responses_transport ?? "-"));
    setText("#stat-responses-transport-meta", t("summary.relayProviders", { count: relayProviders.length }));
  }
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
      hint: t("api.openaiChatHint"),
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
            ${item.hint ? `<div class="endpoint-hint">${escapeHtml(item.hint)}</div>` : ""}
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

  const selectedCount = uiState.selectedAccounts.size;
  const container = document.querySelector("#account-filters");

  // Only create the search input once; preserve focus across re-renders
  if (!container.querySelector("#account-search-input")) {
    const searchDiv = document.createElement("div");
    searchDiv.className = "account-search";
    searchDiv.innerHTML = `<input id="account-search-input" type="text" placeholder="${escapeHtml(t("accounts.searchPlaceholder"))}" value="${escapeHtml(uiState.accountSearch)}" />`;
    container.prepend(searchDiv);
    searchDiv.querySelector("#account-search-input").addEventListener("input", (e) => {
      uiState.accountSearch = e.target.value;
      renderAccounts(accountsPayload);
    });
  }

  // Update filter chips and bulk bar — these can be rebuilt freely
  let chipsHtml = labels
    .filter(([key]) => key === "all" || (counts.get(key) || 0) > 0)
    .map(
      ([key, label]) => `
      <button class="chip ${uiState.accountFilter === key ? "is-active" : ""}" data-account-filter="${escapeHtml(key)}">
        ${escapeHtml(label)}
        <strong>${escapeHtml(counts.get(key) || 0)}</strong>
      </button>
    `,
    )
    .join("");

  let bulkHtml = `
    <div class="bulk-bar ${selectedCount === 0 ? "hidden" : ""}">
      <label class="section-heading-row" style="margin:0">
        <input type="checkbox" class="account-select" id="account-select-all" ${selectedCount === accounts.length ? "checked" : ""} />
        <span class="bulk-count">${escapeHtml(t("accounts.selected", { count: selectedCount }))}</span>
      </label>
      <div class="bulk-actions">
        <button class="action-btn" data-bulk-action="refresh">${escapeHtml(t("accounts.bulkRefresh"))}</button>
        <button class="action-btn" data-bulk-action="enable">${escapeHtml(t("accounts.bulkEnable"))}</button>
        <button class="action-btn" data-bulk-action="disable">${escapeHtml(t("accounts.bulkDisable"))}</button>
        <button class="action-btn danger" data-bulk-action="delete">${escapeHtml(t("accounts.bulkDelete"))}</button>
      </div>
    </div>
  `;

  // Remove old chips and bulk bar, then re-insert after search input
  container.querySelectorAll(".badge-row, .bulk-bar").forEach((el) => el.remove());
  container.insertAdjacentHTML("beforeend", `<div class="badge-row">${chipsHtml}</div>${bulkHtml}`);

  const selectAllCheckbox = container.querySelector("#account-select-all");
  if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener("change", () => {
      const filtered = filterAccountList(accounts, uiState.accountFilter, uiState.accountSearch);
      if (selectAllCheckbox.checked) {
        filtered.forEach((a) => uiState.selectedAccounts.add(a.entry_id));
      } else {
        filtered.forEach((a) => uiState.selectedAccounts.delete(a.entry_id));
      }
      renderAccounts(accountsPayload);
    });
  }
}

function filterAccountList(accounts, filter, search) {
  let list = accounts;
  if (filter !== "all") {
    list = list.filter((a) => (a.status || "unknown") === filter);
  }
  if (search) {
    const q = search.toLowerCase();
    list = list.filter(
      (a) =>
        (a.email || "").toLowerCase().includes(q) ||
        (a.entry_id || "").toLowerCase().includes(q) ||
        (a.status || "").toLowerCase().includes(q) ||
        (a.plan_type || "").toLowerCase().includes(q),
    );
  }
  return list;
}

function renderAccounts(accountsPayload) {
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
        const isSelected = uiState.selectedAccounts.has(account.entry_id);
        return `
          <article class="account-card">
            <div class="account-card-header">
              <div style="display:flex; align-items:flex-start; gap:8px; min-width:0; flex:1">
                <input type="checkbox" class="account-select" data-account-select="${escapeHtml(account.entry_id)}" ${isSelected ? "checked" : ""} style="margin-top:3px; flex-shrink:0" />
                <div style="min-width:0">
                  <strong>${escapeHtml(account.email || account.entry_id)}</strong>
                  <small>${escapeHtml(account.entry_id)}</small>
                </div>
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

            <div class="metric-grid">
              <div class="metric">
                <span>${escapeHtml(t("common.plan"))}</span>
                <strong>${escapeHtml(quota.planType || account.plan_type || "—")}</strong>
              </div>
              <div class="metric">
                <span>${escapeHtml(t("accounts.imageQuota"))}</span>
                <strong>${
                  quota.imageGenRemaining != null
                    ? `${escapeHtml(String(quota.imageGenRemaining))}${quota.imageGenLimit ? " / " + escapeHtml(String(quota.imageGenLimit)) : ""}`
                    : escapeHtml(t("accounts.imageQuotaUnknown"))
                }</strong>
              </div>
              <div class="metric">
                <span>${escapeHtml(t("accounts.imageCount"))}</span>
                <strong>${escapeHtml(String(account.usage?.image_count || 0))}</strong>
              </div>
              <div class="metric">
                <span>${escapeHtml(t("accounts.proxyTraffic"))}</span>
                <strong>${escapeHtml(proxyTrafficText)}</strong>
              </div>
            </div>

            ${
              quota.imageGenRemaining != null && quota.imageGenRestoreAt
                ? `<div class="muted" style="font-size:0.78rem; margin-top:-4px">${escapeHtml(t("accounts.imageQuotaRestore"))}: ${escapeHtml(formatRestoreTime(quota.imageGenRestoreAt))}</div>`
                : ""
            }

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

            <div class="account-actions">
              <button class="action-btn" data-account-action="refresh" data-account-id="${escapeHtml(account.entry_id)}" title="${escapeHtml(t("accounts.refresh"))}">
                ↻ ${escapeHtml(t("accounts.refresh"))}
              </button>
              <button class="action-btn" data-account-action="copy-id" data-account-id="${escapeHtml(account.entry_id)}" title="${escapeHtml(t("accounts.copyId"))}">
                ⊘ ${escapeHtml(t("accounts.copyId"))}
              </button>
              <button class="action-btn danger" data-account-action="delete" data-account-id="${escapeHtml(account.entry_id)}" title="${escapeHtml(t("accounts.delete"))}">
                ✕ ${escapeHtml(t("accounts.delete"))}
              </button>
            </div>
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
              ${
                item.key_id === "env_lite_api_key"
                  ? ""
                  : `<button class="action secondary" type="button" data-api-key-delete="${escapeHtml(item.key_id)}">删除</button>`
              }
            </div>
          </article>
        `,
      )
      .join(""),
  );
}

function applyUsageSummary(usage, apiKeysSummary) {
  const k = apiKeysSummary && typeof apiKeysSummary === "object" ? apiKeysSummary : null;
  const hasKeyTotals = k && (k.total_request_count !== undefined || k.key_count !== undefined);
  setText("#usage-total-input", formatNumber(hasKeyTotals ? k.total_input_tokens || 0 : usage.total_input_tokens || 0));
  setText("#usage-total-output", formatNumber(hasKeyTotals ? k.total_output_tokens || 0 : usage.total_output_tokens || 0));
  setText("#usage-total-requests", formatNumber(hasKeyTotals ? k.total_request_count || 0 : usage.total_request_count || 0));
  setText(
    "#usage-account-count",
    formatNumber(hasKeyTotals ? k.key_count || 0 : usage.account_count || 0),
  );
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
  const keyHistoryUrl = `/admin/api-keys/usage-history?granularity=${encodeURIComponent(
    uiState.usageGranularity,
  )}&hours=${encodeURIComponent(String(uiState.usageHours))}`;
  const apiKeysUrl = `${endpoints.apiKeys}?hours=${encodeURIComponent(String(uiState.usageHours))}`;
  const accUrl = accountsLoadUrl();
  const [status, runtime, rotation, usage, apiKeys, accounts, proxies, relays, usageHistory, recentRequests] = await Promise.all([
    loadJson(endpoints.status),
    loadJson(endpoints.runtime),
    loadJson(endpoints.rotation),
    loadJson(endpoints.usage),
    loadJson(apiKeysUrl),
    loadJson(accUrl),
    loadJson(endpoints.proxies),
    loadJson(endpoints.relays),
    loadJson(keyHistoryUrl),
    loadJson(endpoints.recentRequests),
  ]);
  uiState.lastRefreshAt = new Date().toISOString();
  uiState.data = { status, runtime, rotation, usage, apiKeys, accounts, proxies, relays, usageHistory, recentRequests };
  return uiState.data;
}

function renderDashboard() {
  const { status, runtime, rotation, usage, apiKeys, accounts, proxies, relays, usageHistory, recentRequests } = uiState.data;
  applyViewFromHash();
  applySummary(status, runtime, usage, accounts, proxies, relays, recentRequests, apiKeys);
  applySettings(rotation);
  renderWarnings(accounts);
  renderRecentRequests(recentRequests);
  renderAccounts(accounts);
  renderApiKeys(apiKeys);
  renderProxies(proxies);
  renderProxyAssignments(accounts);
  renderRelays(relays);
  applyUsageSummary(usage, apiKeys);
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

async function createConnectorSession() {
  const button = document.querySelector("#create-connector-session");
  const commandInput = document.querySelector("#connector-command");
  const output = document.querySelector("#connector-result");
  if (!button || !commandInput || !output) {
    return;
  }
  button.disabled = true;
  output.textContent = "正在为本次添加账号生成命令...";
  commandInput.value = "";
  try {
    const result = await postJson(endpoints.connectorSessionCreate, {});
    if (result?.error) {
      output.textContent = prettyJson(result);
      return;
    }
    const command = `curl -fsSL "${result.install_url}" | bash`;
    commandInput.value = command;
    output.textContent = [
      "账号添加命令已生成。请发给目标用户在本地终端执行。",
      `会话 ID: ${result.session_id || ""}`,
      `有效期: ${result.expires_in_seconds || 0} 秒`,
      "",
      "本次会话仅对应一个账号，等待上传结果...",
    ].join("\n");
    if (uiState.connectorPollTimer) {
      window.clearInterval(uiState.connectorPollTimer);
      uiState.connectorPollTimer = null;
    }
    const poll = async () => {
      try {
        const status = await loadJson(`/admin/connector/session/${encodeURIComponent(result.session_id || "")}`);
        if (status?.error) {
          output.textContent = prettyJson(status);
          return;
        }
        const lines = [
          `状态: ${status.status || "pending"}`,
          `过期时间: ${status.expires_at || "-"}`,
          status.message ? `说明: ${status.message}` : "",
          status.uploaded_entry_id ? `账号文件: ${status.uploaded_entry_id}` : "",
          status.uploaded_email ? `邮箱: ${status.uploaded_email}` : "",
          status.error ? `错误: ${status.error}` : "",
        ].filter(Boolean);
        output.textContent = lines.join("\n");
        if (status.status && status.status !== "pending") {
          if (uiState.connectorPollTimer) {
            window.clearInterval(uiState.connectorPollTimer);
            uiState.connectorPollTimer = null;
          }
          if (status.status === "completed" || status.status === "duplicate") {
            render().catch(() => {});
          }
        }
      } catch (error) {
        output.textContent = prettyJson({ ok: false, error: String(error) });
      }
    };
    await poll();
    uiState.connectorPollTimer = window.setInterval(() => {
      poll().catch(() => {});
    }, 3000);
  } catch (error) {
    output.textContent = prettyJson({ ok: false, error: String(error) });
  } finally {
    button.disabled = false;
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

async function deleteAccounts(ids) {
  return postJson(endpoints.accountDelete(), { ids });
}

async function setAccountBatchStatus(ids, status) {
  return postJson(endpoints.accountBatchStatus, { ids, status });
}

async function importAccounts(accounts) {
  return postJson(endpoints.accountImport, { accounts });
}

async function refreshAccountQuota(entryId) {
  return postJson(endpoints.accountResetUsage(entryId), {});
}

async function copyToClipboard(text) {
  if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
    return navigator.clipboard.writeText(text);
  }
  return Promise.reject(new Error("Clipboard unavailable"));
}

async function refreshUsage() {
  if (!uiState.data) {
    await render();
    return;
  }
  const keyHistoryUrl = `/admin/api-keys/usage-history?granularity=${encodeURIComponent(
    uiState.usageGranularity,
  )}&hours=${encodeURIComponent(String(uiState.usageHours))}`;
  const apiKeysUrl = `${endpoints.apiKeys}?hours=${encodeURIComponent(String(uiState.usageHours))}`;
  uiState.data.usage = await loadJson(endpoints.usage);
  uiState.data.apiKeys = await loadJson(apiKeysUrl);
  uiState.data.usageHistory = await loadJson(keyHistoryUrl);
  renderDashboard();
}

function showImportModal() {
  const existing = document.querySelector(".modal-backdrop");
  if (existing) existing.remove();

  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal-card">
      <h3>${escapeHtml(t("accounts.import"))}</h3>
      <p class="subcopy small">${escapeHtml(t("accounts.importHint"))}</p>
      <textarea id="import-textarea" placeholder="eyJhbGciOi...&#10;eyJhbGciOi..."></textarea>
      <div style="display:flex; gap:8px; justify-content:flex-end">
        <button class="action secondary" id="import-cancel">${escapeHtml(t("accounts.importCancel"))}</button>
        <button class="action" id="import-confirm">${escapeHtml(t("accounts.importConfirm"))}</button>
      </div>
    </div>
  `;
  document.body.appendChild(backdrop);

  backdrop.querySelector("#import-cancel")?.addEventListener("click", () => backdrop.remove());
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) backdrop.remove();
  });
  backdrop.querySelector("#import-confirm")?.addEventListener("click", async () => {
    const textarea = backdrop.querySelector("#import-textarea");
    const raw = (textarea?.value || "").trim();
    if (!raw) return;
    let accounts = [];
    try {
      const parsed = JSON.parse(raw);
      accounts = Array.isArray(parsed) ? parsed : [parsed];
    } catch {
      const lines = raw.split("\n").map((l) => l.trim()).filter(Boolean);
      accounts = lines.map((line) => ({ tokens: [line] }));
    }
    if (!accounts.length) return;
    const result = await importAccounts(accounts);
    backdrop.remove();
    if (result?.error) {
      setText("#accounts-list", renderEmpty(result.error.message || t("common.unknown")));
    } else {
      await render();
    }
  });
}

async function exportAccounts() {
  const result = await loadJson("/auth/accounts/export");
  if (result?.error) return;
  const accounts = result?.accounts || [];
  if (!accounts.length) return;
  const blob = new Blob([JSON.stringify(accounts, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `codex2gpt-accounts-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(url);
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

  document.querySelector("#create-connector-session")?.addEventListener("click", () => {
    createConnectorSession().catch((error) => {
      setText("#connector-result", prettyJson({ ok: false, error: String(error) }));
    });
  });

  document.querySelector("#copy-connector-command")?.addEventListener("click", async () => {
    const commandInput = document.querySelector("#connector-command");
    const button = document.querySelector("#copy-connector-command");
    const value = (commandInput && "value" in commandInput ? commandInput.value : "").trim();
    if (!value || !button) {
      return;
    }
    try {
      await navigator.clipboard.writeText(value);
      button.textContent = "已复制";
      window.setTimeout(() => {
        button.textContent = "复制命令";
      }, 1200);
    } catch (error) {
      button.textContent = "复制失败";
      window.setTimeout(() => {
        button.textContent = "复制命令";
      }, 1200);
    }
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
      return;
    }

    const accountAction = target.closest("[data-account-action]");
    if (accountAction) {
      const action = accountAction.getAttribute("data-account-action") || "";
      const accountId = accountAction.getAttribute("data-account-id") || "";
      if (action === "delete" && accountId) {
        if (!window.confirm(t("accounts.confirmDelete"))) return;
        deleteAccounts([accountId])
          .then(() => render())
          .catch(() => {});
      } else if (action === "refresh" && accountId) {
        accountAction.disabled = true;
        accountAction.textContent = t("accounts.refreshing");
        refreshAccountQuota(accountId)
          .then(() => render())
          .catch(() => render());
      } else if (action === "copy-id" && accountId) {
        copyToClipboard(accountId)
          .then(() => {
            accountAction.textContent = `✓ ${t("accounts.copied")}`;
            window.setTimeout(() => {
              accountAction.textContent = `⊘ ${t("accounts.copyId")}`;
            }, 1200);
          })
          .catch(() => {});
      }
      return;
    }

    const accountSelect = target.closest("[data-account-select]");
    if (accountSelect) {
      const entryId = accountSelect.getAttribute("data-account-select") || "";
      if (accountSelect.checked) {
        uiState.selectedAccounts.add(entryId);
      } else {
        uiState.selectedAccounts.delete(entryId);
      }
      if (uiState.data?.accounts) {
        renderAccountFilters(uiState.data.accounts);
      }
      return;
    }

    const bulkAction = target.closest("[data-bulk-action]");
    if (bulkAction) {
      const action = bulkAction.getAttribute("data-bulk-action") || "";
      const ids = [...uiState.selectedAccounts];
      if (!ids.length) return;
      if (action === "delete") {
        if (!window.confirm(t("accounts.confirmBulkDelete", { count: ids.length }))) return;
        deleteAccounts(ids)
          .then(() => {
            uiState.selectedAccounts.clear();
            render();
          })
          .catch(() => {});
      } else if (action === "refresh") {
        setAccountBatchStatus(ids, "active")
          .then(() => render())
          .catch(() => {});
      } else if (action === "enable") {
        setAccountBatchStatus(ids, "active")
          .then(() => render())
          .catch(() => {});
      } else if (action === "disable") {
        setAccountBatchStatus(ids, "disabled")
          .then(() => {
            uiState.selectedAccounts.clear();
            render();
          })
          .catch(() => {});
      }
      return;
    }

    const importButton = target.closest("[data-account-import]");
    if (importButton) {
      showImportModal();
      return;
    }

    const exportButton = target.closest("[data-account-export]");
    if (exportButton) {
      exportAccounts();
      return;
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
