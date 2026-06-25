# 06. 向量数据库：选型与实战

向量数据库（Vector DB）是长期记忆系统的**基础设施**——episodic memory 和部分 semantic memory 都靠它。这一章讲清楚主流向量库的对比、选型、实战经验。

## 2026 年向量库全景

我把主流向量库分成 3 类：

### 第一类：传统数据库加向量能力

**PostgreSQL + pgvector**

- 优点：单机一站式、SQL 查询成熟、运维简单
- 缺点：>1 亿向量慢
- 适合：中小规模（< 5000 万向量）

**Elasticsearch 8+**

- 优点：本身就适合全文检索，加 dense_vector 字段后支持语义检索
- 缺点：向量检索性能比专用库差
- 适合：需要全文 + 语义混合检索

**MongoDB Atlas Vector Search**

- 优点：MongoDB 用户无缝接入
- 缺点：性能中等
- 适合：已经在用 MongoDB 的团队

### 第二类：专用向量库（云服务）

**Pinecone**

- 优点：全托管、性能强、文档好
- 缺点：贵、vendor lock-in
- 适合：不想运维的中大型团队
- 价格：$0.096 / GB-月（serverless 模式）

**Weaviate Cloud**

- 优点：开源 + 托管、内置 vectorization 模块
- 缺点：性能略弱于 Pinecone
- 适合：需要 GraphQL 接口的场景

**Qdrant Cloud**

- 优点：Rust 写的、性能好、支持丰富 metadata 过滤
- 缺点：生态比 Pinecone 弱
- 适合：metadata 过滤复杂的场景

### 第三类：开源自部署

**Milvus**

- 优点：国产、CNCF 项目、生态丰富
- 缺点：架构复杂、运维门槛高
- 适合：大规模生产（亿级向量）

**Qdrant（自部署）**

- 优点：单二进制部署、性能好
- 缺点：生态较小
- 适合：中小规模自部署

**Chroma**

- 优点：Python 原生、轻量、适合原型
- 缺点：不适合生产
- 适合：本地开发、demo

**LanceDB**

- 优点：基于列存储、单机性能强、支持 SQL
- 缺点：生态新
- 适合：嵌入式 / 边缘部署

## 选型决策树

```
你的场景是什么？
│
├─ 数据量 < 100 万向量
│  └─ 已经在用 PostgreSQL？
│     ├─ 是 → pgvector（首选）
│     └─ 否 → Chroma（原型）/ pgvector（生产）
│
├─ 数据量 100 万 - 1 亿
│  └─ 预算 ≥ $500/月？
│     ├─ 是 → Pinecone（全托管，省心）
│     └─ 否 → Qdrant 自部署（性能好、运维简单）
│
└─ 数据量 > 1 亿
   └─ Milvus（大规模首选）
```

## pgvector 实战（最常见选择）

大部分 agent 系统 90% 的场景 pgvector 够用。这里讲实战。

### 安装

```bash
# PostgreSQL 16+ 自带
CREATE EXTENSION IF NOT EXISTS vector;

# 或 Docker
docker run -d --name pgvector -p 5432:5432 \
  -e POSTGRES_PASSWORD=xxx \
  pgvector/pgvector:pg16
```

### 建表

```sql
CREATE TABLE episodic_events (
    event_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),  -- OpenAI text-embedding-3-small 维度
    metadata JSONB,
    parent_event_id TEXT
);

-- 向量索引（IVFFlat）
CREATE INDEX events_embedding_idx ON episodic_events 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 元数据过滤索引
CREATE INDEX events_user_timestamp_idx ON episodic_events (user_id, timestamp DESC);
CREATE INDEX events_metadata_idx ON episodic_events USING GIN (metadata jsonb_path_ops);
```

`lists = 100` 是经验值，约等于 `sqrt(行数)`。1000 万行用 lists=3000 左右。

### 写入

```python
async def write_event(event: EpisodicEvent):
    if not event.embedding:
        event.embedding = await embed(event.content)
    
    await conn.execute(
        """
        INSERT INTO episodic_events 
            (event_id, user_id, session_id, timestamp, type, content, embedding, metadata, parent_event_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """,
        event.event_id, event.user_id, event.session_id, event.timestamp,
        event.type, event.content, event.embedding, json.dumps(event.metadata),
        event.parent_event_id,
    )
```

