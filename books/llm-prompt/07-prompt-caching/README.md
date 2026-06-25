# 07. Prompt Caching：降成本 10x

> 长 prompt 重复发，每次都按全量 token 计费——这是 2024-2025 年最常见的「烧钱漏洞」。这章讲 cache 怎么工作、怎么写 prompt 最大化命中、真实成本对比。

## Cache 是什么

**Prompt caching = 把已经处理过的 prompt 片段存起来，下次直接复用，不重新计算**。

```python
# 没 cache：每次都按全量 token 计费
for user_query in queries:
    long_system_prompt = "你是...（5000 字）"
    prompt = long_system_prompt + user_query
    llm.call(prompt)   # 每次 5000 token system + user

# 有 cache：system 重复部分按 1/10 价格
# OpenAI / Anthropic / Google 都支持 prompt caching
```

**节省幅度**（OpenAI GPT-4o）：不命中 $2.50/1M（基准），命中 $0.625/1M，**省 75%**。

**Anthropic Claude Sonnet 4.5**：Write（首次）$3.75/1M（+25%）、Hit（命中）$0.30/1M，**省 90%**。

**100 万次调用、5000 token system prompt 的成本**：

不用 cache：5,000,000,000 token × $2.50/1M = **$12,500**。
用 cache（90% 命中）：write $18.75 + hit $1,498.50 = **$1,517.25**。
**省 88%——$12,500 → $1,517，省 $11,000。**

## Cache 怎么工作

**命中机制**——不是按字符串匹配，而是按「token prefix」：

```
Prompt 1: [system 5000 tokens] + [user 100 tokens]
Prompt 2: [system 5000 tokens (相同)] + [user 200 tokens (不同)]

→ Prompt 2 的前 5000 tokens 命中 cache
→ 只对后 200 tokens 全价计费
```

关键：

- Cache 从 prompt **开头**开始匹配（前缀匹配）
- 中间不能插入「破坏 cache 的内容」（如时间戳）
- 命中长度 ≥ 1024 token（OpenAI / Anthropic）才有意义
- 缓存有效期 5-10 分钟（Anthropic 5-10 分钟，OpenAI 5-60 分钟）

**显式标记 vs 自动**：

OpenAI（自动）—— 不需标记，但 cache 只对 ≥ 1024 token 的 prompt 生效：

```python
response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": long_system_prompt},
        {"role": "user", "content": user_query},
    ],
)
# usage.prompt_tokens_details.cached_tokens 看命中多少
```

Anthropic（显式）—— 用 `cache_control` 标记：

```python
import anthropic

response = anthropic.Anthropic().messages.create(
    model="claude-sonnet-4-5",
    system=[
        {
            "type": "text",
            "text": long_system_prompt,
            "cache_control": {"type": "ephemeral"},   # 显式标记
        }
    ],
    messages=[{"role": "user", "content": user_query}],
)
# usage.cache_creation_input_tokens / cache_read_input_tokens
```

Gemini（自动 + 显式）—— 用 `CachedContent.create`：

```python
import google.generativeai as genai

cached_content = genai.caching.CachedContent.create(
    model="models/gemini-2.5-flash",
    system_instruction=long_system_prompt,
    contents=[user_query],
    ttl=datetime.timedelta(minutes=10),
)
```

## 6 大命中规则

**1. 把固定内容放最前**——system 放最前，user 放后面。system 是固定的→命中；user 每次变→按全价计费。

```python
# 错：user 放最前
messages = [
    {"role": "user", "content": user_query},       # 变 → 命中失败
    {"role": "system", "content": long_system},
]

# 对：system 放最前
messages = [
    {"role": "system", "content": long_system},     # 固定 → 命中
    {"role": "user", "content": user_query},
]
```

**2. cache 内容 ≥ 1024 token**——小 system prompt 不值得开 cache，token 不够命中无意义。5000+ token 才有明显节省。

**3. 避免动态内容在 cache 块**——系统 prompt 里加时间戳/UUID/random 都会让 cache 永远不命中。动态内容放 user message。

```python
# 错：system 里有时间戳
system_with_time = f"当前时间：{datetime.now()}\n你是 X..."
# system 每次不一样 → cache 永远不命中

# 对：动态内容放 user
messages = [
    {"role": "system", "content": "你是 X..."},   # 固定 → 命中
    {"role": "user", "content": f"当前时间：{datetime.now()}\n{user_query}"},  # 变化
]
```

**4. tool 定义放 cache 块**——Anthropic 把整个 tools 列表当 cache 块，工具定义也命中 cache，省 N 倍 token。

**5. 长文档放 cache 块**——RAG 应用每次带同一篇 5000 token 文档，cache 后省 90%。

```python
# 对：长文档 cache
messages = [
    {"role": "system", "content": "你是 X"},
    {"role": "user", "content": f"文档：{long_doc_5000_tokens}"},  # 第一次 write
]
# 后续 user 替换为新问题
for q in queries[1:]:
    messages.append({"role": "user", "content": f"问题：{q}"})
    # 文档部分 cache 命中
```

**6. 多模态也支持 cache**——OpenAI 多模态 + cache，同一张图片在后续 query 命中 cache。

## 真实成本对比

**场景 1：客服 Agent**——每日 10,000 次调用、3000 token system + 200 user + 1000 history + 500 tools。

不用 cache：47M token × $2.50/1M = $117.5/天 = **$3,525/月**。
用 cache（80% 命中）：$51.5/天 = **$1,545/月**。**节省 56%**。

