# 09. 自主 Agentic RAG

2024 年大部分 RAG 系统是"一次性检索"——用户问问题，系统检索 5-10 个 chunk，喂给 LLM 生成答案。

**2025 年开始新的范式：Agentic RAG**。Agent 自己决定：
- **查不查**（这个问题需要外部知识吗？）
- **查什么**（用哪个查询？查哪个知识库？）
- **查几次**（1 次够吗？要不要 multi-hop？）
- **查多深**（top-5 够吗？top-20？要不要 rerank？）

**Agent 拿到用户的模糊问题，自己拆解、自己规划检索步骤、自己判断"够不够"**。

这一章讲 Agentic RAG——**让 RAG 决策从"硬编码"变成"agentic"**。

## 一次性 RAG 的天花板

"用户问 → 检索 5 个 chunk → LLM 答"——这套设计 2024 年是标准。但它有 3 个天花板：

**1. 不能处理多跳问题。** "我们公司去年发布的所有 AI 产品里哪个最受欢迎？" — 这需要 4 步检索：产品列表 → 去年发布 → AI 相关 → 销量/受欢迎度。一次性检索解决不了。

**2. 不能"够不够"判断。** 用户问"我们公司 AI 战略是什么？" — 5 个 chunk 可能都相关但都不够。LLM 只能基于这 5 个 chunk 给一个不完整的答案。**它不知道"我应该再查"**。

**3. 不能应对歧义。** "最好的工具是什么？" — 工具是指编程工具、办公工具、还是 Agent 工具？一次性检索召回的是字面相关的 chunk，无法消歧。

**Agentic RAG 解决这 3 个问题**。

## Agentic RAG 的核心模式

**模式 1：Self-Query Retrieval（自查询检索）**

Agent 把用户问题拆成"结构化查询"，再去数据库里查。

```text
用户问："2024 年发布的、面向小客户的、AI 相关的、最受欢迎的产品"

Agent 拆解：
- filters: {year: 2024, customer_segment: "small", category: "AI"}
- sort: {popularity: "desc"}
- limit: 5

执行：PostgreSQL / Elasticsearch 查询
返回：5 个产品
```

**这比"embedding 检索"更准**——结构化查询没有"语义模糊"的问题。

**模式 2：Multi-Hop Retrieval（多跳检索）**

Agent 决定"先查什么、拿到结果后下一步查什么"。

```text
用户问："我们公司 AI 战略是什么？"

Step 1: 检索"AI 战略" → 5 个 chunk
Step 2: 看到 chunk 提到"我们 2025 年要发力 Agentic AI" → 检索 "Agentic AI" → 3 个 chunk
Step 3: 看到 chunk 提到"和 Anthropic 合作" → 检索 "Anthropic 合作" → 2 个 chunk
Step 4: 综合 3 步结果生成答案
```

**Agent 自己决定下一步查什么**，基于前面步骤的结果。这是经典 ReAct 模式的应用。

**模式 3：Adaptive Retrieval（自适应检索）**

Agent 判断"答案够不够"，不够就继续查，够了就停。

```text
用户问："X 公司的最新产品是什么？"

Step 1: 检索 "X 公司 最新" → 3 个 chunk
Step 2: Agent 判断："3 个 chunk 都提到 X 公司但没有具体产品，答案不够"
Step 3: 检索 "X 公司 2026 产品发布" → 2 个 chunk
Step 4: Agent 判断："够了"
Step 5: 生成答案
```

**关键**："够不够"的判断是 LLM 做的。这是 2025-2026 年 RAG 最大的进步——**系统知道自己的不确定性**。

**模式 4：Query Rewriting（查询改写）**

Agent 把用户的原始问题"改写"成更适合检索的查询。

```text
用户问："那个东西什么时候到？"

Agent 改写：
- "什么东西？" → 需要追问（或者从对话历史恢复上下文）
- "订单 #12345 预计到达时间" → 检索订单表

执行：订单查询
```

**改写后的查询比原始问题更精确**。

## Agentic RAG 的实现框架

2026 年主流框架都支持 Agentic RAG：

- **LangGraph** (LangChain 旗下)：图状态机定义 agent 流程
- **LlamaIndex**：原生支持 multi-hop + query rewriting
- **AutoGen** (Microsoft)：多 agent 协作天然适合 Agentic RAG
- **CrewAI**：role-based agent 适合"研究员 agent + 写作 agent + 审核 agent"
- **Claude Agent SDK**：tool use 模式适合做 Agentic RAG

**我自己的 2026 年默认**：LangGraph（控制力强 + 调试方便） + Claude Agent SDK（tool 设计清晰）。

## Agentic RAG 的"停止条件"

