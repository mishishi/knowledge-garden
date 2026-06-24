# 06. Prompt 设计：把检索结果喂给 LLM

> 检索拿到 Top-5 不代表 LLM 会用好。**Prompt 设计 = 怎么把 5 个 chunk 拼起来**，决定最终答案质量。

## 最常见的反模式

```python
# ❌ 90% 教程这么写，实际效果很差
prompt = f"""基于以下上下文回答问题：

{context}

问题：{question}
"""
```

**哪里差：**
- 没有指令（「只基于上下文」「不知道就说不知道」）
- 没有格式（要 JSON 还是散文？）
- 没有引用（「来源：xxx.pdf p.5」）
- context 没有结构（一坨糊一起）

## 生产级 Prompt 模板

```python
SYSTEM_PROMPT = """你是 {company_name} 的 AI 助手。基于【参考资料】回答用户问题。

严格规则：
1. 只基于【参考资料】回答，不要用你自己的知识
2. 如果【参考资料】里没有答案，直接说「未找到相关资料」——不要编造
3. 回答要简洁，3 句话内
4. 必须在结尾列出引用的资料编号，例如：[1][3]
5. 如果【参考资料】互相矛盾，指出矛盾点

参考资料格式：
[编号] 来源路径 | 页码
\"\"\"
{context_with_metadata}
\"\"\"
"""

USER_PROMPT = "{question}"
```

关键元素：
- **角色定位**：「{company_name} 的 AI 助手」——给 LLM 锚定
- **明确禁止**：「不知道就说不知道」「不要编造」——压住幻觉
- **格式约束**：3 句话、引用编号
- **结构化 context**：每段前加编号，方便引用

## Context 拼装

不要把 5 个 chunk 直接 `"\n\n".join()`，要结构化：

```python
def build_context(chunks: list[dict]) -> str:
    """把 Top-K chunks 拼成结构化 context"""
    parts = []
    for i, c in enumerate(chunks, 1):
        meta = c["metadata"]
        # 来源标注
        source = f"{meta.get('source', '未知')} p.{meta.get('page', '?')}"
        # 限制长度（避免 prompt 爆掉）
        text = c["text"][:800]
        parts.append(f"[{i}] 来源：{source}\n{text}")
    return "\n\n".join(parts)
```

最终 prompt 形如：

```
【参考资料】
[1] 来源：/uploads/2024-q3.pdf p.5
2024 年第三季度营收为 12.3 亿元，同比增长 18%...

[2] 来源：/uploads/2024-q3.pdf p.7
第三季度净利润 1.8 亿元...

【用户问题】
2024 Q3 营收是多少？
```

## Token 预算管理

LLM 上下文有限（GPT-4 是 128K，Claude 是 200K），但实际**有效注意力的窗口是前 8K + 后 2K**（中间遗忘）。

**Top-K 选择：**
- GPT-4 (8K 上下文): Top-3，每个 chunk 限制 1500 token
- GPT-4 (128K): Top-10，每个 chunk 限制 2000 token
- Claude (200K): Top-15，每个 chunk 限制 2500 token

```python
def truncate_chunks(chunks: list[dict], max_tokens_per_chunk: int = 1500) -> list[dict]:
    """粗略按字符截断（中文 1 字符 ≈ 1.5 token）"""
    max_chars = int(max_tokens_per_chunk / 1.5)
    return [
        {**c, "text": c["text"][:max_chars]}
        for c in chunks
    ]
```

## 处理「无答案」

用户问题检索不到相关 chunk 时，**LLM 容易编造**。防御：

```python
SYSTEM_PROMPT = """...

如果【参考资料】与问题无关或为空：
- 不要试图回答
- 说「未找到与您问题相关的资料。建议您换个说法或联系人工客服。」
- 不要道歉、不要补充「您可以试试问 xxx」——那是 prompt injection 漏洞
"""
```

然后在 Python 层先检查：

```python
def rag_answer(query: str, top_k=5):
    chunks = rag_search(query, top_k=top_k)

    # 强过滤：rerank 分数太低 = 不相关
    if not chunks or chunks[0]["score"] < 0.3:
        return "未找到与您问题相关的资料。"

    context = build_context(chunks)
    prompt = SYSTEM_PROMPT.format(context_with_metadata=context)
    return llm.complete(prompt, user_message=query)
```

**强过滤 > 依赖 LLM 自己判断**。

## 上下文结构：Parent Document Retrieval

chunk 切得太小 → 检索精确但**上下文不完整**。解法：**小块检索 + 大块返回**。

```python
# 入库时：小 chunk (200 token) embed + 标记 parent_id
chunks = []
for doc in documents:
    parent_chunks = splitter_large.split(doc.text)  # 大块 1000 token
    for parent in parent_chunks:
        parent_id = hash(parent.text)
        child_chunks = splitter_small.split(parent.text)  # 小块 200 token
        for child in child_chunks:
            chunks.append({
                "id": hash(child.text),
                "text": child.text,
                "embedding": embed(child.text),
                "metadata": {"parent_id": parent_id, ...},
            })

# 检索时：小块检索，返回时换 parent 大块
def search_with_parent(query, top_k=5):
    children = vector_search(query, top_k=top_k)
    # 去重 parent
    parent_ids = list({c.metadata["parent_id"] for c in children})
    # 拿 parent 完整内容
    parents = db.get_by_ids(parent_ids)
    return parents
```

LLM 看到的 chunk **比检索的 chunk 大**，上下文更完整。

## 多轮对话的 RAG

用户连续对话时，**当前问题可能脱离上下文**：

```
User: 2024 Q3 营收多少？
Bot: 12.3 亿
User: 那 Q4 呢？   ← 这个 "那" 指代什么？
```

**解决**：把对话历史也喂给 LLM，让它改写 query：

```python
def rewrite_query(history: list[dict], current_q: str) -> str:
    history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history[-4:])
    prompt = f"""基于对话历史，把用户最新问题改写成独立完整的问题（包含所有上下文）：

{history_text}

最新问题：{current_q}

改写后的问题（独立、完整、可直接检索）："""
    return llm.complete(prompt)

# 用
rewritten = rewrite_query(history, "那 Q4 呢？")
# rewritten = "2024 年第四季度营收是多少？"
chunks = rag_search(rewritten)
```

**改写 query 是多轮 RAG 必做项**——否则第 3 轮之后检索基本全失效。

## Stream 输出

长答案别让用户干等。**用流式输出**：

```python
import openai
stream = openai.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "system", "content": system}, {"role": "user", "content": question}],
    stream=True,
)
for chunk in stream:
    delta = chunk.choices[0].delta.content or ""
    print(delta, end="", flush=True)
```

UX 上 **首字延迟 < 1s** 用户体感就流畅。

## 下篇

[07. 混合检索](../07-hybrid-search/) — 向量 + 关键词双路召回，提升边缘场景召回率。
