# 04. Context 管理：Context Window 爆了怎么办

> 第 1 章我写过"context 爆了"——第 12 轮 agent 失忆。这章专门拆 context 管理：4 种 compact 策略、prompt cache 怎么用、tool result 怎么 trim、长文档怎么处理。

## Context Window 是物理限制，不是建议

Claude 200k、GPT-4 Turbo 128k、Gemini 1.5 Pro 2M——看着都很大，但实际工程里很容易爆。

我自己测过：一个 50 步 multi-agent 任务，平均每轮 messages 涨 8000-15000 tokens（包括 tool 输出、LLM 思考、sub-agent 返回）。50 步就到 50 万 tokens——超过任何模型的 context window。

更阴险的是 **"Lost in the Middle" 现象**——Stanford / Samaya AI 2023 的论文证明 LLM 在长 context 中段注意力明显衰减。200k context 的模型，实际有效注意力的"甜区"是头 20k 和尾 20k。中间 160k 的内容基本被"扫过但没真看"。

所以 context 管理不是"塞进去就好"——是有策略地选择塞什么、放哪里。

## 我的 4 种 compact 策略

不同任务适合不同策略。我维护的工具箱里 4 种都备着：

**Head + Tail（保留头尾）**

```python
def compact_head_tail(messages, max_messages=60):
    if len(messages) <= max_messages:
        return messages
    # 保留 system + 前 4 轮 + 后 30 轮
    return messages[:4] + [summary_message(messages[4:-30])] + messages[-30:]
```

适合：用户持续追问同一主题（"继续"、"然后呢"、"上次你说..."）。保留头 4 轮（任务设定）+ 尾 30 轮（最近交互）。

翻车：中间被砍的对话里如果有"用户给出关键约束"（"记住，我要的是 X 不是 Y"），LLM 会忘。修：system prompt 里把"用户关键约束"提出来，单独维护一个 `user_constraints` 字段，compact 时把 constraints 拼到 system 里。

**Semantic Summary（语义总结）**

```python
def compact_semantic(messages, target_tokens=20_000):
    summary = llm_call(
        model="claude-haiku-3-5",
        system="Summarize this conversation, preserving: 1) user goals 2) decisions made 3) tools used 4) errors encountered. Be concise.",
        messages=messages,
        max_tokens=2000,
    )
    return [
        messages[0],  # system
        {"role": "user", "content": f"[对话历史摘要]\n{summary}"},
        *messages[-10:],  # 保留最近 10 轮原文
    ]
```

适合：长对话、内容密度高、需要保留决策脉络。

翻车：Haiku 总结 100k tokens 要 30 秒 + 烧 $0.05——频繁 compact 反而更贵。修：只在 context > 80% window 时才触发 compact，不是每 N 轮都触发。

**Tool Result Trimming（只 trim tool 输出）**

```python
def trim_tool_results(messages, max_chars=2000):
    for msg in messages:
        if msg["role"] == "user":
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    content = block["content"]
                    if len(content) > max_chars:
                        block["content"] = content[:max_chars] + f"\n\n[truncated, original was {len(content)} chars]"
    return messages
```

适合：tool 输出特别长的场景（`grep -r` 返回几千行、`read_file` 大文件、`search_web` 整页 HTML）。

这招最简单也最有效。我跑的一个代码搜索 agent，光这招就把 context 从 180k 降到 65k，LLM 完成率还更高（因为 LLM 没被噪声淹没）。

**Selective Drop（按重要性丢）**

```python
def selective_drop(messages):
    # 优先级: system > user > assistant > tool_result
    # 砍 tool_result 时按时间倒序砍最旧的
    tool_results = [m for m in messages if is_tool_result(m)]
    if len(tool_results) > 20:
        # 只保留最近 10 个 + 标记为 important 的
        kept = tool_results[-10:] + [t for t in tool_results[:-10] if t.get("important")]
        return rebuild(messages, kept)
    return messages
```

适合：tool 数量多但少数是关键决策（"读 config 文件"、"找关键 API"），其余是次要 tool（"看 log"、"查 typo"）。

我的判断标准：tool result 后面跟 LLM 重要决策（修改代码、发消息、调外部 API）→ important；只是查询类（grep / list）→ not important。

## Prompt Cache 实战

Anthropic 2024-08 推了 Prompt Caching——cache system prompt + 大段不变内容，cache 命中时输入成本降 90%、延迟降 85%。

实战配置：

```python
response = client.messages.create(
    model="claude-sonnet-4",
    system=[
        {
            "type": "text",
            "text": "你是个人助手...",  # 不变部分
            "cache_control": {"type": "ephemeral"}  # 标记 cache
        }
    ],
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "[项目背景]", "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": user_msg}  # 真正变化的部分
            ]
        }
    ],
    tools=TOOLS,
)
```

cache 命中的 3 个条件：
1. system 前缀完全一样（不能多空格少标点）
2. 至少 1024 tokens（不够 cache 反而更慢）
3. 5 分钟内（Anthropic 默认 TTL），要更长可以选 1 小时 cache

我自己跑的项目背景 ~3000 tokens + tool schema ~2000 tokens + system ~500 tokens = cache 5500 tokens。命中后输入从 $3/M 降到 $0.30/M，省 90%。

