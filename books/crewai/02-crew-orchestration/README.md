# 02. Crew 编排：Process 选型与协作

> 写中。先看 ch01。

加第二个 Agent，把单 Agent 升级成 2 人小组：研究员 + 写作员。Sequential、Hierarchical、Async 三种 Process 怎么选，`context` 怎么传，`async_execution` 怎么用——配真实代码 + 跑出来的对比。

## 大致会覆盖

- 加 Writer Agent，跟 Researcher 串成 Pipeline
- `context=[task_a]` 怎么把上一个 Task 的输出喂给下一个
- `Process.sequential` vs `Process.hierarchical`：用 manager_llm 做任务分配
- `async_execution=True` 并行跑独立 Task（比如同时调研 3 个主题）
- `allow_delegation=True` 让 Agent 自主决定「这事该谁做」

## 下篇

[03. Agent 调优：让 agent 听指挥](../03-agent-tuning/) — 同一段 Prompt 不同模型跑出来天差地别，reasoning / knowledge_sources / multimodal / inject_date 这些开关怎么调。
