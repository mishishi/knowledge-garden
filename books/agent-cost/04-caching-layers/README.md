# 04. Caching 三层

上 routing 之后我的账单从 $400 降到 $180。但我看 log 发现一个事：**同一段 prompt 一周内被发 800 多次**。

这 800 次每次都走完整 LLM call。如果能 cache 掉 70%，光这一段就省 $90/月。Cache 是**单次 ROI 最高的优化**。

## 三种 cache 不是同一个东西

我一开始以为 cache 就是"问过的问题别再问"。后来才发现这事分三层，每层解决的问题不一样：

**Exact match cache** — 输入完全相同，输出直接用。Redis / Memcached 实现。**适合**：FAQ 机器人、固定模板生成、重复 query。

**Semantic cache** — 意思相似（不是完全相同），输出也近似。embedding 相似度判断。**适合**：用户 query 改个说法但意图一样、bug 描述变体。

**Prefix cache** — OpenAI / Anthropic provider 自己做的。如果你的 prompt 前缀（system + few-shot + 静态 context）保持稳定，provider 自动 cache 那一段，**只算一半价**。**适合**：system prompt 长（>1K token）且不变的 agent。

## exact match cache 命中率比你想的低

我先加的 exact match。`hash(query + context_hash) → response`，存 Redis。

跑了一周命中率 4%。**比我想象的低 4 倍**。

为什么？用户的 query 不会逐字重复：
- "如何修这个 bug" vs "这个 bug 怎么修"
- "今天天气" vs "今天北京天气怎么样"

exact match cache 只在用户**复制粘贴同一段话**的时候才命中。客服场景还行，agent 类一般 5-15%。

```python
import hashlib
import json
import redis

r = redis.Redis()

def cached_call(prompt, context, model):
    key = hashlib.sha256(
        (prompt + json.dumps(context, sort_keys=True)).encode()
    ).hexdigest()

    cached = r.get(key)
    if cached:
        return json.loads(cached)  # 命中, 0 token

    response = call_llm(prompt, context, model)
    r.setex(key, 86400, json.dumps(response))  # 24h TTL
    return response
```

Trick：TTL 别设太长。1-7 天够长了，再长 cache 里堆满了过期 query 没人用，命中率会被新数据稀释。

## semantic cache 是更普适的解

exact 不行就上语义。我用 embedding + cosine similarity 找最近邻。

```python
import numpy as np
from typing import Optional

class SemanticCache:
    def __init__(self, threshold=0.92):
        self.threshold = threshold
        self.store = []  # [(embedding, response, metadata)]

    def lookup(self, query_emb):
        if not self.store:
            return None
        # 找最相似的
        best_score, best_resp = -1, None
        for emb, resp, _ in self.store:
            score = np.dot(query_emb, emb) / (
                np.linalg.norm(query_emb) * np.linalg.norm(emb)
            )
            if score > best_score:
                best_score, best_resp = score, resp
        return best_resp if best_score >= self.threshold else None

    def store(self, query_emb, response):
        self.store.append((query_emb, response, time.time()))
```

但**几个坑**我替你踩过了：

**1. 相似度高 ≠ 答案对**。"Python 怎么装"和"Python 装不上"语义相似但答案可能不同。要做 response-side check：缓存的 response 真的回答了 query 吗？或者干脆把 query 也存下来，命中时再过一遍 judge model。

**2. embedding 本身花钱**。每次 query 都要 embed 一次。`text-embedding-3-small` 是 $0.02/1M，1K call 0.2M token = $0.004。听起来便宜但如果命中率 20%，你花 $0.004 替掉 $0.5 的 LLM call。值。如果命中率 5%，你花 $0.004 替掉 $0.125。**还是值**，但 ROI 没 exact 那么夸张。

**3. 阈值难调**。0.95 太严，命中率低；0.85 太松，错的答案冒出来。**用 task-specific eval 调**——拿 100 个真实 query，测不同阈值下"答对率"和"命中率"。

跑下来 semantic cache 给我 22% 命中率（vs exact 4%），整体账单再降 25%（$180 → $135）。

## prefix cache 是隐藏 boss

这个 90% 的开发者不知道。

OpenAI 2024 年 8 月开始自动给长 prompt 做 prefix cache：

- prompt 超过 1024 token 才有效
- 命中条件：**前 N 个 token 完全相同**（字符级）
- 折扣：命中部分按 cached input 单价算（GPT-4o 是 input 的一半）

听起来限制很多——prompt 必须字符级相同。但其实**只要你 system prompt 不变**，就命中。few-shot examples 不变，就命中。RAG 注入的文档可能不命中（每次 query 检索的都不一样），但 RAG 之前的所有 prefix 都命中。

我的 agent 配置：

```
[system prompt 4000 token] [few-shot 2000 token] [RAG docs 4000-12000 token] [user query]
└────── prefix 命中 ──────────┘
```

每次 call 的 6000 token prefix 都命中，剩下 4000-12000 token 走正常 input 价。**等于在 RAG 之前砍了 40% 的 input 钱**。

这个 0 行代码、0 基础设施成本，纯靠**保持 system prompt 稳定**就拿到。**先做这个**。

## 三层叠起来

我现在的 cache 栈：

1. **Prefix cache**（自动，0 行代码）— 60% 命中
2. **Exact cache**（Redis）— 5% 命中（拦截重复 query）
3. **Semantic cache**（embedding）— 22% 命中（拦截语义重复 query）

整体 cache 命中率 70%。账单从 $400 降到 $90。

我后来还加了 **negative cache**（失败的 response 也缓存，比如"我不知道"），进一步省了一点。5% 不到，但聊胜于无。

下一章讲 prompt 压缩——cache 把"重复"省了，但如果 prompt 本身就臃肿，cache 也救不了你。下一章是把 4K prompt 压到 800 而能力损失 < 5% 的实战。
