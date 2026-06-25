# 02. A2A vs MCP：分工与配合

MCP（Model Context Protocol）和 A2A 是 2026 年 agent 协议层的**双子星**。它们解决不同问题，经常被混淆。

## 一句话区分

**MCP 是模型 ↔ 工具的协议**（agent 怎么调外部工具）。**A2A 是 agent ↔ agent 的协议**（多个 agent 怎么协作）。

打个比方：

- MCP 是 USB 标准——规定了"键盘、鼠标、U盘怎么插电脑"。
- A2A 是团队协作工具（Slack / Teams）——规定了"人（agent）之间怎么发消息、分配任务、提交结果"。

## MCP 解决什么

一个 agent 想调外部工具（数据库、API、文件系统）时，工具格式千差万别——有的用 REST，有的用 gRPC，有的 CLI。MCP 统一了**工具描述格式**（tool schema）、**调用格式**（JSON-RPC）、**结果格式**（text / image / embedded resource）。

Anthropic 2024 年 11 月推 MCP，到 2026 年 6 月已经有 5000+ 公开 MCP server，包括 Slack、GitHub、Notion、Stripe、Figma、Cloudflare。

MCP 让 **agent 能调用几乎任何外部系统**，不用每次重写胶水代码。

## A2A 解决什么

一个任务太复杂，一个 agent 做不完。需要多个 agent 协作：PM agent 拆需求 → Architect agent 设计 → Coder agent 实现 → Reviewer agent 审 → Tester agent 测。每个 agent 用不同框架写（LangChain / AutoGen / CrewAI / 自研），跑在不同机器上。

A2A 统一了 **agent 之间的协作格式**：

- 怎么发现其他 agent（Agent Card）
- 怎么发任务（Task 创建）
- 怎么传消息（Message / Part）
- 怎么传文件 / 流式响应（FilePart / SSE）
- 怎么订阅事件（Webhook / SSE）

## 配合使用

实际生产里，MCP 和 A2A **同时用**：

```
用户："帮我分析上个季度的销售数据并出一份报告"
   ↓
[PM Agent] (A2A server)
   ↓ A2A: 委托给 DataAnalyst Agent
[DataAnalyst Agent]
   ↓ A2A: 委托给 SQL Agent 取数
[SQL Agent]
   ↓ MCP: 通过 postgres MCP server 查 DB
   ↓ A2A: 返回结构化数据给 DataAnalyst
[DataAnalyst Agent]
   ↓ MCP: 通过 matplotlib MCP server 出图
   ↓ A2A: 返回报告给 PM Agent
[PM Agent]
   ↓ A2A: 把报告发给 Slack (通过 slack MCP server)
```

一个端到端任务里 MCP 和 A2A 穿插使用。

## 什么时候用哪个

| 场景 | 协议 | 例子 |
|------|------|------|
| Agent 调外部 API/工具 | MCP | 查数据库、发 Slack、上传文件 |
| 多个 Agent 协作 | A2A | PM 派活给 Coder，Coder 派活给 Reviewer |
| 单 agent + 多工具 | MCP | 一个 Coder agent 用 Git + Postgres + Docker MCP |
| 多 agent + 各有工具 | A2A + MCP | 5 个 agent 协作，每个 agent 内部用 MCP |
| Agent 调用其他 agent 的工具 | A2A → MCP | Coder agent 通过 A2A 调 DBA agent，DBA agent 内部用 postgres MCP |

## 2026 生态现状

**MCP**——Anthropic 主导，已经成为事实标准。Claude Desktop / Cursor / Continue.dev / Cline 全员支持。

**A2A**——Google 主导（联合 50+ 公司），刚起步（2026 年 4 月正式发布）。LangChain / CrewAI / AutoGen 都在集成。**生态比 MCP 落后 18 个月**，但增长快。

**协议融合**——Anthropic 和 Google 2026 年 5 月宣布合作，**MCP 和 A2A 不互斥而是互补**。未来 agent 架构的标配：**A2A 管 agent 间通信 + MCP 管 agent 调工具**。

## 学习路径建议

如果你刚开始学 agent 协议：

1. 先学 MCP（更成熟、生态更好）
2. 再学 A2A（刚开始，了解概念 + 跑通 demo）
3. 实战项目里组合用

下一章讲 Agent Card——A2A 的"自我介绍"，所有 agent 互操作都从这里开始。