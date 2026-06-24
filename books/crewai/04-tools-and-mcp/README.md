# 04. Tools 与 MCP：给 agent 接手和脚

> 写中。先看 ch01-03。

LLM 自己只能生成文字，干不了实事。Tool 是 Agent 的「手和脚」——查数据库、调 API、读文件、发邮件都靠它。这章分三层：内置工具怎么选、自定义 Tool 怎么写、MCP server 怎么接。

## 大致会覆盖

- **内置工具选型**：SerperDevTool / WebsiteSearchTool / FirecrawlTool / CodeInterpreterTool（已废弃）/ RAG Tool
- **自定义 Tool 两种写法**：`@tool` 装饰器 vs `BaseTool` 子类
- **Tool 设计原则**：粒度、错误信息、幂等性、Docstring 写法（LLM 靠这个决定调不调）
- **MCP 集成**：v1.14 新引入 `mcps` 字段，stdio / SSE / streamable-http 三种 transport
- **MCP 安全注意事项**：不能盲信外部 MCP server 的 Tool 返回

## 下篇

[05. Memory + Knowledge：让 agent 有记忆](../05-memory-and-knowledge/) — Agent 跑完就忘事怎么办？短期 / 长期 / 实体记忆怎么配。
