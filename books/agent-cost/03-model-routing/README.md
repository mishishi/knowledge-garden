# 03. Model routing 101

路由这个事，最朴素的想法是"贵的 model 强，便宜的 model 弱"。但实际生产里**任务的难度不是均匀分布的**。

我的 agent 跑了一个月之后我统计了一下 query 的实际复杂度：

- 62% — 单步问题（"今天北京天气"、"这个 bug 怎么修"）
- 28% — 多步但路径明确（"给我写个排序函数 + 测试"）
- 8% — 真正复杂（"对比这 3 个架构"）
- 2% — 边界 case（"为什么这个 prompt 输出跟我想要的不一样"）

但 100% 的 call 我都用了 GPT-4o。

把 62% 的单步问题换成 gpt-4o-mini，价格差 30 倍。**$400 月账单里至少 $240 是浪费的**。

## cascade 是最简单有效的路由

最朴素的 router 模式：先用便宜 model 试，结果不 confidence 再升级到强 model。

```python
def route(query):
    # 便宜 model 先试
    cheap_response = call("gpt-4o-mini", query, tools=tools)
    confidence = judge_confidence(cheap_response)

    if confidence > 0.7:
        return cheap_response
    else:
        # 升级到强 model
        return call("gpt-4o", query, tools=tools)
```

关键是 `judge_confidence` 怎么实现。三种主流做法：

**1. logprob 阈值** — 便宜 model 输出的 top token logprob 高 → confidence 高。这个最准但要 OpenAI 直接暴露 logprob，第三方 provider 不一定有。

**2. self-eval** — 让 model 自己说"我对这个回答的 confidence 是 X"。**这个不准**，模型普遍过度自信。

**3. pattern match** — 如果 tool call 出错、回答里有 "I'm not sure"、回答超过 N 字符没有 conclusion，视为低 confidence。规则简单粗暴但 80% 场景够用。

我的 agent 用的是 pattern match + 关键短语检测。准确率 70%，但**省钱**比**准确率提升**更值得，因为升级到 4o 是 fallback 不是常态。

实际跑下来：62% 的 query 走 mini，30% 升级到 4o，8% 升级到 4o + retry。**月账单从 $400 降到 $180**。

## self-consistency 适合低风险场景

另一种不依赖外部 router 的模式：让便宜 model 跑 N 次，投票取多数。

```python
def self_consistency(query, n=3):
    answers = [call("gpt-4o-mini", query) for _ in range(n)]
    return majority(answers)
```

3 次 mini = 3 × $0.15/1M input × ~2K token = $0.0009
1 次 4o = $2.5/1M input × ~2K token = $0.005

3 次 mini 仍然比 1 次 4o 便宜 5 倍。质量呢？mini 在分类、提取、简单生成上跟 4o 差距 < 5%，3 次投票后能追平甚至超过 4o。

这个 pattern 的**前提是 N 次可以并行**——如果你的 agent 是 streaming 用户实时等，那 3 次串行 = 3x latency 就不行。Batch job、preprocessing、shadow eval 这类场景合适。

## embedding 路由适合结构化任务

我那个 agent 70% 的 task 实际上是 5 类之一：QA / 提取 / 摘要 / 分类 / 工具编排。每类有最适合的 model。

- QA / 提取 / 分类 → 4o-mini 甚至 3.5-turbo-instruct 够用
- 摘要 → 4o-mini 跟 4o 差不多
- 工具编排 / 复杂 reasoning → 必须 4o

embedding 路由的代码很简单：

```python
TASK_CATEGORIES = {
    "qa": "gpt-4o-mini",
    "extraction": "gpt-4o-mini",
    "summary": "gpt-4o-mini",
    "classification": "gpt-4o-mini",
    "tool_orchestration": "gpt-4o",
}

def route_by_intent(query):
    intent = classify_intent(query)  # 一个便宜 model 分类
    return TASK_CATEGORIES[intent]
```

`classify_intent` 这一步只花 100 token。把它做成 3-shot 或者直接用 embedding + cosine similarity 做 KNN。**分类本身是分类任务，所以又回到便宜 model——递归省钱**。

## 什么时候别路由

不是所有场景都该路由。

**1. 实时交互 + 低 latency 要求**

如果你给用户 200ms 内响应，cascade 里"试 mini + 可能升级 4o"平均 latency 是 1.3 × mini latency + 0.3 × (4o latency - mini latency)。实际往往比纯 4o 还慢。

**2. 质量不可接受妥协的关键决策**

医疗、法律、金融、合同审查。错一次 cost 远大于省下的 token 钱。

**3. 任务难度分布均匀**

如果你的 query 都是高难度（复杂 reasoning），路由没意义——所有都进强 model。router 的价值在**任务难度方差大**的时候最大。

## 我现在的策略

跑了 8 个月，2 次大调整：

- v1 — 100% 4o，$400/月
- v2 — cascade mini → 4o，$180/月（45% 走 mini）
- v3 — embedding 路由 + cascade，$110/月（73% 走 mini）

下一步是加 reasoning model（o1 mini 或 o3-mini）做规划层，4o 做执行层。预估再砍 30%。

下一章讲 caching。cascade 之后省下的钱还可能被重复 call 吃掉——同一段 prompt 一周内被发 1000 次，cache 直接打 5 折。
