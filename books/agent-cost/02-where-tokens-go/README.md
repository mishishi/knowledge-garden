# 02. Token 是怎么烧的

第一次看 OpenAI 账单我以为是 "我用的模型太贵"。第二次看账单，我以为 "用户用太多了"。第三次我才意识到：**token 烧在哪我根本不知道**。

那一周我把所有 call 的 log dump 出来，按用途分了一下。1.2 亿 token 拆开看：

- 52% — system prompt + few-shot examples（每次 call 都带）
- 28% — 用户输入（query + 上下文）
- 16% — RAG retrieval 注入的文档片段
- 4% — agent 自己生成的 chain-of-thought / function call 推理

我以为的"主战场"（用户输入）只占 28%。剩下 72% 是我自己代码决定的。

## input / output / cache 是三件事

OpenAI 账单分三栏：

- **input** — 你发给模型的 prompt（包含 system + user + RAG 注入）
- **output** — 模型生成的回复（包含 reasoning + final answer）
- **cached input** — 命中 prompt cache 的部分（按折扣价算）

价格差很大。GPT-4o 大概 input $2.5/1M，output $10/1M，cached input $1.25/1M。**output 是 input 的 4 倍，cache 是 input 的一半**。

如果你只盯着总 token 数，会错过三件事：

- 能不能让更多进 cache（半价）
- 能不能让 output 更短（4 倍价）
- 能不能让 input 更精简（基础价）

## system prompt 是最容易被忽略的

我那个 1.2 亿 token 里 52% 是 system prompt。听起来夸张对吧？拆开看：

- 角色说明 200 token
- 任务约束 400 token
- 输出格式示例 800 token
- 工具描述 1500 token
- 历史对话摘要（如果用 sliding window）1500 token

加起来 ~4400 token。每个 call 都带，1 个月 27,000 次 call = 1.18 亿 token。**一个 4400 token 的 system prompt 在 2.7 万次 call 下能烧 1.2 亿 token**。

我的 system prompt 是 6 个月前写的，从来没 review 过。后来我做了 3 件事：
1. 删了重复的格式示例（一份就够了，之前写了 2 份）
2. 工具描述从描述体改成签名（200 token → 60 token）
3. 历史摘要只在第 5 轮之后才注入（前 4 轮直接用原文）

这 3 件事砍掉了 1800 token。每个 call 少花 $0.0045。一个月省 $120。**只是因为我 review 了一下自己 6 个月没动过的 system prompt。**

## 长 context 的 hidden cost

OpenAI 的 pricing 表告诉你 input $2.5/1M。但 128K context model 不是这样算的。

当 prompt 超过 32K，OpenAI 会自动切到更高价的 tier。GPT-4o 在 32K 以下 $2.5/1M，32K-128K 区间变成 $5/1M。**长度翻一倍，价格翻一倍**。

我之前不知道这事。我那个 RAG agent 默认注入 8 段 top-k 文档，每段 ~3000 token，加起来 24K。再加 system 4K + user 2K = 30K，刚好卡在边界上。

但偶尔用户 query 引用了一篇超长文档，context 冲到 80K，单次 call 价格翻 3 倍。一个月遇到 50 次这样的 call 就多烧 $30。

修法：在 RAG 检索后做 length check，超过 25K 就把 top-k 从 8 段降到 5 段。多花 5 行代码，省 $30/月。

## chain-of-thought 是双刃剑

agent 类应用普遍用 "think step by step" prompt 来逼模型先推理再行动。output 长度涨 3-5 倍，质量确实涨 10-20%。

但你付出了什么？

一个 5-step agent loop，每步 500 token 推理 = 2500 token output。光这一项一个月 27,000 次 call × 2500 token = 6700 万 token，按 output 单价 $10/1M = $670。

如果你能让模型跳过推理（直接行动 + 简短 reason）只在确实需要时再 think，output 能砍 50%。一个简单的 pattern：

```
if step_complexity == "low":
    prompt = "直接回答，跳过推理"
elif step_complexity == "high":
    prompt = "think step by step, then act"
```

我那个 agent 调成这个后，output token 从月 6700 万掉到 4200 万。省 $250/月。质量评估下来只降了 3%。

## reasoning model 单独算

如果你用 o1 / o3 这种 reasoning model，价格是另一个数量级。o1 input $15/1M，output $60/1M，cached input $7.5/1M。**比 GPT-4o 贵 6 倍**。

reasoning model 适合：复杂规划、代码生成、数学推理。不适合：格式化、分类、简单 QA、聊天。

我的 agent 把 o1 用在 3 个地方：plan 生成、tool selection、错误诊断。其它地方都用 4o。**不是"用最便宜的 model"，是"用对的 model"**。

下一章我们讲 routing — 怎么写一个轻量级 dispatcher 把任务分到不同的 model。
