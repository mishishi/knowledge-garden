# 01. 什么是 A2A 协议

2026 年 4 月，Google 联合 50 多家公司（包括 Salesforce、Atlassian、LangChain、MongoDB、ServiceNow 等）推出了 **Agent2Agent (A2A) 协议**。目标是让不同框架、不同厂商的 agent **互相通信、互相协作**——不需要事先集成。

这是个大事。之前 MCP（Anthropic 2024 年推）解决了**模型 ↔ 工具**的标准化，A2A 解决的是 **agent ↔ agent** 的标准化。两个协议互补：MCP 让一个 agent 能调用外部工具，A2A 让多个 agent 能组成团队。

## 为什么需要 A2A

2025 年有个真实场景：客户让我们做一个"AI 软件开发团队"，PM agent 拆需求、Architect agent 画架构、Coder agent 写代码、Reviewer agent 审 PR、Tester agent 跑测试。**5 个 agent 怎么通信？**

我们最初的做法是写一套内部协议，每个 agent 监听 RabbitMQ 队列，交换 JSON 消息。3 个月后发现两个问题：

1. **跨公司复用难**——客户的 Salesforce agent 想加入流程，得按我们的协议重写一遍。
2. **schema 漂移**——每个 agent 自己改消息格式，集成时一堆类型错误。

A2A 协议就是为了解决这两个问题：标准化的 agent 间通信，让任何符合 A2A 规范的 agent 都能加入任何其他符合 A2A 规范的系统。

## A2A 协议核心概念

**Agent Card** — JSON 文件，描述 agent 的能力、输入输出格式、认证方式。类似 OpenAPI 的 `swagger.json`，但描述的是 agent 而不是 API。Agent Card 通常托管在 `/.well-known/agent.json` 路径。

**Task** — A2A 的基本工作单元。一个 Task 有唯一 ID、有状态机（submitted / working / input-required / completed / failed / canceled）、有 artifacts（输出）。

**Message** — agent 间交换的内容，包含 role（user / agent）、parts（text / file / data）、contextId、taskId。

**Part** — Message 的最小单元，分 4 种类型：TextPart（纯文本）、FilePart（文件，可带 base64 / URI）、DataPart（结构化 JSON，JSON Schema 描述）、最关键的 **AgentPart**（内嵌另一个 agent 的引用，用于嵌套调用）。

## A2A vs HTTP REST vs gRPC

A2A 不是替代 HTTP——它是 HTTP 之上的语义层。A2A 的传输通常是 JSON-RPC over HTTP（SSE 用于流式响应）。

类比：

- HTTP = 字节传输层
- REST = 资源抽象层
- A2A = agent 协作语义层

A2A 的关键创新是 **Task 作为有状态对象**。REST 的 endpoint 调用是无状态的，A2A 的 Task 可以跨多次调用、跨多个 agent 持续存在，**带状态机的协作**。

## A2A 适用场景

**多 agent 协作系统** — 多个专业 agent 共同完成一个复杂任务（软件开发、数据分析、研究综述）。

**跨厂商 agent 互操作** — 你用 LangChain 写的 agent 调 Salesforce 的 Agentforce agent，调 Atlassian 的 Rovo agent，**不需要写胶水代码**。

**agent 市场** — 开发者发布 agent 到市场（按能力定价），其他 agent 通过 A2A 调用，按调用付费。

**agent mesh** — 多个 agent 组成动态网络，根据任务自动选择最合适的 agent。

## A2A 不适用场景

**单机单 agent** — 你就一个 agent 不需要 A2A。

**高频低延迟调用** — A2A 默认走 HTTP，延迟 50-200ms。如果你要微秒级 agent 调用，A2A 太重。

**强实时音视频** — 用 WebRTC / SIP，不要用 A2A。

下一章讲 A2A 和 MCP 的区别与配合——这是 2026 年 agent 架构师面试必问题。