# 07. Prompt Caching：降成本 10x

> 长 prompt 重复发，每次都按全量 token 计费——这是 2024-2025 年最常见的「烧钱漏洞」。这章讲 cache 怎么工作 + 怎么写 prompt 最大化命中 + 真实成本对比。

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

**节省幅度**（OpenAI GPT-4o）：

| Cache | 价格（input） | 节省 |
|-------|-------------|------|
| 不命中 | $2.50 / 1M | 基准 |
| 命中 | $0.625 / 1M | **75%** |

**Anthropic Claude Sonnet 4.5**：

| Cache | 价格 | 节省 |
|-------|------|------|
| Write（首次）| $3.75 / 1M | +25% |
| Hit（命中）| $0.30 / 1M | **90%** |

**100 万次调用、5000 token system prompt 的成本**：

```
不用 cache：
  5,000,000,000 token × $2.50 / 1M = $12,500

用 cache（90% 命中）：
  write: 5,000,000 × $3.75 / 1M = $18.75  (一次)
  hit:   4,995,000,000 × $0.30 / 1M = $1,498.50
  total: $1,517.25

节省 88%
```

**$12,500 → $1,517，省 $11,000。**

## Cache 怎么工作

### 命中机制

Cache 命中**不是按字符串匹配**，而是按「token prefix」：

```
Prompt 1: [system 5000 tokens] + [user 100 tokens]
Prompt 2: [system 5000 tokens (相同)] + [user 200 tokens (不同)]

→ Prompt 2 的前 5000 tokens 命中 cache
→ 只对后 200 tokens 全价计费
```

**关键**：

- Cache 从 prompt **开头**开始匹配（前缀匹配）
- 中间不能插入「破坏 cache 的内容」（如时间戳）
- 命中长度 ≥ 1024 token（OpenAI）/ 1024 token（Anthropic）才有意义
- 缓存有效期 5-10 分钟（Anthropic 5-10 分钟，OpenAI 5-60 分钟）

### 显式标记 vs 自动

**OpenAI**（自动）：

```python
# OpenAI 自动 cache（不需标记）
# 但 cache 只对 ≥ 1024 token 的 prompt 生效
response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": long_system_prompt},  # ≥ 1024 token
        {"role": "user", "content": user_query},
    ],
)
# usage.prompt_tokens_details.cached_tokens 看命中多少
```

**Anthropic**（显式）：

```python
import anthropic

response = anthropic.Anthropic().messages.create(
    model="claude-sonnet-4-5",
    system=[
        {
            "type": "text",
            "text": long_system_prompt,
            "cache_control": {"type": "ephemeral"},   # ← 显式标记
        }
    ],
    messages=[{"role": "user", "content": user_query}],
)
# usage.cache_creation_input_tokens / cache_read_input_tokens
```

**Gemini**（自动 + 显式）：

```python
# Gemini 自动 cache，但用 cached_content 显式
import google.generativeai as genai

cached_content = genai.caching.CachedContent.create(
    model="models/gemini-2.5-flash",
    system_instruction=long_system_prompt,
    contents=[user_query],   # 预填
    ttl=datetime.timedelta(minutes=10),
)

model = genai.GenerativeModel.from_cached_content(cached_content)
response = model.generate_content("next user query")
```

## 6 大命中规则

### 规则 1：把固定内容放最前

```python
# 错：user 放最前
messages = [
    {"role": "user", "content": user_query},       # 变 → 命中失败
    {"role": "system", "content": long_system},    # 后面的内容 cache 不到
]

# 对：system 放最前
messages = [
    {"role": "system", "content": long_system},     # 固定 → 命中
    {"role": "user", "content": user_query},
]
```

### 规则 2：cache 内容 ≥ 1024 token

```python
# 错：cache 500 token 的 system（< 1024，cache 不生效）
short_system = "你是 X"   # 10 token

# 对：cache 5000 token 的 system（≥ 1024）
long_system = "你是 X, ...（5000 字）"   # 5000 token
```

**小 system prompt 不值得开 cache**——token 不够，命中无意义。

### 规则 3：避免动态内容在 cache 块

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

