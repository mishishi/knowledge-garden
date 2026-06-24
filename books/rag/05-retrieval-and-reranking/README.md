# 05. 检索与 Reranking

> 向量检索拿 Top-50 候选不难，但**真正能用的 Top-5 才是功夫**。Reranking 是这一关的关键。

## 检索流水线

```
用户问题
  ↓
Embedding（问题 → 向量）
  ↓
向量检索 Top-50 候选（粗排，快但粗糙）
  ↓
Reranking（精排，慢但准确）
  ↓
Top-5 喂给 LLM
```

**为什么需要粗排 + 精排？**
- 粗排：向量检索很快，但只是「相似度」，不一定是「相关度」
- 精排：Cross-encoder 模型逐一评 (query, doc) 对的相关性，准但慢

类比：粗排是「筛选简历」，精排是「面试」。

## 粗排：向量检索

上一章讲过，Top-K 召回：

```python
# Qdrant
results = qdrant.search(
    collection_name="docs",
    query_vector=query_emb,
    limit=50,  # Top-50 候选
)
```

Top-50 是经验值：**太小 → 漏召回**；**太大 → Rerank 慢**。

## 精排：Cross-encoder Reranking

Cross-encoder 把 query 和 doc **一起输入**模型，输出相关性分数：

```python
from sentence_transformers import CrossEncoder

model = CrossEncoder("BAAI/bge-reranker-large")

# 对 50 个候选逐一打分
pairs = [[query_text, hit.payload["text"]] for hit in results]
scores = model.predict(pairs)  # 50 个分数

# 按分数排序取 Top-5
ranked = sorted(zip(results, scores), key=lambda x: -x[1])
top5 = ranked[:5]
```

## 主流 Reranker 对比

| 模型 | 速度 | 质量 | 显存 | 中文 |
|---|---|---|---|---|
| bge-reranker-large | 中 | 高 | 4 GB | ✅ 强 |
| bge-reranker-base | 快 | 中 | 2 GB | ✅ |
| cohere-rerank-v3 | 云 API | 最高 | 0 | ✅ |
| jina-rerank | 云 API | 高 | 0 | 中等 |

**中文首选 bge-reranker-large**（开源、自托管、中文好）。

## 完整 Pipeline

```python
from sentence_transformers import SentenceTransformer, CrossEncoder
from qdrant_client import QdrantClient

emb_model = SentenceTransformer("BAAI/bge-m3")
rerank_model = CrossEncoder("BAAI/bge-reranker-large")
qdrant = QdrantClient("http://localhost:6333")

def rag_search(query: str, top_k_final: int = 5, top_k_initial: int = 50) -> list[dict]:
    # 1. Embedding
    query_emb = emb_model.encode(query).tolist()

    # 2. 粗排：向量检索
    candidates = qdrant.search(
        collection_name="docs",
        query_vector=query_emb,
        limit=top_k_initial,
    )

    if not candidates:
        return []

    # 3. 精排：Cross-encoder rerank
    pairs = [[query, hit.payload["text"]] for hit in candidates]
    scores = rerank_model.predict(pairs)

    # 4. 按 rerank 分数排序
    ranked = sorted(
        zip(candidates, scores),
        key=lambda x: -x[1]
    )

    # 5. Top-K
    return [
        {
            "text": hit.payload["text"],
            "score": float(score),
            "metadata": hit.payload,
        }
        for hit, score in ranked[:top_k_final]
    ]

# 使用
results = rag_search("2024 Q3 营收是多少？")
for r in results:
    print(f"[{r['score']:.3f}] {r['text'][:100]}...")
```

## 关键陷阱

### 1. Rerank 顺序很重要

❌ 错误：直接用向量相似度排
```python
results = qdrant.search(..., limit=5)  # 跳过 rerank
```

✅ 正确：Top-50 → Rerank → Top-5

### 2. 候选要带 metadata

```python
# ❌ 只返回 text，丢了出处
return [hit.payload["text"] for hit in candidates]

# ✅ 保留 metadata（用于引用、回溯）
return [{"text": ..., "metadata": ..., "score": ...}]
```

LLM 回答里加「来源：xxx.pdf p.5」是 RAG 的关键 UX。

### 3. Reranker 也有局限

Cross-encoder **对 query 措辞很敏感**。同样问题换种问法，分数能差 0.3。

**解决**：先让 LLM 把用户问题改写成 3 种问法，**每种都检索后合并候选**，再 rerank：

```python
def expand_query(query: str) -> list[str]:
    prompt = f"""把下面的用户问题改写成 3 种不同的问法，保持原意：
原问题：{query}

改写：
1.
2.
3.
"""
    response = llm.complete(prompt)
    return [query] + parse_list(response)  # 共 4 个 query

def rag_search_multi(query):
    all_candidates = []
    for q in expand_query(query):
        all_candidates.extend(vector_search(q, top_k=20))
    # 去重 + rerank
    unique = dedupe_by_doc_id(all_candidates)
    return rerank(query, unique)[:5]
```

召回率能提升 **15-30%**，代价是多 3 倍 embedding 调用。

### 4. MMR 多样性

Top-5 全是相似内容（重复）= 浪费 token。用 **MMR（Maximal Marginal Relevance）**：

```python
def mmr_select(query_emb, candidates, top_k=5, lambda_param=0.5):
    selected = []
    remaining = list(candidates)
    while len(selected) < top_k and remaining:
        if not selected:
            # 第一选：最相似
            best = max(remaining, key=lambda c: c.score)
        else:
            # 后续：相关度 + 多样性
            def mmr_score(c):
                relevance = c.score
                diversity = min(
                    cosine_sim(c.embedding, s.embedding)
                    for s in selected
                )
                return lambda_param * relevance - (1 - lambda_param) * diversity
            best = max(remaining, key=mmr_score)
        selected.append(best)
        remaining.remove(best)
    return selected
```

`lambda_param` 越大越相关，越小越多样。**0.5 是常用起点**。

## 何时不用 Rerank

- **候选极少**（< 10）——rerank 收益不大
- **延迟极敏感**（< 100ms）——rerank 加 50-200ms
- **钱极敏感**——rerank 模型推理贵

否则**默认加 rerank**。

## 下篇

[06. Prompt 设计](../06-prompt-design/) — 把 Top-5 喂给 LLM 的 prompt 怎么写，决定最终答案质量。
