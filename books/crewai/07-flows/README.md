# 07. Flows：状态化的事件驱动编排

> 写中。先看 ch01-06。

Crew 适合「一组人干一件事」。但生产里你常需要：「先让 Crew A 跑，结果喂给 Crew B，再让 Crew C 收尾」。这时候 Crew 不够用，需要 Flow——v1.14 引入的状态化事件驱动层。

## 大致会覆盖

- **Flow 核心概念**：`@start()` / `@listen()` 装饰器、state（Pydantic BaseModel）、router
- **第一个 Flow**：从单 Crew 升级到带 state 的 Flow
- **路由（Router）**：根据 state 决定下一步走哪个分支
- **持久化**：state 怎么存（SQLite / Postgres）、crash 后怎么恢复
- **Human-in-the-Loop**：`@human_feedback` 装饰器，关键决策让人来
- **Conversational Flow**：`handle_turn` 多轮对话场景（客服 / 助手）
- **和 Crew 的关系**：Flow 是「导演」，Crew 是「演员」

## 下篇

[08. Skills 与生产化基础](../08-skills-and-prod/) — v1.14 新引入的 Skills 系统，给 Agent 像 npm 包一样注入领域知识。