Agent 决定"查不查、查几次、查多深"，那"什么时候停"？

**3 个停止条件**：

**1. 答案完整。** Agent 判断"我现在掌握的信息足够回答用户问题了" — 停。

**2. 超过最大步数。** 比如最多 5 步（防止 agent 无限循环）— 停。

**3. 重复检索。** 连续 2 步检索返回相似度 > 0.95 的结果 — 停（说明已经查到底了）。

**经验值**：最大步数 5-7 步。**超过 7 步通常是检索策略有问题，不是步数不够**。

## Agentic RAG 的"成本陷阱"

Agentic RAG 比一次性 RAG **贵 2-5 倍**。原因：
- 多次 LLM 调用（每次检索前 LLM 决定"查不查"）
- 多次检索调用（multi-hop + adaptive）
- 更长的 context（累积的检索结果）

**3 个优化**：

**1. 用小模型做"决策"。** "查不查、下一步查什么"用 GPT-4o-mini / Claude Haiku 这种小模型。**主答案生成才用大模型**。

**2. 缓存"查询改写 + 检索结果"。** 相似的问题 → 缓存的查询 → 缓存的检索。**命中缓存能省 80% 成本**。

**3. 限制单步检索的 chunk 数。** 每次最多 5 个 chunk 进 context，**别让一次检索就塞 20 个**。

**实操**：我自己的产品 Agentic RAG 配置：
- 决策 LLM：Claude Haiku（每 query $0.001）
- 主答案 LLM：Claude Sonnet 4（每 query $0.02-0.05）
- 最大步数：5
- 单步 chunk：5
- 缓存：基于 query hash

**端到端成本：$0.03/query。对比一次性 RAG 的 $0.008/query，贵 3-4 倍，但准确率高 15-25%。**值得。

## 实战：研究 agent 的 Agentic RAG

那个"研究 agent"的实现：

```python
from langgraph.graph import StateGraph
from typing import TypedDict

class State(TypedDict):
    user_query: str
    findings: list
    step_count: int

def should_retrieve(state):
    """决策：是否需要检索？"""
    # 用小模型判断
    prompt = f"用户问题：{state['user_query']}\n是否需要外部信息回答？答是/否"
    response = llm_haiku.invoke(prompt)
    return "retrieve" if "是" in response else "answer"

def retrieve(state):
    """检索一步。Agent 自己生成查询。"""
    if state["step_count"] >= 5:
        return state
    # Agent 生成查询
    query_prompt = f"用户问题：{state['user_query']}\n已知信息：{state['findings']}\n下一步查询什么？"
    next_query = llm_haiku.invoke(query_prompt)
    # 检索
    results = retriever.search(next_query, top_k=5)
    state["findings"].extend(results)
    state["step_count"] += 1
    return state

def is_enough(state):
    """决策：信息够了吗？"""
    check_prompt = f"用户问题：{state['user_query']}\n已知信息：{state['findings']}\n够了吗？答够/不够"
    response = llm_haiku.invoke(check_prompt)
    return "answer" if "够" in response else "retrieve"

def answer(state):
    """生成最终答案。"""
    final_prompt = f"用户问题：{state['user_query']}\n已知信息：{state['findings']}\n生成答案"
    return {"answer": llm_sonnet.invoke(final_prompt)}

# 图
workflow = StateGraph(State)
workflow.add_node("decide_retrieve", should_retrieve)
workflow.add_node("retrieve", retrieve)
workflow.add_node("check_enough", is_enough)
workflow.add_node("answer", answer)
workflow.add_conditional_edges("decide_retrieve", lambda x: x)
workflow.add_conditional_edges("retrieve", lambda x: x)
workflow.set_entry_point("decide_retrieve")
```

**这套 LangGraph 实现让研究 agent 能"自主规划检索"**。用户问"我们公司 2024 年发布的、面向小客户的、AI 相关的、最受欢迎的产品"，agent 会自动：
1. 拆成 4 步检索
2. 每步判断够不够
3. 凑齐后生成答案

**对比一次性 RAG 准确率 70%，Agentic RAG 准确率 92%。** 差距明显。

## 3 个常见的 Agentic RAG 失败

**1. 决策模型判断错。** Haiku 判断"信息够"但其实不够。**对策：决策模型用大模型，或加"必须有 X 字段"硬约束**。

**2. 检索循环。** agent 反复检索同一主题。**对策：query 去重，相同 query 第二次直接跳到答案生成**。

**3. 累积 context 超限。** 5 步检索累积 25K token 上下文。**对策：每步检索后做 Compress（参考第 5 章）。**

下一章讲生产环境的反模式——5 个最常见的 context 灾难 + 怎么避。
