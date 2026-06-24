# 05. 通信与状态

> 上章 5 种编排模式决定 Agent 之间怎么连。这章往下走一层：连起来后数据怎么传、状态怎么管。这是工程问题，跟编排模式那种架构图层面的事不一样。

## 本章要回答的问题

1. Agent 之间用什么格式传消息？
2. 多个 Agent 需要共享数据时，是传值还是共享内存？
3. 什么时候用"黑板"模式，什么时候用"点对点"？
4. 状态隔离 vs 共享，trade-off 是什么？

---

## 通信的 3 个层次

### Layer 1：消息协议（Message Protocol）

Agent 之间传什么格式的数据？

```
格式 1：自然语言字符串
└─ "我调研了 3 个框架：FastAPI / Django / Flask"

格式 2：结构化 JSON
└─ {"frameworks": ["FastAPI", "Django", "Flask"], "facts": [...], "sources": [...]}

格式 3：Pydantic / TypedDict 模型
└─ class ResearchResult(BaseModel): frameworks: list[str]; facts: list[Fact]
```

**推荐**：生产用 Pydantic 模型。理由：

1. **类型安全**：下游 Agent 知道字段，不用解析字符串
2. **可验证**：可以加 Pydantic validator
3. **可序列化**：直接 dump 成 JSON 存数据库
4. **可观察**：trace 工具能识别字段含义

完整代码：[`code/01_message_protocol.py`](./code/01_message_protocol.py)

---

### Layer 2：传递模式（Transfer Pattern）

数据从一个 Agent 到另一个 Agent 怎么走？

```
模式 A：Pass-by-Value（值传递）
└─ A 把输出塞到 B 的 input → B 处理
   例子：CrewAI 的 context=[task_a]

模式 B：Pass-by-Reference（引用传递）
└─ A 把数据写入共享 store → B 从 store 读
   例子：LangGraph 的 State

模式 C：Broadcast（广播）
└─ A 的输出同时给 B / C / D
   例子：LangGraph 的 Send API
```

**什么时候用什么**：

| 场景 | 推荐模式 | 原因 |
|------|---------|------|
| 简单线性流程 | Pass-by-Value | 简单清晰 |
| 多 Agent 共享数据 | Pass-by-Reference | 避免重复传 |
| 一个输出给多个下游 | Broadcast | 并行高效 |

完整代码：[`code/02_pass_by_value.py`](./code/02_pass_by_value.py) 和 [`code/03_broadcast.py`](./code/03_broadcast.py)

---

### Layer 3：状态管理（State Management）

整个 Multi-Agent 系统的状态怎么组织？

```
方案 1：单一大 State
└─ 所有 Agent 操作同一个 dict
   优点：简单
   缺点：所有 Agent 都能改任何字段，难追踪

方案 2：分层 State
└─ 每个 Agent 有自己的 State + 共享 State
   优点：隔离 + 共享兼顾
   缺点：需要设计 State 结构

方案 3：外部数据库
└─ Agent 把数据写入 Postgres / Redis
   优点：可持久化、可跨会话
   缺点：增加 IO，状态一致性需要管理
```

**推荐**：LangGraph 的方案 2（TypedDict State），按节点定义读写权限。

完整代码：[`code/04_state_management.py`](./code/04_state_management.py)

---

## 黑板模式 vs 点对点

### 黑板模式（Blackboard）

```
┌─────────────────────────────────┐
│      Blackboard（共享）          │
│  ┌─────┐ ┌─────┐ ┌─────┐       │
│  │Key A│ │Key B│ │Key C│       │
│  └─────┘ └─────┘ └─────┘       │
└─────────────────────────────────┘
   ↑    ↑    ↑    ↑    ↑
   │    │    │    │    │
   A    B    C    D    E
```

所有 Agent 读 / 写同一块共享内存。

**适用**：

- 多个 Agent 需要看到完整上下文
- 任务没有明确流程（每个 Agent 自己决定做什么）
- 知识需要持续累积

**反模式**：

- Agent 之间数据流是线性的（用 Pass-by-Value 即可）
- 调试时需要追溯"谁改了哪个 key"（黑板模式难定位）

### 点对点（Point-to-Point）

```
A ──→ B ──→ C ──→ D
```

数据沿着边走，每个 Agent 只看到上游传过来的。

**适用**：

- 流程清晰
- 每个 Agent 的输入只来自特定上游
- 调试时需要 step into 每一步

**反模式**：

- 多个 Agent 需要同一份数据（重复传）

---

## 状态隔离 vs 共享：Trade-off

```
隔离（每个 Agent 自己的 state）
✅ 调试简单（每个 Agent 互不影响）
✅ 不需要考虑并发
❌ 共享数据要重复传（token 翻倍）

共享（所有 Agent 操作同一 state）
✅ 数据一次写入，多处读取
✅ 实时看到其他 Agent 的进展
❌ 并发冲突（两个 Agent 同时写一个 key）
❌ 调试困难（不知道谁改了什么）
```

**生产推荐**：

- 默认隔离
- 必须共享的数据用显式 channel（CrewAI context、LangGraph State）
- 避免"所有 Agent 都能改整个 state"

---

## 实战：通信反模式

### 反模式 1：传自然语言 blob

```python
# 反模式
agent_a_output = "我调研了 3 个框架，它们分别是..."

agent_b_prompt = f"基于 A 的调研：{agent_a_output}"
# ↑ B 要自己解析自然语言，提取结构
```

修复：

```python
from pydantic import BaseModel

class ResearchResult(BaseModel):
    frameworks: list[str]
    facts: dict[str, list[str]]

agent_a_output: ResearchResult = ...
agent_b_input = agent_a_output  # ← 直接传结构化对象
```

### 反模式 2：超大消息

```python
# 反模式：把整个代码库塞进消息
messages.append({"role": "user", "content": open("codebase.zip", "rb").read()})
# ↑ 5MB 代码进 context，token 爆炸
```

修复：

```python
# 传引用，不传内容
messages.append({"role": "user", "content": "代码在 codebase.zip，请用 read_file 工具按需读取"})
```

### 反模式 3：循环引用

```python
# 反模式：A 把 state 传给 B，B 又把 state 传回 A
# → 死循环
```

修复：明确有向无环图（DAG），用 LangGraph 自动检测。

---

## 通信安全

Agent 之间传数据的安全注意事项：

1. **不要传密钥**：state 里的 API key 会被序列化到日志
2. **验证输入**：下游 Agent 假设上游可能传脏数据
3. **大小限制**：单条消息不超过 100KB（防止 OOM）
4. **TTL**：state 里的数据有过期时间（防止用陈旧数据）

---

## 本章小结

- 3 个层次：**消息协议 / 传递模式 / 状态管理**
- 推荐 Pydantic 模型做消息协议（类型安全 + 可验证）
- 默认隔离，按需共享
- 黑板模式适合开放式问题，点对点适合线性流程

## 下篇

[06. 失败的艺术](../06-failure-handling/) — Multi-Agent 系统的失败是单 Agent 的 N 倍，讲怎么防御。

## 生产化提示

通信的工程化：

- **消息协议**：用 Pydantic 做 schema 化，加 validator
- **传递模式**：Pass-by-Value 用 CrewAI context，Pass-by-Reference 用 LangGraph State
- **状态管理**：用 LangGraph 的 TypedDict State，按节点定义读写权限
- **监控**：每条消息记录来源、大小、耗时
- **告警**：单条消息 > 1MB 告警，单次 session 状态 > 10MB 告警