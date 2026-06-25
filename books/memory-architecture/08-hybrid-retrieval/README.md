# 08. 混合检索：向量 + 图谱 + 关键词

单一检索方式都不够——向量检索擅长相似度但不懂关系，关键词检索懂精确但不懂语义，图谱检索懂关系但规模受限。

**生产里的长期记忆系统一定是混合检索**：三种方式组合 + 重排序。

这一章讲实战。

## 三种检索方式回顾

**向量检索**：

```python
results = await vector_db.search(
    vector=query_embedding,
    top_k=20,
)
```

优点：语义理解强、容错好（"违约率" 和 "不良贷款率" 能匹配）。

缺点：不精确（"上海" 可能匹到 "海上"）、不懂关系。

**关键词检索**（BM25 / Elasticsearch）：

```python
results = await elasticsearch.search(
    query={"match": {"content": "上海 违约率"}},
    top_k=20,
)
```

优点：精确匹配、支持复杂 query、速度快。

缺点：不懂语义（同义词漏匹配）、对错别字敏感。

**图谱检索**：

```cypher
MATCH (u:User {id: $user_id})-[:OWNS]->(p:Project)
RETURN p
```

优点：关系推理、跨实体关联。

缺点：图查询语言学习成本、规模受限。

## 混合架构

```
[用户问题]
   ↓
[Query 解析]
   ├─ 提取关键词
   ├─ 提取实体（人 / 项目 / 工具）
   ├─ 识别意图
   ↓
[并行检索]
   ├─ 向量检索（top 20）
   ├─ 关键词检索（top 20）
   └─ 图谱检索（基于提取的实体）
   ↓
[融合 + 重排序]
   ├─ 合并候选
   ├─ 按多维度评分
   └─ 返回 top K
```

## 实战代码骨架

```python
class HybridRetriever:
    def __init__(self, vector_db, keyword_db, graph_db):
        self.vector_db = vector_db
        self.keyword_db = keyword_db
        self.graph_db = graph_db
    
    async def retrieve(self, query: str, user_id: str, top_k: int = 10):
        # Step 1: Query 解析
        query_analysis = await analyze_query(query)
        # {
        #   "keywords": ["上海", "违约率", "Q1"],
        #   "entities": {"user_id": "u_123", "project_id": null},
        #   "intent": "data_query",
        #   "embedding": [...]
        # }
        
        # Step 2: 并行检索
        vector_results, keyword_results, graph_results = await asyncio.gather(
            self.vector_search(query_analysis, user_id, top_k=20),
            self.keyword_search(query_analysis, user_id, top_k=20),
            self.graph_search(query_analysis, user_id),
        )
        
        # Step 3: 融合 + 重排序
        candidates = self.merge_candidates(vector_results, keyword_results, graph_results)
        reranked = self.rerank(candidates, query, query_analysis)
        
        return reranked[:top_k]
    
    async def vector_search(self, q, user_id, top_k):
        return await self.vector_db.search(
            vector=q["embedding"],
            filter={"user_id": user_id},
            top_k=top_k,
        )
    
    async def keyword_search(self, q, user_id, top_k):
        return await self.keyword_db.search(
            query={
                "bool": {
                    "must": [{"match": {"content": " ".join(q["keywords"])}}],
                    "filter": [{"term": {"user_id": user_id}}],
                }
            },
            top_k=top_k,
        )
    
    async def graph_search(self, q, user_id):
        # 基于实体和意图查图
        if q["entities"].get("project_id"):
            # 用户问的是项目相关
            return await self.graph_db.query_project_context(
                user_id, q["entities"]["project_id"]
            )
        elif q["intent"] == "preference":
            # 用户问偏好
            return await self.graph_db.query_user_preferences(user_id)
        return []
```

## 融合策略

**策略 1：RRF（Reciprocal Rank Fusion）**

不同检索方式排序后，按排名倒数求和：

```python
def rrf_fusion(*result_lists, k=60):
    """RRF 融合：score = sum(1 / (k + rank))"""
    scores = defaultdict(float)
    for results in result_lists:
        for rank, item in enumerate(results, 1):
            scores[item.id] += 1 / (k + rank)
    
    reranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [item_id for item_id, score in reranked]
```

简单有效，不需要训练。

**策略 2：加权求和**

给每种检索方式一个权重，按权重融合：

```python
def weighted_fusion(vector_results, keyword_results, graph_results, 
                    w_vec=0.5, w_kw=0.3, w_graph=0.2):
    scores = defaultdict(float)
    
    # 向量结果：score = similarity
    for r in vector_results:
        scores[r.id] += w_vec * r.similarity
    
    # 关键词结果：score = bm25 score（归一化到 0-1）
    for r in keyword_results:
        scores[r.id] += w_kw * normalize(r.bm25_score)
    
    # 图谱结果：score = 1.0（命中即满分）
    for r in graph_results:
        scores[r.id] += w_graph * 1.0
    
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

权重需要根据场景调优。一般默认 `vector=0.5, keyword=0.3, graph=0.2`。

**策略 3：LLM 重排序**

把候选 top 50 用 LLM 重新排序：

```python
async def llm_rerank(query, candidates):
    prompt = f"""
    用户问题：{query}
    
    候选答案：
    {format_candidates(candidates)}
    
    请根据相关性、准确性、时效性，重新排序候选答案。
    输出 top {top_k} 的 ID 列表。
    """
    
    response = await llm.invoke(model="claude-haiku-4.5", prompt=prompt)
    return parse_reranked_ids(response)
