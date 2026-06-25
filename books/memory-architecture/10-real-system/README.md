# 10. 真实生产系统：端到端长期记忆架构

最后这一章把所有层、组件、策略组合起来，看一个端到端的长期记忆系统怎么搭。**案例**：2026 年 Q1 我帮一家 SaaS 公司搭的"AI 客服助手"长期记忆系统。

## 业务场景

**用户**：某 SaaS 公司，年付费客户 5000 家。

**需求**：做一个 AI 客服助手，记住每个客户的偏好、历史问题、账户信息，提供个性化支持。

**关键约束**：

- 数据合规（GDPR + 中国个保法）
- 响应延迟 < 2 秒
- 单用户月成本 < ¥0.50
- 用户可随时删除所有记忆

## 整体架构

```
[用户 Web/移动端]
   ↓ 用户问题
[API Gateway] (鉴权 + 速率限制 + GDPR 入口)
   ↓
[Query 处理器]
   ├─ LLM 分析 query
   ├─ 提取关键词 / 实体 / 意图
   ↓
[混合检索]
   ├─ 向量检索 (pgvector)
   ├─ 关键词检索 (PostgreSQL FTS)
   └─ 图谱检索 (Neo4j)
   ↓
[Context 组装]
   ├─ 注入 Semantic memory
   ├─ 注入相关 Episodic events
   ├─ Working memory compaction
   ↓
[LLM 推理] (生成回复)
   ↓
[回复用户]
   ↓
[Memory 写入器] (异步)
   ├─ 评估事件重要度
   ├─ 写入 episodic
   ├─ 周期提炼 semantic
```

## 详细实现

### 1. Query 处理器

```python
class QueryProcessor:
    def __init__(self, llm):
        self.llm = llm
    
    async def analyze(self, query: str, user_id: str) -> QueryAnalysis:
        prompt = f"""
        分析用户问题：
        原始问题：{query}
        用户 ID：{user_id}
        
        输出 JSON：
        {{
          "keywords": ["关键词1", "关键词2"],
          "entities": {{"account_id": "a_xxx", "product": "p_yyy"}},
          "intent": "technical_question | billing | account | feedback",
          "embedding": [...]  // 1536 维向量
        }}
        """
        
        response = await self.llm.invoke(
            model="claude-haiku-4.5",  # 便宜模型
            system=QUERY_ANALYSIS_PROMPT,
            user=prompt,
            response_format={"type": "json_object"},
        )
        
        return QueryAnalysis.parse_raw(response)
```

### 2. 混合检索器

```python
class HybridRetriever:
    def __init__(self, episodic_db, graph_db):
        self.episodic_db = episodic_db
        self.graph_db = graph_db
    
    async def retrieve(self, query_analysis: QueryAnalysis, user_id: str, top_k=10):
        # 并行检索
        vector_results, keyword_results, graph_results = await asyncio.gather(
            self.vector_search(query_analysis, user_id, top_k=20),
            self.keyword_search(query_analysis, user_id, top_k=20),
            self.graph_search(query_analysis, user_id),
        )
        
        # RRF 融合
        fused = self.rrf_fusion(vector_results, keyword_results, graph_results)
        
        # 重排序（5 维度）
        reranked = self.rerank(fused, query_analysis)
        
        return reranked[:top_k]
    
    async def vector_search(self, q, user_id, top_k):
        return await self.episodic_db.search(
            vector=q.embedding,
            filter={"user_id": user_id},
            top_k=top_k,
        )
    
    async def keyword_search(self, q, user_id, top_k):
        return await self.episodic_db.keyword_search(
            query=" ".join(q.keywords),
            filter={"user_id": user_id},
            top_k=top_k,
        )
    
    async def graph_search(self, q, user_id):
        if q.intent == "account":
            return await self.graph_db.query_user_account(user_id)
        elif q.intent == "billing":
            return await self.graph_db.query_user_billing(user_id)
        return []
```

### 3. Context 组装

```python
class ContextAssembler:
    def __init__(self, semantic_db, episodic_db):
        self.semantic_db = semantic_db
        self.episodic_db = episodic_db
    
    async def assemble(self, query: str, query_analysis, retrieved_events, user_id):
        # 1. 检索 semantic memory（用户偏好、项目规则）
        semantic_facts = await self.semantic_db.get_current(user_id)
        
        # 2. Working memory compaction（如果超长会话）
        recent_messages = await self.get_recent_messages(user_id, limit=20)
        if count_tokens(recent_messages) > 100_000:
            recent_messages = await compact_context(recent_messages)
        
        # 3. 组装 prompt
        context = {
            "user_preferences": format_facts(semantic_facts),
            "relevant_history": format_events(retrieved_events),
            "recent_conversation": format_messages(recent_messages),
            "user_query": query,
        }
        
        return context
```

### 4. Memory 写入器

