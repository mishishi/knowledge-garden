# 04. Episodic Memory：事件流存储

Episodic memory（情景记忆）是 3 层记忆里**数据量最大、查询频率最高、技术最成熟**的一层。本质就是一个事件流数据库 + 向量检索能力。

## 核心数据结构

每个事件是一条记录：

```python
class EpisodicEvent:
    event_id: str              # 唯一 ID（如 evt_20260601_001）
    user_id: str               # 用户 ID
    session_id: str            # 会话 ID
    timestamp: datetime        # 事件时间
    type: str                  # 事件类型：question / action / observation / feedback
    content: str               # 事件内容
    embedding: list[float]     # 1536 维向量（OpenAI text-embedding-3-small）
    metadata: dict             # 结构化元数据
    parent_event_id: str       # 父事件（用于事件链追溯）
    
    # 元数据示例
    # {
    #   "agent": "risk-analyst",
    #   "tools_used": ["postgres_query"],
    #   "result_summary": "违约率 2.3%",
    #   "user_satisfaction": 4.5,
    #   "tags": ["risk", "shanghai", "demographics"],
    #   "duration_ms": 2300,
    #   "tokens_used": 4500,
    # }
```

## 存储选型

3 个主流方案：

**方案 1：PostgreSQL + pgvector**

适合中小规模（< 1 亿事件），单机部署。

```sql
CREATE TABLE episodic_events (
    event_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),  -- pgvector
    metadata JSONB,
    parent_event_id TEXT
);

CREATE INDEX ON episodic_events USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX ON episodic_events (user_id, timestamp DESC);
CREATE INDEX ON episodic_events USING GIN (metadata);
```

**优点**：一站式解决方案、SQL 查询能力成熟、运维简单。

**缺点**：向量检索性能比专用向量库差，>1 亿事件慢。

**方案 2：专用向量库 + 关系数据库**

Pinecone / Weaviate / Milvus / Qdrant 存向量 + embedding 元数据，PostgreSQL 存完整事件内容。

```python
# 写入
async def write_event(event: EpisodicEvent):
    # 向量库存向量 + 元数据
    await vector_db.upsert(
        id=event.event_id,
        values=event.embedding,
        metadata={
            "user_id": event.user_id,
            "timestamp": event.timestamp.isoformat(),
            "type": event.type,
            "tags": event.metadata.get("tags", []),
        }
    )
    # 关系库存完整事件
    await postgres.execute(
        "INSERT INTO events (...) VALUES (...)",
        event.to_dict()
    )

# 检索
async def search_events(user_id, query, top_k=10):
    # 向量检索
    query_embedding = await embed(query)
    hits = await vector_db.search(
        vector=query_embedding,
        filter={"user_id": user_id},
        top_k=top_k * 2,  # 多取一些
    )
    # 关系库拿完整内容
    event_ids = [hit.id for hit in hits]
    events = await postgres.fetch(
        "SELECT * FROM events WHERE event_id = ANY($1)",
        event_ids,
    )
    return events
```

**优点**：向量检索性能最好、可扩展到 10 亿+ 事件。

**缺点**：双写一致性问题（要保证向量库和关系库同步）、运维两套系统。

**方案 3：单库一体化（Qdrant / LanceDB）**

新派向量库（Qdrant / LanceDB）支持丰富 metadata 过滤，能替代 PostgreSQL。

**优点**：一套系统、单写一致。

**缺点**：成熟度不如 PostgreSQL，部分高级查询不支持。

**实战推荐**：

- < 1000 万事件：**方案 1（pgvector）**
- > 1000 万事件：**方案 2（专用向量库 + PG）**
- 极致性能要求：**方案 3（Qdrant）**

## 写入策略

**何时写入**：

不是每条消息都写 episodic memory——那样存储爆炸。一般 3 类事件写入：

**a. 用户明确表达偏好 / 规则**