### 规则 4：tool 定义放 cache 块

```python
# 错：tool 定义每次都重发
for q in queries:
    messages = [
        {"role": "system", "content": "你是 X"},
        {"role": "user", "content": q},
        {"role": "assistant", "content": None, "tool_calls": [...]},   # tool 重复
    ]

# 对：tool 定义独立 cache
# Anthropic 把 tools 列表加 cache_control
response = anthropic.Anthropic().messages.create(
    model="claude-sonnet-4-5",
    tools=[...],   # 整个 tool 列表当 cache 块
    system=[
        {"type": "text", "text": "你是 X", "cache_control": {"type": "ephemeral"}},
    ],
    messages=[{"role": "user", "content": q}],
)
# 工具定义也命中 cache，省 N 倍
```

### 规则 5：长文档放 cache 块

```python
# 场景：RAG 应用，每次带同一篇 5000 token 文档

# 错：每次都全价
for q in queries:
    prompt = f"""
    文档：{long_doc_5000_tokens}
    问题：{q}
    """
    llm.call(prompt)   # 5000 token × N 次

# 对：长文档 cache
messages = [
    {"role": "system", "content": "你是 X"},
    {"role": "user", "content": f"文档：{long_doc_5000_tokens}"},  # ← 第一次 write
]
# 后续 user 替换为新问题
for q in queries[1:]:
    messages.append({"role": "user", "content": f"问题：{q}"})
    # 文档部分 cache 命中
```

### 规则 6：多模态也支持 cache

```python
# OpenAI 多模态 + cache
response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "https://..."}},   # ← cache 这张图
                {"type": "text", "text": "描述这张图"},
            ],
        },
    ],
)
# 同样的图片在后续 query 命中 cache
```

## 真实成本对比

### 场景 1：客服 Agent

```
每日 10,000 次调用
System prompt: 3000 token（产品手册 + 客服规则）
User query: 200 token
Conversation history: 平均 1000 token
Tool definitions: 500 token

不用 cache：
  input: (3000 + 200 + 1000 + 500) × 10000 = 47,000,000 token
  cost: 47M × $2.50/1M = $117.5/天 = $3,525/月

用 cache（80% 命中）：
  write: 3000 × 10000 / 60 (1/60 unique conversations) = 500,000 token × $3.75/1M = $1.875
  hit:  3000 × 10000 × 0.8 = 24,000,000 token × $0.30/1M = $7.20
  + 不可 cache 部分: 1700 × 10000 = 17M × $2.50/1M = $42.5
  total: $51.5/天 = $1,545/月

节省 56%
```

### 场景 2：长文档 RAG

```
每日 5,000 次查询
文档: 8000 token（PDF）
Query: 100 token
Output: 500 token

不用 cache：
  input: 8100 × 5000 = 40,500,000 token × $2.50/1M = $101.25/天

用 cache（100% 命中，文档不变）：
  write: 8000 × 1 (一次) = 8000 × $3.75/1M = $0.03
  hit:  8000 × 4999 = 39,992,000 × $0.30/1M = $11.99
  + query: 100 × 5000 = 500,000 × $2.50/1M = $1.25
  + output: 500 × 5000 = 2,500,000 × $10/1M = $25
  total: $38.27/天

节省 62%
```

### 场景 3：固定 prompt 的批量任务

```
每日 100,000 次翻译
System: 2000 token（翻译规则）
Input: 500 token（中英对照）
Output: 500 token

不用 cache：
  input: 2500 × 100K = 250M token × $2.50/1M = $625/天 = $18,750/月

用 cache（100% 命中）：
  write: 2000 × 100K = 200M × $3.75/1M = $750
  hit:  2000 × 100K = 200M × $0.30/1M = $60
  + 不可 cache: 500 × 100K = 50M × $2.50/1M = $125
  + output: 500 × 100K = 50M × $10/1M = $500
  total: $1,435/天 = $43,050/月

反而贵了 2.3x！！
```

**为什么？** 因为 write 阶段多 25% 价格，但 hit 省 90%——**命中率必须足够高才划算**。

**经验**：cache 命中率 > 50% 才考虑用。命中率 < 30% 不如不用。