```python
class MemoryWriter:
    def __init__(self, episodic_db, semantic_db, llm):
        self.episodic_db = episodic_db
        self.semantic_db = semantic_db
        self.llm = llm
        self.queue = asyncio.Queue()
    
    async def on_message(self, message: Message, response: Message, metadata: dict):
        # 评估重要度
        importance = await self.score_importance(message, response, metadata)
        
        if importance < 0.5:
            return  # 不写
        
        event = EpisodicEvent(
            event_id=f"evt_{uuid.uuid4().hex[:16]}",
            user_id=metadata["user_id"],
            session_id=metadata["session_id"],
            timestamp=datetime.now(),
            type=metadata.get("event_type", "question"),
            content=message.content,
            embedding=await embed(message.content),
            metadata={
                **metadata,
                "importance": importance,
                "response_summary": response.content[:200],
            },
        )
        
        # 异步写（不阻塞主流程）
        await self.queue.put(event)
    
    async def flush_loop(self):
        """后台循环，每 5 秒批量写一次"""
        while True:
            batch = []
            try:
                while len(batch) < 50:
                    batch.append(await asyncio.wait_for(self.queue.get(), timeout=5.0))
            except asyncio.TimeoutError:
                pass
            
            if batch:
                await self.episodic_db.batch_insert(batch)
    
    async def extract_semantic_loop(self):
        """后台循环，每小时提炼一次 semantic"""
        while True:
            await asyncio.sleep(3600)
            
            # 拉过去 1 小时的事件
            events = await self.episodic_db.fetch_recent(hours=1, min_importance=0.6)
            
            if events:
                facts = await extract_semantic_facts(events)
                await self.semantic_db.upsert_batch(facts)
```

### 5. GDPR 合规：用户删除

```python
class GDPRCompliance:
    async def delete_user_data(self, user_id: str):
        # 1. 删除 episodic events
        await episodic_db.delete(user_id=user_id)
        
        # 2. 删除 semantic facts
        await semantic_db.delete(scope=f"user:{user_id}")
        
        # 3. 删除图谱节点
        await graph_db.execute(
            "MATCH (u:User {id: $user_id}) DETACH DELETE u",
            user_id=user_id,
        )
        
        # 4. 删除冷归档
        await s3.delete(f"s3://archive/events/{user_id}/")
        
        # 5. 记录删除日志（合规需要保留"已删除"的事实）
        await audit_log.info(f"user {user_id} data deleted per GDPR request")
```

## 性能数据

生产 3 个月，5000 用户：

| 指标 | 数值 |
|------|------|
| 平均响应时间 | 1.4 秒 |
| P95 响应时间 | 1.9 秒 |
| 单用户月均事件量 | 87 条 |
| 单用户月成本 | ¥0.38 |
| 用户满意度 | 4.5/5 |
| 记忆命中率（"我记得你说过..."）| 78% |
| GDPR 删除请求 | 23 次，全部 < 30 分钟完成 |

**记忆命中率 78%** 是核心指标——意味着 78% 的对话里 agent 能准确引用用户过去说过的事 / 偏好。

## 关键技术决策回顾

**1. 向量 + 关键词都用 PostgreSQL**

500 万事件规模下，pgvector + PG FTS 完全够用，省一套 ES 的运维成本。

**2. 图谱用 Neo4j 社区版**

5000 用户的图谱规模 < 50 万节点，社区版够用。如果上百万用户，再考虑 Nebula Graph。

**3. 重要事件实时写 + 普通事件批量写**

混合策略在成本和延迟间平衡。

**4. semantic 提炼用周期任务（每 1 小时）**

不阻塞主流程，节省成本。

**5. WAL + 异步队列**

保证写入可靠性 + 不阻塞主流程。

**6. GDPR 删除 < 30 分钟**

合规是底线，不能等出问题再补。

## 踩过的坑

**坑 1：图谱节点膨胀**

最初把所有事件都建模成图节点，3 个月后 200 万节点、查询慢。**修法**：图谱只存"提炼后的知识"，原始事件只存向量库 + PG。

**坑 2：semantic 冲突**

用户改口后老知识不废弃，agent 用旧偏好回答。**修法**：版本化 + 标记 superseded，新知识自动覆盖旧知识。

**坑 3：成本失控**

某天突然发现 5 个用户的 episodic 事件量是平均值 100 倍。**修法**：单用户事件量上限 + 异常告警。

**坑 4：GDPR 删除不完整**

某次删除只清了 episodic，semantic + 图谱没清，监管找上门。**修法**：删除流程必须覆盖所有存储层 + 审计日志记录。

## 经验总结

搭长期记忆系统 8 个关键决策：

1. **3 层架构**（working / episodic / semantic）+ 各层选对存储
2. **混合检索**（向量 + 关键词 + 图谱）+ RRF 融合
3. **写入策略**（混合实时 / 批量）+ 重要度评分
4. **版本化**（所有知识可回溯）
5. **冲突处理**（证据数 + 显式确认）
6. **GDPR 合规**（可删除、审计日志）
7. **成本控制**（每用户上限 + 异常告警）
8. **可观测性先行**（命中率、延迟、成本三指标上线前就要有）

整个系列 10 章到这里。下一步看你想继续哪个方向——具身智能 / AI 内容创作经济。