**场景 2：长文档 RAG**——每日 5,000 次查询、8000 token 文档 + 100 query + 500 output。

不用 cache：$101.25/天。
用 cache（100% 命中）：$38.27/天。**节省 62%**。

**场景 3：固定 prompt 的批量任务**——每日 100,000 次翻译、2000 system + 500 input + 500 output。

不用 cache：$625/天 = $18,750/月。
用 cache（100% 命中）：$1,435/天 = $43,050/月。**反而贵了 2.3x**。

**为什么**——write 阶段多 25% 价格，但 hit 省 90%——**命中率必须足够高才划算**。

**经验**：cache 命中率 > 50% 才考虑用。命中率 < 30% 不如不用。

## 5 大反模式

**1. 小 system prompt 开 cache**——< 1024 token 的 cache 不生效，浪费 write 阶段。

**2. 命中率低时开 cache**——每个 user query 完全不一样，命中率 0%，OpenAI 不会 cache（即使 system 一样，conversation 整体变了）。

**3. Cache 块里有随机数 / UUID**——`f"Request ID: {uuid4()}\n你是 X..."` 每次都新，cache 失效。

**4. 依赖 cache 提高速度**——cache 命中时延迟差不多（几百 ms），cache 命中是**省钱不是省时**。

**5. 忽视 cache TTL**——Anthropic 5-10 分钟、OpenAI 5-60 分钟。长间隔查询 → cache 失效。**高频查询场景才用 cache**——1 分钟 100 次 vs 1 小时 100 次，效果差很多。

## 实战：长文档 RAG 完整例子

```python
import openai


# 一次性 write cache
def init_rag_cache(long_doc: str):
    """第一次调用，把长文档写入 cache"""
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "你是文档问答助手。基于文档回答用户问题。"},
            {"role": "user", "content": f"文档：\n{long_doc}\n\n（请记住这份文档，后续我会问相关问题）"},
        ],
    )
    print(f"Init: {response.usage.prompt_tokens_details}")
    return response


def query_with_cache(question: str):
    """后续查询，命中 cache"""
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "你是文档问答助手。基于文档回答用户问题。"},
            {"role": "user", "content": f"文档：\n{long_doc}\n\n问题：{question}"},
        ],
    )
    print(f"Query: {response.usage.prompt_tokens_details}")
    return response.choices[0].message.content


# 跑
long_doc = open("big_doc.txt").read()   # 假设 8000 token
init_rag_cache(long_doc)
for q in ["X 是什么？", "Y 怎么用？", "Z 跟 A 有什么关系？"]:
    answer = query_with_cache(q)
    print(f"答案：{answer}\n")
```

关键：第 2 次起 prompt 一模一样，OpenAI 自动 cache（命中条件：prompt ≥ 1024 token + 内容相同）。

## 怎么测 cache 命中率

```python
import openai
from collections import defaultdict

stats = defaultdict(int)

for _ in range(100):
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": long_system},
            {"role": "user", "content": random_query()},
        ],
    )
    details = response.usage.prompt_tokens_details
    stats["total_tokens"] += response.usage.prompt_tokens
    stats["cached_tokens"] += details.cached_tokens

print(f"命中率: {stats['cached_tokens'] / stats['total_tokens']:.1%}")
# 命中率 > 50% 才值得开 cache
```

## Cache 策略 4 步决策

```
1. prompt token 总数 ≥ 1024？
   ├─ 否 → 不用 cache（不生效）
   └─ 是
2. 调用频率 ≥ 1/分钟？
   ├─ 否 → 不用 cache（cache 5-10 分钟失效）
   └─ 是
3. 同一 prompt 出现 ≥ 2 次？
   ├─ 否 → 不用 cache（命中率低）
   └─ 是
4. 命中率 ≥ 50%？
   ├─ 否 → 不用 cache（write 阶段反贵）
   └─ 是 → 开 cache
```

## Anthropic 显式 cache_control 实战

```python
import anthropic


def query_with_explicit_cache(system_text: str, user_text: str):
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"},   # 标记 cache
            }
        ],
        messages=[{"role": "user", "content": user_text}],
    )
    usage = response.usage
    print(f"cache_creation: {usage.cache_creation_input_tokens}")
    print(f"cache_read: {usage.cache_read_input_tokens}")
    return response


# 第一次（write）
query_with_explicit_cache(long_system, "问题 1")
# cache_creation: 5000, cache_read: 0

# 5 分钟内（hit）
query_with_explicit_cache(long_system, "问题 2")
# cache_creation: 0, cache_read: 5000

# 10 分钟后（miss + new write）
query_with_explicit_cache(long_system, "问题 3")
# cache_creation: 5000, cache_read: 0
```

## 3 个常见坑

**坑 1：以为 cache 自动生效**——OpenAI cache 是「best effort」——prompt 一样 + 长度够 + 时间窗口内才命中，不是 100% 命中。一定要用 `usage.prompt_tokens_details.cached_tokens` 验证。

**坑 2：cache 块里加可变内容**——`f"时间：{now()}\n你是 X"` 每次不一样，cache 失效。修：动态内容放 user。

**坑 3：多轮对话累积历史破坏 cache**——早期 message 被 push 出去 → cache 失效。修：定期压缩历史（summary），保留最近 5 轮：

```python
if len(messages) > 20:
    summary = llm.call(f"总结上面对话: {messages}")
    messages = [{"role": "system", "content": "你是 X"},
                {"role": "user", "content": f"之前对话总结: {summary}"},
                *messages[-5:]]   # 保留最近 5 轮
```
