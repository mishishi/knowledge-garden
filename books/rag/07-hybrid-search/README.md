# 07. 混合检索：向量 + 关键词

> 纯向量检索在「数字 ID / 专有名词 / 代码错误」场景会失灵。**混合检索** 是企业 RAG 的标配。

## 纯向量检索的盲点

**场景 1：搜订单号**
- 用户：「订单 #20240615-abc 状态？」
- Embedding 模型不理解数字 ID，订单号在向量空间里和普通数字没差别
- 检索：「订单 20240615 abc 状态」→ 召回一堆不相关

**场景 2：搜代码错误**
- 用户：「TypeError: cannot read property 'name' of undefined 怎么修？」
- 向量相似度匹配会返回任何提到 TypeError 的文档，可能完全不相关

**场景 3：搜专有名词**
- 用户：「GDPR 第 17 条是什么？」
- 缩写「GDPR」可能没在训练语料里有充分 embedding 表达

**共同点**：需要**精确匹配**，不是语义相似。

## 解法：Hybrid Search

**两条路并行召回，最后融合**：

```
用户问题
  ↓
  ├─→ 向量检索 Top-50（语义相似）
  └─→ BM25 关键词检索 Top-50（精确匹配）
            ↓
        Reciprocal Rank Fusion（融合排序）
            ↓
        Top-K 喂给 Rerank + LLM
```

## BM25：经典关键词检索

BM25 是 1990 年代的算法，**专门做关键词匹配**，比 TF-IDF 强。Python 实现：

```python
from rank_bm25 import BM25Okapi
import jieba  # 中文分词

# 准备语料
corpus = [
    "订单 20240615-abc 已发货",
    "用户问订单状态查询方法",
    "TypeError cannot read property name",
    # ... 每条 = 一个 chunk 的 text
]

# 中文分词
tokenized_corpus = [list(jieba.cut(doc)) for doc in corpus]
bm25 = BM25Okapi(tokenized_corpus)

# 检索
def bm25_search(query: str, top_k=50):
    tokenized_query = list(jieba.cut(query))
    scores = bm25.get_scores(tokenized_query)
    top_indices = sorted(range(len(scores)), key=lambda i: -scores[i])[:top_k]
    return [
        {"text": corpus[i], "score": scores[i], "idx": i}
        for i in top_indices
    ]
```

**关键**：**中文必须先分词**（用 jieba）。否则「订单 20240615 abc」会被当成一整个词，BM25 算不出匹配。

## 融合：Reciprocal Rank Fusion (RRF)

两条路返回两个排序列表，怎么融合？**RRF**（简单有效）：

```python
def rrf_fuse(vector_results, bm25_results, k=60) -> list[dict]:
    """
    RRF 公式: score(doc) = Σ 1 / (k + rank)
    k 通常 60，越大对排名靠后的越宽容
    """
    scores = {}
    for rank, hit in enumerate(vector_results):
        doc_id = hit["id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
    for rank, hit in enumerate(bm25_results):
        doc_id = hit["id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)

    # 按融合分数排序
    all_docs = {hit["id"]: hit for hit in vector_results + bm25_results}
    ranked = sorted(
        [{"id": doc_id, "score": score, **all_docs[doc_id]}
         for doc_id, score in scores.items()],
        key=lambda x: -x["score"]
    )
    return ranked
```

**为什么 RRF 有效**：
- 不需要归一化两路分数（向量是 0-1 cosine，BM25 是 0-30）
- 排名靠前的权重指数衰减，**「在两路都进 Top-5」** 的文档自然排前
- 简单、可解释、无超参

## 用 Qdrant 自带的混合检索

Qdrant 1.10+ 支持 **sparse vectors**（类似 BM25）原生融合：

```python
from qdrant_client.models import (
    SparseVector, NamedSparseVector, PointStruct, VectorParams,
    Distance, SparseVectorParams, Modifier,
)

# 1. 创建 collection（同时有 dense + sparse）
client.create_collection(
    collection_name="docs",
    vectors_config={"dense": VectorParams(size=1024, distance=Distance.COSINE)},
    sparse_vectors_config={
        "sparse": SparseVectorParams(modifier=Modifier.IDF),
    },
)

# 2. 入库时同时计算 dense 和 sparse
def add_doc(chunk_id, text):
    dense = emb_model.encode(text).tolist()
    sparse_indices, sparse_values = bm25_encoder.encode(text)
    client.upsert(
        collection_name="docs",
        points=[PointStruct(
            id=chunk_id,
            vector={
                "dense": dense,
                "sparse": SparseVector(indices=sparse_indices, values=sparse_values),
            },
            payload={"text": text},
        )],
    )

# 3. 检索：原生 hybrid query
from qdrant_client.models import Prefetch, FusionQuery, Fusion

results = client.query_points(
    collection_name="docs",
    prefetch=[
        Prefetch(query=dense_query_emb, using="dense", limit=50),
        Prefetch(query=sparse_query_emb, using="sparse", limit=50),
    ],
    query=FusionQuery(fusion=Fusion.RRF),
    limit=10,
)
```

**优势**：Qdrant 内部 RRF 融合，比 Python 层手动融合快 30-50%。

## 实战：用 FastEmbed + Qdrant 一行 hybrid

[FastEmbed](https://github.com/qdrant/fastembed) 把 dense + sparse 打包：

```python
from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient

dense_model = TextEmbedding("BAAI/bge-m3")
sparse_model = SparseTextEmbedding("Qdrant/bm25")

# 同时算 dense 和 sparse
texts = ["文档 1 内容", "文档 2 内容"]
dense_embs = list(dense_model.embed(texts))
sparse_embs = list(sparse_model.embed(texts))

# 入库 + 检索参考上一节
```

## 何时纯向量够用、何时必须混合

| 场景 | 纯向量 | 混合 |
|---|---|---|
| 文档内容都是自然语言、无专有名词 | 够 | over-engineering |
| 数字 ID、版本号、错误码 | | 必须 |
| 中英混排（公司名 + 产品名）| | |
| 用户问题有具体缩写（K8s、GDPR）| | |
| 法律 / 医疗 / 金融专有术语 | | |
| 聊天 / 闲聊类（无明确答案）| 够 | over-engineering |

**默认上混合**——多花 20% 推理时间，召回率提升 15-30%。

## 性能权衡

混合检索 = 向量检索 + BM25，两路都跑：

```python
# pgvector + ES 混合（如果已有这套）
def hybrid_search_pg(query, top_k=10):
    # 向量检索
    vec_results = pgvector_search(query_emb, top_k=50)
    # BM25 检索（Postgres 有 pgroonga 或 tsvector）
    bm25_results = fulltext_search(query, top_k=50)
    # RRF 融合
    return rrf_fuse(vec_results, bm25_results)[:top_k]
```

每路 50-100ms → 融合 → Rerank 50-200ms → LLM 1-3s

**总延迟 2-4s**，对实时对话勉强够用。优化方向：
- 缓存：相同 query 复用结果
- 异步：3 步并行
- 流式：第 1 字出来后用户感知「快」

