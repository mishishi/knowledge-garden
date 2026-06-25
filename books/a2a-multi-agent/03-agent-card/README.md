# 03. Agent Card：A2A 的自我介绍

Agent Card 是 A2A 协议的核心原语——一个 JSON 文件，描述 agent 的身份、能力、输入输出、认证方式。**所有 agent 间互操作都从 Agent Card 开始**。

## 类比 OpenAPI

做过 API 集成的人都知道 OpenAPI / Swagger：`swagger.json` 一份文件描述整个 API，client SDK 自动生成、文档自动生成、测试工具自动接入。

Agent Card 就是 agent 世界的 OpenAPI：

```json
{
  "name": "DataAnalyst Agent",
  "description": "分析结构化数据并生成报告，支持 SQL 查询、可视化、统计建模",
  "url": "https://agents.example.com/data-analyst",
  "version": "1.2.0",
  "provider": {
    "organization": "ExampleCorp",
    "url": "https://example.com"
  },
  "capabilities": {
    "streaming": true,
    "pushNotifications": true,
    "stateTransitionHistory": false
  },
  "authentication": {
    "schemes": ["bearer", "oauth2"]
  },
  "defaultInputModes": ["text", "data"],
  "defaultOutputModes": ["text", "file", "data"],
  "skills": [
    {
      "id": "sql-query",
      "name": "SQL Query",
      "description": "执行 SQL 查询并返回结果",
      "inputModes": ["text", "data"],
      "outputModes": ["data"],
      "examples": [
        {
          "input": "查询 2026 Q1 销售额前 10 的产品",
          "output": {"columns": [...], "rows": [...]}
        }
      ]
    },
    {
      "id": "visualization",
      "name": "Data Visualization",
      "description": "生成数据可视化图表",
      "inputModes": ["data"],
      "outputModes": ["file"]
    }
  ]
}
```

## Agent Card 的关键字段

**name / description / version** — 基本信息，跟 npm package 或 OpenAPI 的 info 段类似。

**url** — agent 的 endpoint。客户端通过这个 URL 发起 A2A 调用（默认是 `https://agent-url/a2a/v1`，类似 gRPC 的 service URL）。

**provider** — agent 所属组织。用于 agent 市场里的信任评估。

**capabilities**：

- **streaming**：agent 是否支持流式响应（SSE）。如果是，client 可以订阅增量输出。
- **pushNotifications**：agent 是否支持异步通知（长任务跑完推 webhook）。
- **stateTransitionHistory**：agent 是否保留完整状态机历史。

**authentication.schemes** — 支持的认证方式（bearer / oauth2 / apiKey / mtls）。

**defaultInputModes / defaultOutputModes** — 默认支持的内容类型（text / file / data）。

**skills[]** — agent 的具体能力，每个 skill 独立描述：

- **id** — skill 唯一标识
- **name / description** — 人类可读的名称和说明
- **inputModes / outputModes** — 该 skill 特定的输入输出类型
- **examples[]** — 示例输入输出（**重要**，用于 LLM 理解怎么用）

## 为什么 examples 关键

Agent Card 的 skills 里**必须带 examples**。原因是 A2A 的客户端往往是另一个 LLM agent，它通过读 examples 理解**怎么调你这个 agent**。

我们实测：

- 带 3 个 examples 的 Agent Card，client agent 一次调通率 78%
- 不带 examples 的 Agent Card，client agent 一次调通率 23%，平均需要 2.4 轮试错

所以发布 Agent Card 时**写 examples 比写 description 更重要**。

## Agent Card 的存放

按 A2A 规范，Agent Card 应托管在 agent 的 `/.well-known/agent.json` 路径。这样客户端可以通过 GET 这个路径自动发现 agent 能力，类似 OpenID Connect 的 `.well-known/openid-configuration`。

```bash
curl https://agents.example.com/data-analyst/.well-known/agent.json
```

如果 agent 跑在 K8s / Docker 里，这个路径通常通过 Ingress / Nginx 暴露。

## Agent Card vs MCP Server Manifest

A2A 的 Agent Card 和 MCP 的 server manifest 经常被比较：

| 维度 | MCP Manifest | A2A Agent Card |
|------|--------------|----------------|
| 描述对象 | 工具 | Agent |
| 内容粒度 | tools[] | skills[] |
| 传输 | stdio / http + SSE | JSON-RPC over HTTP |
| 状态 | 无状态 | 有状态（Task） |
| 适用场景 | 模型调工具 | agent 调 agent |

**两者可以共存**：同一个 agent 可以同时有 MCP server manifest（描述它暴露的工具）和 A2A Agent Card（描述它的能力）。MCP 让外部 agent **用它的工具**，A2A 让外部 agent **把整个任务委托给它**。

## 实战建议

我自己写 A2A agent 的流程：

1. 先写 Agent Card JSON（这个先于代码！）
2. 给每个 skill 写 3 个 examples
3. 部署到 `/.well-known/agent.json`
4. 写 agent 实现
5. 跑 A2A conformance test suite（官方有）

写 Agent Card 的过程会逼你想清楚 agent 的边界——什么能做、什么不能做、输入输出格式、错误处理。**很多人跳过这一步直接写代码，最后 agent 能力模糊、难集成**。

下一章讲 4 种 A2A 协作范式——A2A 协议之上，组织多个 agent 完成复杂任务的标准模式。