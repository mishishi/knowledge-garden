# 05. Memory + Knowledge：让 agent 有记忆

> Agent 默认跑完一次啥也不记得。这一章拆 v1.14 的两层记忆系统：Memory（短期 / 长期 / 实体）和 Knowledge（文件型知识源）。区别在哪、什么时候用哪个、`respect_context_window` 怎么配合。

## Memory vs Knowledge：先分清

很多人把这两个混。它们其实解决完全不同的问题：

| 维度 | Memory | Knowledge |
|------|--------|-----------|
| **存什么** | 对话历史、用户偏好 | 产品文档、公司规范 |
| **存哪里** | 向量数据库（ChromaDB） | 文件（TXT / PDF / CSV） |
| **怎么用** | 自动检索相关历史 | 语义搜索找相关段落 |
| **持久化** | 跨 session | 静态 |
| **典型场景** | 「你上次说喜欢 Python」 | 「产品手册第 3 章」 |

**一句话**：Memory 是 Agent 自己的脑子，Knowledge 是给 Agent 看的参考资料。

## Memory：三种记忆

v1.14 的 `memory=True` 启用后，自动配三种记忆：

```
Short-term Memory（短期）
└─ 当前 session 的对话历史
   存在 ChromaDB（默认）或外部向量库

Long-term Memory（长期）
└─ 跨 session 保留的事实
   比如「这个用户上次问了什么」「用户的偏好」

Entity Memory（实体）
└─ 记住具体的人/事/物
   比如「User 提过他们公司叫 ABC，CEO 叫张三」
```

### 启用 Memory

一行 `memory=True`：

```python
from crewai import Agent

agent = Agent(
    role="Customer Support",
    goal="帮用户解决问题",
    backstory="...",
    memory=True,   # ← 启用全部三种 memory
    verbose=True,
)
```

**实测**：

- 第 1 次跑：Agent 完全凭 prompt 回答
- 第 2 次跑（同一 user_id）：Agent 会说「我注意到你上次问过类似问题」
- 第 3 次跑：Agent 会主动引用之前的对话

### 配 Memory 后端

默认用 ChromaDB + 本地 SQLite。生产建议换外部向量库：

```python
from crewai.memory.storage.chromadb import ChromaDBStorage

storage = ChromaDBStorage(
    type="short_term",   # short_term / long_term / entity
    embedder_config={
        "provider": "openai",
        "config": {"model": "text-embedding-3-small"},
    },
)

agent = Agent(
    role="...",
    memory=True,
    memory_storage=storage,   # ← 用配好的 storage
)
```

**生产推荐**：

- 小规模 demo：默认 ChromaDB 本地
- 跨机器：ChromaDB server 模式
- 大规模：Pinecone / Weaviate / Qdrant

### Memory 调试

```python
agent = Agent(
    role="...",
    memory=True,
    verbose=True,   # ← 看到 Agent 每次检索了哪些 memory
)
```

verbose 输出会显示 `[Memory] Retrieved 3 relevant past conversations: ...`。

### Memory 隐私

Memory 持久化意味着**用户数据会留在你的数据库里**。生产环境必做：

1. **定期清理**：超过 90 天的 memory 自动删
2. **PII 脱敏**：往 memory 里写之前先 regex 掉邮箱、手机号
3. **用户控制**：给用户「忘记我」按钮，调 `memory.reset()`

```python
# 删某个 user 的所有 memory
agent.reset_memory(user_id="user_123")
```

## Knowledge：文件型知识源

Knowledge 是 v1.14 的一等公民——给 Agent 挂「参考资料」。

### 支持的文件类型

| 类型 | 用途 |
|------|------|
| `TextFileKnowledgeSource` | .txt / .md |
| `PDFKnowledgeSource` | .pdf |
| `CSVKnowledgeSource` | .csv |
| `JSONKnowledgeSource` | .json |
| `ExcelKnowledgeSource` | .xlsx |

### 写法 1：单文件

```python
from crewai.knowledge.source.text_file_knowledge_source import TextFileKnowledgeSource

manual = TextFileKnowledgeSource(file_paths=["product_manual.md"])

agent = Agent(
    role="技术支持",
    goal="用产品手册帮用户",
    backstory="...",
    knowledge_sources=[manual],
)
```

### 写法 2：多文件 + 目录

```python
from pathlib import Path

docs = TextFileKnowledgeSource(
    file_paths=[
        "docs/manual.md",
        "docs/faq.md",
        "docs/troubleshooting.md",
    ],
)

agent = Agent(
    role="技术支持",
    knowledge_sources=[docs],
)
```

### 写法 3：PDF

```python
from crewai.knowledge.source.pdf_knowledge_source import PDFKnowledgeSource

hr_policy = PDFKnowledgeSource(file_paths=["hr_2026_policy.pdf"])

agent = Agent(
    role="HR Assistant",
    knowledge_sources=[hr_policy],
)
```

### 写法 4：CSV

```python
from crewai.knowledge.source.csv_knowledge_source import CSVKnowledgeSource

products = CSVKnowledgeSource(file_paths=["products.csv"])

agent = Agent(
    role="销售助手",
    knowledge_sources=[products],
)
```

### 配 Knowledge embedder

默认用 OpenAI embedding。生产可以换：

```python
manual = TextFileKnowledgeSource(
    file_paths=["product_manual.md"],
    embedder={
        "provider": "openai",
        "config": {"model": "text-embedding-3-small"},
    },
)
```

