# 03. 向量数据库选型

> 向量数据库是 RAG 的「记忆」。选错数据库，百万级文档塞不下，或者检索慢到用户跑光。这一章讲 2026 年的主流选型 + 决策路径 + 我自己选错的代价。

## 主流选型

我自己用过 / 评估过的 6 个：

| 数据库 | 部署 | 亿级性能 | 混合检索 | 元数据过滤 | 适合场景 |
|---|---|---|---|---|---|
| **Chroma** | 嵌入式 / 服务 | 千万级 | 否 | 基础 | 原型 / 小项目 |
| **pgvector** | Postgres 扩展 | 千万级 | 是（BM25 + 向量）| 强 | 已有 PG 的项目 |
| **Qdrant** | 自托管 / 云 | 亿级 | 是 | 强 | 中文首选生产 |
| **Pinecone** | 云 | 亿级 | 是 | 是 | 不想运维 |
| **Milvus** | 自托管 / 云 | 亿级 | 是 | 强 | 大规模 + 多模态 |
| **Weaviate** | 自托管 / 云 | 千万级 | 是 | 强 | 多模态 + GraphQL |

## 数据规模怎么选

不是看「我现在有多少文档」，是看「12 个月后会有多少」。向量数据库迁移成本很高（要 re-embed + reindex），最好一次选对。

我自己用的决策路径：

**原型 / 小项目（< 100 万文档）**——Chroma 嵌入式，一行代码启动，最快上手。Python 原生 API，适合 hobby / side project。

**中型项目（100 万 - 1000 万）**——pgvector（如果已有 PG）或 Qdrant。pgvector 跟业务数据合一，ACID 保证，但百万级后性能下降；Qdrant 是 Rust 写的，性能更好，自带 server 部署简单。

**大型项目（> 1000 万）**——Qdrant / Milvus / Pinecone。Milvus 支持多模态（图像 / 视频 embedding），Pinecone 全托管最省心但要钱。

我第一版 RAG 项目选了 Chroma，3 个月后塞到 50 万文档就明显慢（单次检索从 30ms 涨到 800ms）。迁移到 Qdrant 后稳定在 50ms 以内。教训：**别只看「现在」规模，预估 12 个月后再选**。

## 纯向量检索有盲点

向量检索擅长语义相似（"天气怎么样" → "今天下雨吗"），不擅长精确匹配。这两类场景必须配 BM25 混合检索：

- 用户搜「订单 #12345」——embedding 模型不理解数字 ID，纯向量检索返回一堆「#1234」「#12346」相近结果
- 用户搜 `TypeError: cannot read property` ——代码搜索需要精确匹配关键词，纯向量检索匹配到「error」语义的段落
- 用户搜「OpenAI」品牌名——想精确找到提到 OpenAI 的文档，不想返回「AI 公司」语义的

混合检索 = 向量检索 top-50 + BM25 检索 top-50 + rerank 融合。Qdrant / pgvector / Milvus / Pinecone / Weaviate 都原生支持，Chroma 不支持（要自己组合）。

我自己 RAG 项目上线后**纯向量检索的召回率 71%，混合检索的召回率 89%**——混合 +18 个百分点，主要是关键词类查询拉高的。

## 元数据过滤

向量检索只解决了「找相似」，没解决「找这个用户能看的」。元数据过滤让你在检索时同时按 user_id / department / doc_type 等过滤：

```python
# Qdrant 例子
results = qdrant.search(
    query_vector=embed(query),
    query_filter=Filter(must=[
        FieldCondition(key="department", match=MatchValue(value="engineering")),
        FieldCondition(key="created_at", range=Range(gte=datetime(2024, 1, 1))),
    ]),
    limit=10,
)
```

我自己用元数据过滤做权限隔离（每个用户只检索自己有权限的文档）、时间过滤（"最近 1 年的项目文档"）、类别过滤（"只检索技术文档不检索 HR 政策"）。

pgvector 的元数据过滤最强（跟 PostgreSQL 一样的 JSONB query），其他几个都支持基础 filter。Chroma 也支持但功能较弱。

## 混合检索实战

我自己项目里用的 Qdrant 混合检索配置：

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

client = QdrantClient(url="http://localhost:6333")

# 混合检索：向量 + BM25
results = client.search(
    collection_name="docs",
    query_vector=embed(query),  # dense vector
    query_bm25=bm25_encode(query),  # sparse vector
    fusion="rrf",  # reciprocal rank fusion
    limit=10,
    query_filter=Filter(must=[
        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
    ]),
)
```

RRF（Reciprocal Rank Fusion）是把向量 top-K 和 BM25 top-K 的排名融合的标准方法。比简单加权平均稳定，不需要调权重。

## 中文场景的特殊考虑

中文 embedding 模型（bge-large-zh / m3e-large / text2vec-large-chinese）跟英文模型在向量空间分布不一样。Qdrant 在中文 RAG 圈用得最多（社区贡献了大量中文优化）。Chroma 也能跑中文但检索质量稍差（社区反馈，我没做严谨 A/B）。

我自己的中文 RAG 项目选 Qdrant 不是因为最强，是因为社区问题能搜到答案。Milvus / Weaviate 功能更强但中文资料少，踩坑 debug 成本高。

## 运维成本

向量数据库一旦上 production，运维是最大的隐性成本。

Chroma 嵌入式几乎零运维（进程内）——但不能跨进程访问，多副本要自己同步。

pgvector 跟 PG 一起运维——如果团队已有 PG DBA，几乎零额外成本。

Qdrant / Milvus 自带 server——要起 Docker / k8s 部署、监控 disk usage、做 backup。

Pinecone / Weaviate Cloud——全托管，自己不用运维，但要钱（Pinecone 标准版 $70/月起）。

我自己的 side project 选 Chroma（零成本），production 项目选 Qdrant 自托管（一次部署 + 日常监控）。从没用过 Pinecone——个人项目没预算买这个。

## 我的决策 checklist

- 文档量 < 100 万 + 不需要混合检索 → Chroma
- 已有 PG + 中等规模 → pgvector
- 文档量 > 1000 万 + 团队有运维能力 → Qdrant / Milvus
- 不想要运维 + 有预算 → Pinecone
- 多模态（图像 + 文本）→ Milvus / Weaviate

我自己的实际选型：side project 全用 Chroma（4 个项目），production 2 个用 Qdrant（中文 RAG + 多租户文档检索），1 个用 pgvector（团队已有 PG 不想引新组件）。

[04. Chunking 策略](../04-chunking-strategies/) 讲文档怎么切块——chunk size 选错，retrieval 召回率能差 30 个百分点。
