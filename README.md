# codex2gpt

[English](./README_EN.md)

统一接入 Codex 账号池、代理路由、请求记录和基础运维面板。

## 仓库介绍

这个仓库主要做五件事：

- 把不同协议的请求统一转发到 Codex 后端
- 管理多个本地 OAuth 账号，并按策略分配请求
- 切换 Codex App 使用的登录账号，无需反复重新登录
- 提供一个轻量控制台，查看账号、代理和用量状态
- 作为本地统一入口，减少不同客户端分别适配的成本

调用方式：

- OpenAI 兼容：`POST /v1/chat/completions`
- Anthropic 兼容：`POST /v1/messages`
- Gemini 兼容：`POST /v1beta/models/{model}:generateContent`
- 原生接口：`POST /v1/responses`
