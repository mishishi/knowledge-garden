# 09. 高级 RAG 模式

> 基础 RAG（embedding + 检索 + LLM）解决 80% 场景。剩下 20% 需要**高级模式**：让 RAG 更智能、更准、更鲁棒。

## 1. Agentic RAG：让 LLM 自己决定怎么检索

**问题**：固定流程（retrieve → generate）不够灵活。复杂问题需要：
- 多步检索
- 不同角度查
- 检索不到时换关键词

**解法**：给 LLM 工具，让它自己调用。

```python
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.tools import Tool

# 工具 1：向量检索
def vector_search(query: str) -> str:
    chunks = rag_search(query, top_k=5)
    return "\n\n".join(c["text"] for c in chunks)

# 工具 2：关键词检索
def keyword_search(query: str) -> str:
    chunks = bm25_search(query, top_k=5)
    return "\n\n".join(c["text"] for c in chunks)

# 工具 3：原始文档读取
def read_full_doc(doc_id: str) -> str:
    return db.get_document(doc_id)

tools = [
    Tool(name="vector_search", func=vector_search,
         description="语义搜索适合找概念相关的内容"),
    Tool(name="keyword_search", func=keyword_search,
         description="关键词搜索适合找 ID / 错误码 / 专有名词"),
    Tool(name="read_doc", func=read_full_doc,
         description="读取完整文档，适合需要全文上下文的场景"),
]

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

result = executor.invoke({
    "input": "对比 2024 Q3 和 Q4 的营收差异，并列出 Q4 的主要增长来源"
})
# Agent 自己会：
# 1. vector_search("2024 Q3 营收")
# 2. vector_search("2024 Q4 营收")
# 3. vector_search("2024 Q4 增长来源")
# 4. 综合回答
```

**代价**：延迟高（多次 LLM 调用）、token 贵（多次工具调用 prompt）。

**适合**：复杂分析问题。简单问答用基础 RAG 即可。

## 2. Multi-hop RAG：链式推理

**问题**：复杂问题需要**多步推理**才能答：

```
Q: 2024 Q3 营收增长的主要客户是谁？

需要：
1. 先找到 2024 Q3 营收
2. 再找到 2024 Q3 主要客户
3. 再找到这些客户贡献的增长
4. 整合回答
```

**解法 A：ReAct 风格**

```python
REACT_PROMPT = """回答用户问题，可以多步检索。

可用工具：
{tools}

格式：
Thought: <思考下一步做什么>
Action: <工具名>
Action Input: <工具输入>
Observation: <工具返回>
... (重复 Thought/Action/Observation)
Thought: 我现在知道答案了
Final Answer: <最终回答>

问题：{question}
{agent_scratchpad}
"""
```

**解法 B：自动 query decomposition**

```python
def decompose_query(question: str) -> list[str]:
    """LLM 把复杂问题拆成子问题"""
    prompt = f"""把下面问题拆成 2-4 个可独立检索的子问题：

原问题：{question}

子问题（每行一个）："""
    return llm.complete(prompt).split("\n")

def multi_hop_rag(question: str) -> str:
    sub_questions = decompose_query(question)
    all_chunks = []
    for sq in sub_questions:
        all_chunks.extend(rag_search(sq, top_k=3))
    # 去重 + rerank + 回答
    unique = dedupe(all_chunks)
    return llm_answer(question, build_context(rerank(question, unique)))
```

## 3. HyDE：假设性文档嵌入

**问题**：用户问「什么是 X」时，问题本身 embedding 通常**不够具体**，检索不准确。

**解法**：让 LLM **先猜一个假设性答案**，再 embed 这个答案去检索：

```python
def hyde_search(question: str, top_k: int = 5) -> list[dict]:
    # 1. LLM 生成假设性答案（不用真事实，模拟答案的样子）
    hypothetical = llm.complete(
        f"用 2-3 句话回答这个问题（可以编）：{question}"
    )

    # 2. embed 假设性答案
    hyp_emb = emb_model.encode(hypothetical).tolist()

    # 3. 用假设性答案的 embedding 检索（比直接 embed 问题更准）
    return qdrant.search(query_vector=hyp_emb, limit=top_k)
```

**为什么有效**：问题的向量和文档的向量**语义空间不对齐**——一个是「问题」，一个是「陈述」。HyDE 用「模拟答案」对齐两个空间。

**实测**：Recall@5 提升 **10-20%**（特别是问句很短时）。

**代价**：每次检索多 1 次 LLM 调用。

## 4. GraphRAG：知识图谱 + 向量

**问题**：很多场景需要**实体关系**推理：

