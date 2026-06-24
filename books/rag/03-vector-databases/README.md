# 03. 向量数据库选型

> 向量数据库是 RAG 的「记忆」。选错数据库，百万级文档塞不下，或者检索慢到用户跑光。

## 主流选型（2026 版）

| 数据库 | 部署 | 亿级性能 | 混合检索 | 元数据过滤 | 适合场景 |
|---|---|---|---|---|---|
| **Chroma** | 嵌入式 / 服务 | 千万级 | ❌ | ✅ | 原型 / 小项目 |
| **pgvector** | Postgres 扩展 | 千万级 | ✅（BM25 + 向量）| ✅ 强 | 已有 PG 的项目 |
| **Qdrant** | 自托管 / 云 | **亿级** | ✅ | ✅ 强 | 中文首选生产 |
| **Pinecone** | 云 | 亿级 | ✅ | ✅ | 不想运维 |
| **Milvus** | 自托管 / 云 | **亿级** | ✅ | ✅ 强 | 大规模 + 多模态 |
| **Weaviate** | 自托管 / 云 | 千万级 | ✅ | ✅ 强 | 多模态 + GraphQL |

## 关键决策点

### 1. 数据规模

```
原型 / 小项目 (< 100 万文档)
  → Chroma（嵌入式，最快上手）

中型项目 (100 万 - 1000 万)
  → pgvector（如果已有 PG）或 Qdrant

大型项目 (> 1000 万)
  → Qdrant / Milvus / Pinecone
```

### 2. 混合检索需求

纯向量检索有盲点——**关键词完全匹配**的场景向量检索会失败：
- 用户搜「订单 #12345」→ embedding 模型不理解数字 ID
- 用户搜 `TypeError: cannot read property` → 代码搜索需要精确匹配

需要混合：**BM25（关键词）+ 向量（语义）**，第 7 章会展开。

**pgvector 和 Qdrant 都原生支持**——如果你确定要混合检索，二选一。

### 3. 元数据过滤

企业 RAG 几乎一定需要元数据过滤：
- 「只检索 2024 年的财报」
- 「只检索 IT 部门的文档」
- 「排除已废弃的文档」

数据库需要支持 **filter by metadata**。所有主流都支持，**pgvector 最强**（因为 PG 本来就有完整的 WHERE 子句）。

### 4. 部署模型

**自托管 vs 云**：

| | 自托管 | 云 |
|---|---|---|
| 数据合规 | ✅ 数据不出域 | ❌ 出域 |
| 成本 | 固定（机器费）| 按量（数据量 × 时间）|
| 运维 | 麻烦（升级、备份、监控）| 零运维 |
| 起步成本 | 高（要机器）| 低（按量起步）|

**生产 + 数据敏感 → 自托管 Qdrant / Milvus**
**原型 / MVP → 云 Pinecone / Qdrant Cloud**

## 实战：Qdrant 自托管

```bash
# Docker 启动 Qdrant
docker run -d \
    -p 6333:6333 \
    -v $(pwd)/qdrant_data:/qdrant/storage \
    qdrant/qdrant
```

```python
# 客户端
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance

client = QdrantClient(url="http://localhost:6333")

# 1. 创建 collection
client.create_collection(
    collection_name="docs",
    vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
)

# 2. 插入向量
def add_doc(chunk_id: str, embedding: list[float], text: str, metadata: dict):
    client.upsert(
        collection_name="docs",
        points=[PointStruct(
            id=chunk_id,
            vector=embedding,
            payload={"text": text, **metadata},
        )],
    )

# 3. 检索 Top-K
def search(query_emb: list[float], top_k: int = 5, filter_dict: dict = None):
    return client.search(
        collection_name="docs",
        query_vector=query_emb,
        limit=top_k,
        query_filter=Filter(must=[
            FieldCondition(key=k, match=MatchValue(value=v))
            for k, v in (filter_dict or {}).items()
        ]) if filter_dict else None,
    )

# 使用
results = search(query_emb, top_k=5, filter_dict={"year": 2025})
for r in results:
    print(f"score={r.score:.3f}  {r.payload['text'][:80]}...")
```

## 实战：pgvector（如果已有 PG）

```sql
-- 启用扩展
CREATE EXTENSION vector;

-- 建表
CREATE TABLE docs (
    id BIGSERIAL PRIMARY KEY,
    chunk_id TEXT UNIQUE NOT NULL,
    embedding vector(1024),  -- 维度匹配 embedding 模型
    text TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 建索引（HNSW 是 2026 推荐算法）
CREATE INDEX ON docs USING hnsw (embedding vector_cosine_ops);
```

```python
import psycopg
from pgvector.psycopg import register_vector

conn = psycopg.connect("postgresql://...")
register_vector(conn)

def add_doc(chunk_id, embedding, text, metadata):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO docs (chunk_id, embedding, text, metadata) VALUES (%s, %s, %s, %s)",
            (chunk_id, embedding, text, metadata),
        )
    conn.commit()

def search(query_emb, top_k=5, year=None):
    sql = """
        SELECT text, metadata, 1 - (embedding <=> %s) AS score
        FROM docs
        WHERE (%s IS NULL OR (metadata->>'year')::int = %s)
        ORDER BY embedding <=> %s
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (query_emb, year, year, query_emb, top_k))
        return cur.fetchall()
```

## 常见坑

### 1. 索引选错

- **HNSW**：召回高、查询快、但内存大（亿级数据要几十 GB RAM）
- **IVFFlat**：内存小、但召回稍差、训练时间长

新项目**默认 HNSW** 即可。除非你确定内存不够。

### 2. 距离度量搞错

| 度量 | 适用 |
|---|---|
| Cosine | **文本 embedding 通用**（推荐）|
| Euclidean | 图像 embedding |
| Dot Product | 已归一化的向量 |

OpenAI / BGE / m3e 的向量都是**未归一化**——必须用 Cosine。

### 3. upsert vs insert

向量数据经常会**重新处理**（换 embedding 模型、改 chunking）。数据库要支持 upsert（按 id 更新），不然每次全量重灌。

### 4. 备份和迁移

向量数据**不容易迁移**（不像 SQL 数据可导出 CSV）。选定数据库前考虑：
- 备份方案
- 迁移到另一家的成本
- 数据量增长后的扩容路径

## 下篇

[04. Chunking 策略](../04-chunking-strategies/) — 文档怎么切块最影响 RAG 效果。