**关键坑**：cache 标记位置要在**真正不变的内容上**。如果误把"包含当前时间"的内容标记 cache，会 5 分钟才更新——LLM 用旧时间做决策。

我用 `cache_control` 标 system prompt + 项目文档，**不标**包含 user-specific 或 time-sensitive 内容的部分。

## 长文档处理：不要塞进 context

很多人写 agent 时第一个想法是"把整个文档塞进 prompt"。对 1 万字的小文档可以，对 100 万字的知识库就完全不行。

正确做法是 **chunked retrieval + map-reduce**：

```python
def answer_question_with_long_doc(question, doc_path, chunk_size=2000):
    # 1. 分块
    chunks = chunk_document(doc_path, chunk_size=chunk_size)
    
    # 2. Map: 对每个 chunk 单独问 LLM
    chunk_answers = []
    for chunk in chunks:
        ans = llm_call(
            model="claude-haiku-3-5",
            system=f"Answer the question using ONLY this chunk. If not relevant, say 'not relevant'.",
            messages=[{"role": "user", "content": f"Question: {question}\n\nChunk: {chunk}"}],
            max_tokens=300,
        )
        chunk_answers.append(ans)
    
    # 3. Reduce: 聚合所有 chunk answer 让 LLM 综合
    final = llm_call(
        model="claude-sonnet-4",
        system="Synthesize chunk answers into one comprehensive answer. Cite which chunks you used.",
        messages=[{"role": "user", "content": f"Question: {question}\n\nChunk answers:\n" + "\n".join(chunk_answers)}],
        max_tokens=2000,
    )
    return final
```

成本对比（10 万字文档）：
- 一次塞进 context：~30 万 input tokens × $3/M = **$0.90**
- Chunked map-reduce：~5000 tokens × $0.80/M (Haiku) × 50 chunks + ~3000 tokens × $3/M (Sonnet) = **$0.21**

省 77% 成本。Latency 也更好——可以并行跑 50 个 Haiku calls，最后串一次 Sonnet。

但 map-reduce 有个根本限制：**它假设答案能从多个 chunk 局部推出来**。如果问题需要"看完整文档才能答"（"这个项目最大风险是什么"），map-reduce 会漏掉整体视角。修：保留 system prompt 里的"high-level summary"（预先 LLM 总结的 200 字概要），map-reduce 时让每个 chunk 都看到这个 summary 做上下文锚定。

## Context Window 监控

我在 harness 里加了 context window monitor——每轮 LLM call 前检查 messages 占多少 tokens，超阈值就提前 compact：

```python
def maybe_compact(messages, model="claude-sonnet-4"):
    limits = {"claude-sonnet-4": 180_000, "claude-opus-4": 180_000}
    current = count_tokens(messages, model=model)
    threshold = limits.get(model, 100_000) * 0.75  # 75% 触发
    
    if current > threshold:
        logger.warning(f"Context {current}/{limits[model]} tokens, compacting")
        return compact_semantic(messages)
    return messages
```

阈值设 75%——给后续 LLM call 留 buffer（每轮还要加新内容）。低于 75% 不触发，避免过早 compact 损失上下文。

监控日志输出让我能诊断"哪些任务容易 context 爆"——通常是工具输出太大的任务（grep / read 大文件）和多步 deep research。

## Lost in the Middle 的工程对策

Stanford 论文证明：LLM 在 context 中段注意力弱。我的实际测试也复现了——把关键约束放在 messages 第 30 个（中间位置），LLM 经常忽略；放在第 1 个或最后一个，LLM 100% 遵守。

对策：

- **关键约束放头或尾**——system prompt（开头）+ user message（结尾）放重要信息
- **重复关键约束**——重要的约束在 system 写一次，在每 N 轮 user message 开头再贴一次"提醒"
- **不要依赖中段内容**——如果一段说明必须在 LLM 决策时被看到，把它复制到 tool result 末尾或 user message 末尾

我自己的代码 review 里有一条 hard rule：所有"用户明确禁止 / 必须做的约束"必须在 system prompt 出现一次，且在每轮 user message 开头再次出现。看似冗余，实际让遵守率从 70% 提到 96%。

## 这章踩过的关键坑

**Haiku 做 compact 太频繁**——每次 context 超阈值就调 Haiku 总结，结果总结本身花的时间和 token 比直接用原 context 还贵。修：只在 context > 80% window 时触发。

**Cache 标错位置**——把"当前时间"、"用户最新输入"标 cache_control，导致 LLM 用 5 分钟前的旧时间。修：cache 只标确定不变的内容（system、项目文档、tool schema）。

**Map-reduce 假设过强**——以为 map-reduce 能处理"需要整体视角"的问题，结果漏掉跨 chunk 关联。修：保留 high-level summary 作为 anchor，每个 chunk 都看到这个 summary。

**Tool result trim 截断关键部分**——`grep` 输出被 trim 后正好漏掉用户想看的 match。修：trim 时保留首尾各 1000 字符 + "..."，不直接砍中段；或者用 LLM 摘要而不是机械 trim。

下一章 [05. Permissions / Sandbox](../05-permissions-sandbox/) 拆 harness 第二块基石——危险操作怎么拦、agent 怎么不能删用户文件。