```
Q: 张三的上级的下属是谁？

纯向量检索能找到「张三」「张三的上级」「下属」相关文档
但**推理关系**需要知识图谱
```

**解法**：建一个**实体关系图**，检索时结合向量和图遍历。

```python
# 1. 从文档提取实体和关系（LLM）
def extract_graph(text: str) -> list[tuple[str, str, str]]:
    """返回 [(entity1, relation, entity2), ...]"""
    prompt = f"""从下面文本提取实体和关系：

{text}

格式（每行）：entity1 | relation | entity2"""
    return parse_tuples(llm.complete(prompt))

# 2. 入图数据库
graph.add_edges_from(extract_graph(doc.text))

# 3. 查询：先向量找相关文档 → 再图遍历扩展
def graph_rag(question: str):
    relevant_docs = vector_search(question, top_k=5)
    entities = extract_entities(question)
    related = [graph.neighbors(e, depth=2) for e in entities]
    return combine(relevant_docs, related)
```

**工具**：[LlamaIndex GraphRAG](https://github.com/run-llama/llama_index)、[Neo4j](https://neo4j.com/)、[Memgraph](https://memgraph.com/)

**适合**：企业内部知识（员工关系、产品线、技术栈依赖）。

## 5. Self-RAG：让 LLM 反思自己的检索

**问题**：LLM 拿到检索结果就生成，但**结果可能不相关**——LLM 应该能拒绝。

```python
def self_rag(question: str) -> str:
    chunks = rag_search(question, top_k=5)

    # LLM 评估每个 chunk 是否真的相关
    relevant = []
    for chunk in chunks:
        verdict = llm.complete(f"""这段文档对回答问题有用吗？只回答 YES / NO：
问题：{question}
文档：{chunk['text']}""")
        if "YES" in verdict:
            relevant.append(chunk)

    if not relevant:
        return "未找到相关资料"

    # LLM 评估自己生成的内容是否基于 chunks
    draft = llm.complete(build_prompt(question, relevant))
    critique = llm.complete(f"""这段回答是否完全基于参考资料，没有添加外部信息？

参考资料：{relevant}
回答：{draft}

如果是，回「ANSWER: <原答案>」
如果不是，回「REVISE: <基于资料重写>」""")

    if critique.startswith("REVISE:"):
        return critique.replace("REVISE:", "").strip()
    return draft
```

**效果**：幻觉率降低 **30-50%**。

**代价**：每次问答多 2 次 LLM 调用。

## 6. 分层 RAG：小文档 → 大文档 → 全文档

**问题**：用户问「具体某段的细节」时，**全局检索召回率低**（细节淹没在长文档里）。

**解法**：3 层结构：

```
第 1 层：chunk（200 token，精确检索）
第 2 层：section（2000 token，提供上下文）
第 3 层：document（全文，给 LLM 完整背景）
```

```python
def hierarchical_rag(question):
    # 1. 检索 chunk 层
    chunks = vector_search(question, top_k=10)

    # 2. 升级到 section 层（section 包含多个 chunk）
    sections = []
    for chunk in chunks:
        sections.extend(get_section(chunk.metadata["section_id"]))
    sections = dedupe(sections)

    # 3. 升级到 document 层（只对最相关的 2 个 section）
    docs = [get_doc(s.metadata["doc_id"]) for s in sections[:2]]

    return build_context(chunks + sections + docs)
```

## 7. Cache 缓存

**RAG 大量重复查询**——同一问题 100 个用户问 100 次。

```python
import hashlib
from functools import lru_cache

def cached_rag(question: str, ttl_seconds: int = 3600):
    # 用 question hash 做 cache key
    key = hashlib.md5(question.encode()).hexdigest()

    # Redis / 内存 cache
    cached = cache.get(key)
    if cached and (now() - cached.timestamp) < ttl_seconds:
        return cached.answer

    # 真去检索
    answer = real_rag(question)
    cache.set(key, answer)
    return answer
```

**命中率**：30-60%（企业内部 RAG 经常有重复问题）。

**省下**：60% 的检索 + LLM 成本。

## 什么时候上高级模式

**别过早优化**：

```
基础 RAG 上线 → 看用户吐槽 → 哪个场景特别差 → 上对应模式
```

- 用户问「复杂推理」问题多 → Multi-hop
- 用户问「代码 / 错误」多 → 自托管 rerank
- 用户问「关系 / 实体」多 → GraphRAG
- 用户问题都很短、检索不到 → HyDE
- 幻觉多 → Self-RAG

**先优化基础 RAG，再上高级模式**。否则技术债越堆越深。

