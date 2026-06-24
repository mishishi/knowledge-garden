# 08. Skills 与生产化基础

> 写中。先看 ch01-07。

v1.14 引入的 Skills 系统是这版最大亮点之一——把领域知识（写代码规范、特定业务流程、领域术语表）打包成「skill package」，像装 npm 包一样注入到 Agent prompt 里。再加生产化基础：observability、testing、deployment。

## 大致会覆盖

- **Skills 是什么**：filesystem-based 技能包（`SKILL.md` + 资源文件）
- **官方 Skills 注册**：`npx skills add crewaiinc/skills` 装到 Claude Code / Cursor / Codex
- **Skills vs Tools vs Knowledge**：三者区别，混用原则
- **Observability 集成**：Langfuse / Arize Phoenix / Braintrust / CrewAI Tracing（AMP）
- **Testing**：mock LLM、snapshot 测试、eval harness
- **Deployment**：从 `crewai run` 到 `crewai deploy` 一条命令推到 CrewAI AMP
- **成本控制**：model routing、cache、token budget

## 下篇

[09. 实战：2 个 Side-Project 串起来](../09-side-projects/) — AI 内容工厂 + PR 代码评审 Multi-Agent，从需求到跑通。
