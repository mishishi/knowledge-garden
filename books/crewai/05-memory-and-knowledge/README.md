# 05. Memory + Knowledge：让 agent 有记忆

> CrewAI agent 默认跑完一次啥也不记得。这一章拆 v1.14 的两层记忆系统：Memory（短期 / 长期 / 实体）和 Knowledge（文件型知识源）的区别、什么时候用哪个、跟 context window 怎么配合。

## Memory 和 Knowledge 解决不同的问题

很多人把这两个混。它们其实解决完全不同的问题：

Memory 是 agent 自己的「脑子」——存对话历史、用户偏好、跨 session 保留的事实，存到向量数据库（CrewAI 默认 ChromaDB），自动检索相关历史。

Knowledge 是给 agent 看的「参考资料」——存产品文档、公司规范这类静态内容，存到文件（TXT / PDF / CSV），通过语义搜索找相关段落。

我自己做的项目里区分很清晰：客服 agent 用了 Memory（记用户上次问的订单）、技术文档 agent 用了 Knowledge（加载产品手册 PDF）。如果混用，agent 既要记用户偏好又要找文档，retrieval 噪声大、结果不稳定。

## Memory 的 3 种类型

v1.14 的 `memory=True` 启用后自动配 3 种记忆。

**Short-term Memory**——当前 session 的对话历史，存在 ChromaDB 或外部向量库。session 结束就清空。

**Long-term Memory**——跨 session 保留的事实。「这个用户上次问了什么」「用户的偏好」「用户公司的产品」。这种记忆会持续增长，必须配 decay 策略，否则半年后 10 万条 facts 检索慢。

**Entity Memory**——记住具体的人 / 事 / 物。「用户提过他们公司叫 ABC、CEO 叫张三」「用户上次提的订单号是 #12345」。Entity Memory 是 Long-term Memory 的子集，但检索方式不同（按实体名精确匹配而不是 embedding 相似度）。

```python
from crewai import Crew, Agent, Task

agent = Agent(
    role="资深客服",
    goal="回答用户问题",
    backstory="你是 Acme 平台的客服...",
    memory=True,  # 启用 3 种记忆
)

# Long-term 写入示例（v1.14 API）
agent.long_term_memory.save({
    "user_id": "user-123",
    "fact": "用户偏好中文回复",
})
```

3 种记忆的写入时机：Short-term 是自动的（每轮对话 append）；Long-term 是 LLM 主动判断「这条值得记住」（v1.14 默认开）；Entity Memory 是 NLP 抽实体名 + 关系。

## Knowledge 源：从文件加载

Knowledge 是给 agent 看的参考资料。v1.14 的 `knowledge_sources` 配置：

```python
from crewai.knowledge.source.text_file_knowledge_source import TextFileKnowledgeSource

knowledge = TextFileKnowledgeSource(file_paths=["product_manual.txt"])

agent = Agent(
    role="产品助手",
    goal="回答产品问题",
    backstory="...",
    knowledge_sources=[knowledge],  # 加载文件
)
```

支持的文件类型：TXT、PDF、CSV、Markdown。每种有对应的 Source class。加载时文件被分块、向量化、存到向量库。运行时按 query 检索 top-K 段落塞进 prompt。

我自己踩过的坑：Knowledge 文件太大（500 页 PDF）时全量 embedding 太慢，必须先 split + 选 embedding model。PDF 里如果有图片 / 表格，提取文本会丢信息——v1.14 的 PDFSource 只抽文本，表格变成乱序文字。

## respect_context_window

3 种记忆 + Knowledge 都会塞进 prompt，很容易超 context window。`respect_context_window=True` 让 CrewAI 自动管理：

```python
agent = Agent(
    role="...",
    memory=True,
    respect_context_window=True,  # 关键
    knowledge_sources=[knowledge],
)
```

打开后 CrewAI 会按优先级排序塞内容：当前任务 > Short-term 最近对话 > Long-term 相关 facts > Entity Memory > Knowledge 检索结果。超出 context window 时按优先级砍尾部。

我的经验：永远打开 `respect_context_window=True`。我早期没开时遇到几次 prompt 80k tokens、LLM 答非所问，开之后稳定在 15-20k。

但有一个限制：它只砍「不那么重要」的内容，不会自动 compact 或 summarize。所以 context 超 100k 时还是会有 Lost-in-the-Middle 现象——重要 facts 被砍掉。这种情况要手动配 `knowledge_chunk_size` 和 retrieval 阈值。

## 什么时候用哪个

我自己项目的决策表：

| 场景 | 用 Memory | 用 Knowledge |
|---|---|---|
| 客服 agent | 必开 | 加载产品手册 + 退换货政策 |
| 代码审查 agent | 必开（记用户技术栈偏好） | 加载项目 README + coding style guide |
| 数据分析 agent | 选开（多轮对话才有意义） | 加载数据字典 + 历史 query |
| 单次查询 agent | 不需要 | 选开 |
| 内容生成 agent | 不需要（每次任务独立） | 加载品牌指南 + 风格文档 |

规则：**跨 session 还要用 → Memory；只是任务上下文 → Knowledge；都不用 → 关掉减少噪声**。

## 跟 RAG 的区别

Knowledge 源本质上就是 RAG——把文档分块、向量化、检索、塞 prompt。CrewAI 的 Knowledge 是简化版 RAG，没显式 reranking / hybrid search / chunk overlap 控制。

我需要高级 RAG 功能时关掉 Knowledge，自己接 ChromaDB + LangChain retrieval chain，效果更好。简单场景（agent 查产品手册）直接用 Knowledge，配置简单。

## 我踩过的坑

**Memory 没 decay**——3 个月后 Long-term Memory 10 万条 facts，每次检索 top-K 越来越不准。修：每 30 天跑一次 decay，按 fact timestamp + 引用频率淘汰。

**Knowledge 文件太大**——500 页 PDF 一次性 embedding，4 小时还没完。修：先 split（每 1000 字一块），分批 embedding。

**Entity Memory 抽错实体**——NLP 把「张三」抽成「张」和「三」两个字。修：用更准的 NER model（spaCy / HanLP），或关闭 Entity Memory 自己维护。

**Memory 和 Knowledge retrieval 混在一起**——agent 同时记用户偏好 + 查产品手册，结果把用户偏好当成产品文档引用。修：分开两个向量库，retrieval 时按 query 类型路由。

[06. Structured Output](../06-structured-output/) 讲 CrewAI 的 Pydantic output + JSON validation——把 agent 输出从「自然语言」变成「结构化数据」的工程模式。
