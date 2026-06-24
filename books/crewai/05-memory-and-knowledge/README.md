# 05. Memory + Knowledge：让 agent 有记忆

> 写中。先看 ch01-04。

Agent 默认跑完一次啥也不记得。这一章拆 v1.14 的两层记忆系统：Memory（短期 / 长期 / 实体）和 Knowledge（文件型知识源）。区别在哪、什么时候用哪个、`respect_context_window` 怎么配合。

## 大致会覆盖

- **Memory 三种**：Short-term（当前 session）/ Long-term（跨 session）/ Entity（记住具体的人和事）
- **`memory=True` 一行启用**：背后是向量数据库 + entity memory + conversation buffer
- **Knowledge Source 类型**：TXT / PDF / CSV / JSON / MDX 各自怎么挂
- **Memory vs Tool 的取舍**：什么时候用 RAG Tool，什么时候用 knowledge_sources
- **上下文管理**：`respect_context_window=True` 自动摘要 vs 严格截断
- **生产中的坑**：memory 数据库用什么（默认 SQLite / 换 Chroma / 换 Pinecone）

## 下篇

[06. 结构化输出与 Guardrail](../06-structured-output/) — Agent 输出乱七八糟怎么办？Pydantic 模型怎么锁输出、Guardrail 怎么拦截违规输出。