"我不喝咖啡"→ 写入，tags=["preference", "beverage"]

**b. 重要任务完成 / 失败**

agent 完成任务后写入，包括任务描述、结果、用户反馈。

**c. 错误 / 异常**

agent 出错时写入，包括错误描述、根因、修复方式——便于后续"从错误中学习"。

**写入触发**：

```python
async def should_write_to_episodic(message, response, metadata):
    # 用户明确表达偏好
    if detect_preference_expression(message):
        return True
    
    # 任务完成
    if metadata.get("task_completed"):
        return True
    
    # 任务失败
    if metadata.get("task_failed"):
        return True
    
    # 错误
    if metadata.get("error"):
        return True
    
    return False
```

## 检索策略

**检索维度**：3 个维度组合

**a. 语义检索**（向量相似度）

```python
results = await vector_db.search(
    vector=query_embedding,
    top_k=10,
)
```

适合："类似的问题以前怎么处理的"

**b. 元数据过滤**（结构化查询）

```python
results = await vector_db.search(
    vector=query_embedding,
    filter={
        "user_id": "u_123",
        "type": "question",
        "timestamp": {"$gte": "2026-01-01"},
        "tags": {"$in": ["risk"]},
    },
    top_k=10,
)
```

适合："用户 X 在 2026 Q1 关于风险的所有问题"

**c. 时序窗口**（最近 / 特定时间段）

```python
# 最近 7 天
results = await fetch_events(
    user_id="u_123",
    since=datetime.now() - timedelta(days=7),
)
```

适合："用户最近问过什么"

**实战组合**：

```python
async def retrieve_relevant_events(user_id, query, max_results=10):
    # 1. 语义检索
    query_emb = await embed(query)
    semantic_hits = await vector_db.search(
        vector=query_emb,
        filter={"user_id": user_id},
        top_k=20,  # 多取一些，过滤后取 top
    )
    
    # 2. 重新排序（结合时间 + 满意度）
    reranked = rerank_by_recency_and_quality(semantic_hits)
    
    return reranked[:max_results]
```

重新排序考虑：

- **时间衰减**（越近的事件权重越高）
- **质量权重**（用户高评分的事件权重更高）
- **多样性**（不要全是同一类事件）

## 实战性能数据

pgvector 在 500 万事件规模下：

- 写入：1000 events/s
- 检索（带 metadata 过滤）：50ms P95
- 检索（纯语义）：30ms P95

专用向量库（Pinecone）在 5 亿事件规模下：

- 写入：10K events/s
- 检索：< 100ms P99

如果你的 agent 系统事件量 < 100 万 / 月，pgvector 完全够用。

## 实战代码骨架

```python
class EpisodicMemory:
    def __init__(self, db):
        self.db = db  # pgvector / Qdrant / Pinecone
    
    async def write(self, event: EpisodicEvent):
        # 计算 embedding
        if not event.embedding:
            event.embedding = await embed(event.content)
        await self.db.insert(event)
    
    async def recall(self, user_id: str, query: str, top_k: int = 10) -> list[EpisodicEvent]:
        # 语义检索
        query_emb = await embed(query)
        hits = await self.db.search(
            vector=query_emb,
            filter={"user_id": user_id},
            top_k=top_k * 3,
        )
        
        # 重排序：时间近 + 质量高 + 多样性
        reranked = self._rerank(hits)
        
        return reranked[:top_k]
    
    def _rerank(self, hits):
        now = datetime.now()
        scored = []
        for hit in hits:
            recency = 1.0 / (1 + (now - hit.timestamp).days)
            quality = hit.metadata.get("user_satisfaction", 3.0) / 5.0
            score = 0.6 * recency + 0.4 * quality
            scored.append((score, hit))
        scored.sort(reverse=True, key=lambda x: x[0])
        return [hit for _, hit in scored]
```

下一章讲 Semantic Memory——怎么从情景记忆提炼出抽象知识。