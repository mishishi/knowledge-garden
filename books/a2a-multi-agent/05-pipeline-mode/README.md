# 05. 管道模式（Pipeline）实战

管道是 4 种 A2A 协作范式里最简单的，但"简单"不等于"容易"。2025 年我们用 LangChain 搭过一个研究综述 pipeline，上线第一个月就出了 3 次生产事故，全是管道特有的坑。

这一章讲透管道范式的设计、实现、踩坑、debug。

## 典型 pipeline 结构

```
[Input Agent]
    ↓ 标准化输入
[Processing Agent 1]
    ↓ 中间结果
[Processing Agent 2]
    ↓ 中间结果
[Processing Agent 3]
    ↓ 最终结果
[Output Agent]
    ↓ 格式化输出
[用户]
```

每两个 agent 之间有个**数据 contract**（schema），上游的输出必须严格匹配下游的输入。

## 真实案例：研究综述 pipeline

**场景**：用户输入"总结 2026 年 RAG 领域的最新进展"。

**Pipeline**：

```
[Query Parser Agent]
   - 输入：自然语言问题
   - 输出：标准化查询 { topic, timeRange, language, maxResults }
   - 实现：Claude Opus 4.7 + JSON mode

[Search Agent]
   - 输入：标准化查询
   - 输出：候选论文列表 [{ title, abstract, url, citations }]
   - 实现：调用 arxiv MCP + semantic scholar MCP

[Filter Agent]
   - 输入：候选论文列表
   - 输出：筛选后的论文列表（top 20）
   - 实现：基于 LLM 排序 + 引用数过滤

[Summarize Agent]
   - 输入：20 篇论文
   - 输出：每篇 200 字摘要列表
   - 实现：长 context 模型 + chunking

[Synthesize Agent]
   - 输入：20 个摘要
   - 输出：综述（3000-5000 字）
   - 实现：长 context 模型 + 结构化 prompt

[Format Agent]
   - 输入：综述文本
   - 输出：HTML / Markdown
   - 实现：模板渲染
```

**总耗时**：单跑一次 35-60 秒。**总成本**：约 $0.50-1.00（取决于输入长度）。

## 数据 contract 怎么设计

Pipeline 最容易翻车的地方是**两个 agent 之间的 schema 不匹配**。

反例：

```python
# Search Agent 输出
{"results": [{"title": ..., "url": ..., "abstract": ...}]}

# Filter Agent 期望输入
{"papers": [...]}
```

名字不一致，运行时直接 422 报错。

**正确做法**：用 Pydantic / Zod / TypeScript interface 严格定义 schema，每个 agent 之间做 schema 校验：

```python
from pydantic import BaseModel

class Paper(BaseModel):
    title: str
    abstract: str
    url: str
    citations: int = 0

class SearchOutput(BaseModel):
    results: list[Paper]

class FilterInput(BaseModel):
    papers: list[Paper]  # 注意命名一致性
```

Pydantic 在 runtime 自动校验，上游输出不符合 schema 立即报错。

## 三个常见踩坑

**坑 1：上游失败下游崩**

Search Agent 调用 arxiv MCP 超时（30 秒无响应），整个 pipeline 崩。

**修法**：每个 agent 包一层 try/catch + retry + 超时降级。Search 失败时返回空列表而不是抛异常，下游 Filter Agent 检测到空列表后返回 "未找到相关论文" 而不是继续处理。

**坑 2：上游慢下游等**

Synthesize Agent 需要 30 秒生成综述，但 Summarize Agent 单篇就要 8 秒，20 篇串行 160 秒。

**修法**：Summarize Agent 内部用 `Promise.all` / `asyncio.gather` 并行处理 20 篇（API 限流允许的情况下）。或者用 batch API。

**坑 3：上下文丢失**

Synthesize Agent 拿到 20 个摘要，但不知道这些论文的原始标题、引用数、URL。生成综述时只能引用摘要内容，没法加"参见论文 X"的链接。

**修法**：每个 agent 之间的数据 contract **尽量保留原始字段**，不要只传摘要不传原文链接。让 Synthesize Agent 自己决定要不要用。

## 可观测性

Pipeline 的可观测性是关键。必须能回答：

- 哪一步最慢？
- 哪一步最贵（token / 钱）？
- 哪一步失败率最高？
- 用户的输入最终产生了什么输出？

**实现**：每个 agent 入口和出口打日志（traceId / agentName / inputSize / outputSize / duration / tokenCount / cost）。用 LangSmith / Langfuse / Arize Phoenix 之类的工具聚合。

```python
@observe(name="summarize-agent")
async def summarize(paper: Paper) -> Summary:
    with tracer.start_span("summarize") as span:
        span.set_attribute("paper.title", paper.title)
        result = await llm.invoke(prompt)
        span.set_attribute("output.tokens", result.usage.total_tokens)
        return result
```

## 重跑机制

Pipeline 必须支持**部分重跑**。如果 Synthesize Agent 失败（API 限流），用户不应该等 35 秒重跑整个 pipeline。

**实现**：每个 agent 的输出**持久化**（DB / Redis / 文件），失败时从最后一个成功的 agent 继续跑。

```python
async def run_pipeline(input):
    state = load_state(input.id) or initial_state(input)
    
    if state.stage < "search":
        state.search = await search_agent(state.query)
        save_state(state)
    
    if state.stage < "filter":
        state.filtered = await filter_agent(state.search)
        save_state(state)
    
    # ... 逐个 stage 跑
    
    return state.final
```

## Pipeline 适合 / 不适合

**适合**：线性任务、可以明确拆分阶段的任务、容错要求高（中间任意一步失败可重跑）的任务。

**不适合**：需要多轮迭代的任务（错误修正需要回到上上游）、需要并行探索的任务、需要决策树的任务（pipeline 是单向的）。

下一章讲 Debate 范式——Pipeline 之外的另一条路。