## 5 大反模式

### 反模式 1：小 system prompt 开 cache

```python
# 错：< 1024 token 的 cache 不生效
short_system = "你是 X"   # 10 token，开 cache 浪费 write 阶段

# 对：≥ 1024 token 才有意义
long_system = "你是 X, ...（5000 字）"
```

### 反模式 2：命中率低时开 cache

```python
# 错：每个 user query 完全不一样，命中率 0%
for q in unique_queries:  # 10000 个不同的 query
    messages = [{"role": "system", "content": system}, {"role": "user", "content": q}]
    # system 每次一样，但 messages 列表每次不同

# OpenAI 不会 cache（即使 system 一样，conversation 整体变了）
```

### 反模式 3：Cache 块里有随机数 / UUID

```python
# 错
system = f"Request ID: {uuid4()}\n你是 X..."

# 对
system = "你是 X..."
```

### 反模式 4：依赖 cache 提高速度

```python
# 错：以为 cache 加快响应
# 实际：cache 命中时延迟差不多（几百 ms），cache 命中是省钱不是省时

# 对：理解 cache 的真实作用 = 省钱
```

### 反模式 5：忽视 cache TTL

```python
# 错：以为 cache 永久有效
# 实际：Anthropic 5-10 分钟，OpenAI 5-60 分钟
# 长间隔查询 → cache 失效

# 对：高频查询场景才用 cache
# 1 分钟 100 次 vs 1 小时 100 次，效果差很多
```

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

**关键**：第 2 次起 prompt 一模一样，OpenAI 自动 cache（命中条件：prompt ≥ 1024 token + 内容相同）。

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
    cached = details.cached_tokens
    total = response.usage.prompt_tokens
    stats["total_tokens"] += total
    stats["cached_tokens"] += cached

print(f"命中率: {stats['cached_tokens'] / stats['total_tokens']:.1%}")
# 命中率 > 50% 才值得开 cache
```

## Cache 策略决策

```
决策流程：
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
                "cache_control": {"type": "ephemeral"},   # ← 标记 cache
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
# cache_creation: 5000
# cache_read: 0

# 5 分钟内（hit）
query_with_explicit_cache(long_system, "问题 2")
# cache_creation: 0
# cache_read: 5000

# 10 分钟后（miss + new write）
query_with_explicit_cache(long_system, "问题 3")
# cache_creation: 5000
# cache_read: 0
```

## 跑不起来的常见坑

**坑 1：以为 cache 自动生效**

```python
# OpenAI cache 是「best effort」——prompt 一样 + 长度够 + 时间窗口内才命中
# 不是 100% 命中
# 一定要用 usage.prompt_tokens_details.cached_tokens 验证
```

**坑 2：cache 块里加可变内容**

```python
# 错：cache 失效
messages = [
    {"role": "system", "content": f"时间：{now()}\n你是 X"},   # 每次不一样
]

# 对：分开
messages = [
    {"role": "system", "content": "你是 X"},   # 固定 → cache
    {"role": "user", "content": f"时间：{now()}\n{query}"},   # 变化
]
```

**坑 3：多轮对话累积历史破坏 cache**

```python
# 多轮对话累积 messages
# 早期 message 被 push 出去 → cache 失效

# 解决：定期压缩历史（summary）
if len(messages) > 20:
    summary = llm.call(f"总结上面对话: {messages}")
    messages = [{"role": "system", "content": "你是 X"},
                {"role": "user", "content": f"之前对话总结: {summary}"},
                *messages[-5:]]   # 保留最近 5 轮
```

## 这章跑完之后你该会什么

- Cache 是什么 + 命中机制（前缀匹配 + TTL）
- 6 大命中规则
- 真实成本对比（哪些场景值得用）
- 5 大反模式
- OpenAI / Anthropic / Gemini 3 个 provider 的写法
- 4 步决策流程（判断要不要开 cache）
- 怎么测命中率

## 下篇

[08. Prompt Injection 防御](../08-prompt-injection/) — 攻击向量（直接 / 间接 / jailbreak）+ 6 层防御 + 红队测试方法。