### 检索（带 metadata 过滤）

```sql
SELECT 
    event_id,
    content,
    metadata,
    timestamp,
    1 - (embedding <=> $1) AS similarity  -- 余弦相似度
FROM episodic_events
WHERE 
    user_id = $2
    AND timestamp >= $3
    AND metadata->>'tags' ?| $4  -- 任一 tag 匹配
ORDER BY embedding <=> $1  -- 向量距离排序
LIMIT $5;
```

`<=>` 是 pgvector 的 cosine distance 操作符。值越小越相似。

### 性能调优

**1. 选对索引类型**

- **IVFFlat** — 训练快、查询快、内存占用中等。适合大多数场景。
- **HNSW** — 查询最快、内存占用大。适合查询性能要求高的场景。

```sql
-- HNSW（推荐生产用）
CREATE INDEX events_embedding_hnsw ON episodic_events 
USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- IVFFlat（数据量小时）
CREATE INDEX events_embedding_ivf ON episodic_events 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

**2. 调查询参数**

```sql
-- HNSW 查询时设置 ef_search
SET hnsw.ef_search = 100;  -- 默认 40，越大越精确但越慢
```

**3. 数据分片**

> 1 亿向量时考虑按 `user_id` 分表：

```sql
-- 按用户 ID hash 分 16 张表
CREATE TABLE episodic_events_0 (LIKE episodic_events INCLUDING ALL);
CREATE TABLE episodic_events_1 (LIKE episodic_events INCLUDING ALL);
-- ...
CREATE TABLE episodic_events_15 (LIKE episodic_events INCLUDING ALL);

-- 写入时按 hash 分
INSERT INTO episodic_events_${hash(user_id) % 16} VALUES (...);
```

## Pinecone 实战（如果用云）

```python
from pinecone import Pinecone, ServerlessSpec

pc = Pinecone(api_key="xxx")
index = pc.create_index(
    name="agent-memory",
    dimension=1536,
    metric="cosine",
    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
)

# 写入
index.upsert(vectors=[
    {
        "id": "evt_001",
        "values": embedding,
        "metadata": {
            "user_id": "u_123",
            "timestamp": "2026-06-01T10:23:45Z",
            "type": "question",
            "tags": ["risk", "shanghai"],
        }
    }
])

# 检索
results = index.query(
    vector=query_embedding,
    filter={
        "user_id": {"$eq": "u_123"},
        "timestamp": {"$gte": "2026-01-01T00:00:00Z"},
    },
    top_k=10,
    include_metadata=True,
)
```

Pinecone 的 metadata 过滤语法支持 `$eq`、`$in`、`$gte`、`$lt`、`$and`、`$or` 等。

## Embedding 模型选型

**2026 年 6 月主流 embedding 模型**：

| 模型 | 维度 | 价格（每 1M token） | 性能 |
|------|------|---------------------|------|
| OpenAI text-embedding-3-small | 1536 | $0.02 | 强 |
| OpenAI text-embedding-3-large | 3072 | $0.13 | 最强 |
| Voyage-3 | 1024 | $0.06 | 强（专门优化 retrieval） |
| Cohere embed-v3 | 1024 | $0.10 | 强 |
| BGE-large-en-v1.5 | 1024 | 免费（开源） | 中 |
| BGE-large-zh-v1.5 | 1024 | 免费（开源） | 中文强 |
| M3-Embedding | 1024 | 免费（开源） | 多语言强 |

**实战推荐**：

- 英文为主：**OpenAI text-embedding-3-small**（便宜、性能强）
- 中文为主：**BGE-large-zh-v1.5**（免费、性能强、本地部署）
- 多语言：**M3-Embedding**

## 实战性能数据

**pgvector + HNSW + text-embedding-3-small（100 万向量）**：

- 写入：500 events/s
- 检索（纯向量）：15ms P95
- 检索（带 metadata 过滤）：25ms P95

**Pinecone serverless（1 亿向量）**：

- 写入：5000 events/s
- 检索：50ms P95
- 月成本：$500-2000（取决于规模）

90% 的 agent 系统 pgvector 完全够用。我自己跑了 8 个月，500 万事件，性能稳定。

下一章讲知识图谱——semantic memory 的关系推理能力靠它。