```

效果最好但成本最高（每个 query 都要 LLM 调用）。**慎用**，只在前 N 个候选难分胜负时用。

## 实战：用户问题"上次那个项目用的什么数据库"

**Step 1：Query 解析**

```python
query_analysis = {
    "keywords": ["项目", "数据库"],
    "entities": {},  # 没显式提到实体
    "intent": "tech_stack_query",
    "embedding": [...],
}
```

**Step 2：并行检索**

```python
# 向量检索：找类似问题
vector_results = [
    {"id": "evt_001", "content": "Project X 用 PostgreSQL", "score": 0.92},
    {"id": "evt_002", "content": "Project Y 用 MySQL", "score": 0.85},
    {"id": "evt_005", "content": "我做了 Project Z", "score": 0.78},
]

# 关键词检索
keyword_results = [
    {"id": "evt_005", "content": "我做了 Project Z", "score": 0.7},
    {"id": "evt_010", "content": "数据库选型", "score": 0.5},
]

# 图谱检索：用户最近的项目
graph_results = [
    {"id": "p_456", "type": "project", "name": "风控系统", "last_accessed": "2026-06-01"},
]
```

**Step 3：融合 + 重排序**

```python
# RRF 融合
fused = [
    ("p_456", 1 / (60 + 1)),   # 图谱第 1
    ("evt_001", 1 / (60 + 1)), # 向量第 1
    ("evt_005", 1 / (60 + 2) + 1 / (60 + 1)), # 向量第 3 + 关键词第 1
    ("evt_002", 1 / (60 + 2)), # 向量第 2
    ("evt_010", 1 / (60 + 2)), # 关键词第 2
]

# 重排序：图谱命中的 p_456 是用户最近项目，权重提升
# 找 p_456 用什么数据库
context = await graph_db.query_project_tech_stack("p_456")
# context = ["PostgreSQL", "Redis", "ClickHouse"]

return ["PostgreSQL"]  # + 其他相关信息
```

最终答案："PostgreSQL，Project X（风控系统）上次用的数据库。"

## 重排序的 5 个维度

实战里我常用的 5 个评分维度：

**1. 相关性**（40% 权重）—— 检索方式得分（向量相似度 / BM25 / 图谱命中）

**2. 时效性**（25%）—— 越新权重越高

```python
def recency_score(timestamp, now=datetime.now()):
    days_old = (now - timestamp).days
    return 1.0 / (1 + days_old / 30)  # 30 天前衰减到 50%
```

**3. 质量**（15%）—— 历史满意度

```python
def quality_score(metadata):
    satisfaction = metadata.get("user_satisfaction", 3.0)
    return satisfaction / 5.0
```

**4. 实体匹配**（10%）—— 是否匹配 query 中提到的实体

```python
def entity_match_score(event, query_entities):
    matched = 0
    for entity_type, entity_id in query_entities.items():
        if event.metadata.get(entity_type) == entity_id:
            matched += 1
    return matched / max(len(query_entities), 1)
```

**5. 多样性**（10%）—— 避免全是同一类事件

```python
def diversity_penalty(current_results, candidate):
    # 候选和已选结果的相似度越高，惩罚越大
    similarities = [cosine_sim(c.embedding, candidate.embedding) for c in current_results]
    avg_sim = np.mean(similarities) if similarities else 0
    return 1 - avg_sim * 0.5
```

## 实战性能数据

我跟踪过一个 agent 系统的混合检索优化前后：

| 检索方式 | P@10（top 10 准确率） | 延迟 P95 |
|---------|----------------------|---------|
| 仅向量 | 62% | 30ms |
| 仅关键词 | 48% | 15ms |
| 仅图谱 | 35% | 50ms |
| 混合（RRF） | 78% | 80ms |
| 混合（LLM 重排序） | 86% | 1200ms |

**混合检索准确率提升 16 个百分点**（从 62% 到 78%），延迟在 80ms 可接受范围内。LLM 重排序再提升 8 个百分点但延迟跳到 1.2 秒——**生产里默认 RRF，关键场景用 LLM 重排序**。

## 选型推荐

**小项目（< 100 万事件）**：

- 向量：pgvector
- 关键词：PostgreSQL 全文检索（不用 ES）
- 图谱：PostgreSQL JSONB 模拟

**中项目（100 万 - 1 亿事件）**：

- 向量：Qdrant / Pinecone
- 关键词：Elasticsearch
- 图谱：Memgraph / Neo4j 社区版

**大项目（> 1 亿事件）**：

- 向量：Milvus
- 关键词：Elasticsearch
- 图谱：Nebula Graph

下一章讲 Memory 写入策略——什么时候写、写什么、怎么避免存储爆炸。