### Knowledge 的检索过程

```
Agent 收到问题 "X 功能怎么用？"
    ↓
Knowledge source 把问题转成 embedding
    ↓
向量数据库找最相关的 3-5 个段落
    ↓
把段落塞进 Agent 的 prompt（context）
    ↓
Agent 基于 context 回答
```

**这跟 RAG 完全一样**。Knowledge 本质上就是「框架帮你做了 RAG」，不用自己写 chunk + embed + retrieve。

## Memory + Knowledge 配合

实际项目里两个一起用：

```python
agent = Agent(
    role="技术支持",
    goal="帮用户解决产品问题",
    backstory="资深技术支持，熟悉产品手册",
    memory=True,                  # 记住用户的对话历史
    knowledge_sources=[manual],   # 知道产品手册的内容
    verbose=True,
)
```

Memory 让你说「上次你问过」；Knowledge 让你能查手册回答问题。

**实战模式**：

- 用户：「上次我问你 X 怎么解决，你说是改 Y 配置。现在 Y 配置我改了，但还是有问题。」
- Agent 查 memory：上次确实问过 X
- Agent 查 knowledge：手册说 Y 配置后还要重启服务
- Agent：「你上次问过这个。Y 配置你改对了，但还要重启服务，试试 `systemctl restart product`。」

## 知识源管理 5 个坑

**坑 1：knowledge 文档太大**

PDF 200 页全塞进去。Agent 检索时会找到 5-10 段，每段 1000 字——把 context 撑爆。

**修复**：先自己用脚本把 PDF 切分成 1-2 页一份的小 PDF。或者用 chunking 脚本（LangChain 之类的）预处理。

**坑 2：文档更新了，knowledge 没更新**

改了 `product_manual.md` 但 Agent 回答旧内容。Knowledge 是**启动时**读一次，不会热更新。

**修复**：重启 Crew。生产里配文件 watch + 自动 reload。

**坑 3：Knowledge 检索不到该查的内容**

「用户问 X」时没找到相关段落。可能原因：

- 文档用词跟用户问法差异大（用户问「怎么登录」，文档写「身份验证」）
- 文档太长，关键内容被埋
- Embedding 模型不匹配

**修复**：

- 文档加 FAQ section
- 切分更细
- 用更强的 embedding 模型

**坑 4：Knowledge 跟 Tool 重复**

```python
# 错：Knowledge 存了产品文档 + Tool 调官方 API 查产品信息
agent = Agent(
    knowledge_sources=[product_manual],  # 静态文档
    tools=[ProductAPI()],                # 实时 API
)
```

两套数据可能冲突。**二选一**：

- 数据是「历史文档」（产品手册、API 文档）→ 用 Knowledge
- 数据是「实时变化」（订单状态、库存）→ 用 Tool

**坑 5：Memory 检索出错的旧记忆**

Agent 拿了「3 个月前的对话」当事实。比如「你上次说你公司叫 ABC」（其实你换工作了）。

**修复**：

- 长期 memory 加时间衰减（3 个月前的不优先）
- 给用户「清空记忆」按钮
- 定期让 user 确认「这些记忆对吗」

## 实际选型流程

```
任务是什么类型的？
├─ 跟「历史对话」有关 → Memory
│  ├─ 跨 session 长期 → Long-term memory
│  ├─ 记具体的人和事 → Entity memory
│  └─ 短期当前 session → Short-term memory（默认）
│
└─ 跟「参考资料」有关 → Knowledge
   ├─ 产品手册 / 内部规范 → TextFile / PDF
   ├─ 结构化数据 → CSV / JSON
   └─ 大规模数据 → 配外部向量库
```

## Knowledge vs Tool 决策

| 场景 | 用 Knowledge | 用 Tool |
|------|-------------|---------|
| 产品手册 | ✅ | |
| 用户订单状态 | | ✅（实时） |
| 公司组织架构 | ✅ | |
| Slack 消息历史 | | ✅（实时拉） |
| 技术规范文档 | ✅ | |
| 调 LLM 总结文章 | | ✅（动态） |
| 股票历史价格 | ✅ | |
| 股票实时价格 | | ✅ |

**Rule of thumb**：数据是「不经常变 + 文本为主」用 Knowledge；「实时变化 + 结构化」用 Tool。

## Crew-level Memory

不光 Agent，整个 Crew 也能开 memory——所有 Agent 共享一份：

```python
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    memory=True,         # ← Crew-level memory
    memory_config={
        "provider": "mem0",   # 或 "chromadb"
        "config": {"path": "./crew_memory.db"},
    },
)
```

Crew-level memory 让多个 Agent 共享同一个 memory 后端。适合「多 Agent 共同维护一个客户档案」。

## 这章跑完之后你该会什么

- 区分 Memory（对话历史）和 Knowledge（参考资料）
- 启用 3 种 memory（short / long / entity）
- 给 Agent 挂 Knowledge Source（TXT / PDF / CSV / JSON）
- 知道 Knowledge vs Tool 怎么选
- 知道 5 个常见坑（文档太大 / 不更新 / 检索不到 / 跟 Tool 重复 / 旧记忆）

## 下篇

[06. 结构化输出与 Guardrail](../06-structured-output/) — Agent 输出乱七八糟怎么办？Pydantic 模型怎么锁输出、Guardrail 怎么拦截违规输出。
