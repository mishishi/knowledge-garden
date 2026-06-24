# 03. Agent 调优：让 agent 听指挥

> 写中。先看 ch01-02。

Prompt 写得再细，Agent 还是不听指挥？这一章把 v1.14 的所有 Agent-level 调参开关过一遍：`reasoning` / `max_reasoning_attempts` / `multimodal` / `knowledge_sources` / `inject_date` / `cache` / `max_rpm` / `max_iter` / `respect_context_window`。每个开关配一个「什么时候开、开了会怎样」的实测。

## 大致会覆盖

- `reasoning=True`：让 Agent 在动手前先做计划反思
- `multimodal=True`：让 Agent 能读图（截图、PDF 第一页等）
- `knowledge_sources`：给 Agent 挂专属知识库（不是 Tool，是 v1.14 一等公民）
- `inject_date`：自动注入当前日期，避免「我现在的知识截止 2023 年」这种尴尬
- `cache=True`：重复调同一个 Tool 不重跑（成本杀手）
- `max_rpm`：限流，避免被 OpenAI 限速
- `max_iter` vs `max_execution_time`：循环上限怎么设合理
- `use_system_prompt=False`：老模型（不支持 system message）的兜底

## 下篇

[04. Tools 与 MCP：给 agent 接手和脚](../04-tools-and-mcp/) — 内置工具怎么选、自定义 Tool 怎么写、MCP server 怎么接。
