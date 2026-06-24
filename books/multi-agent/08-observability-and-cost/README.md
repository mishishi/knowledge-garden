# 08. 可观测性与成本

> 上章讲了选框架。这章讲选完后怎么知道系统在干什么、烧了多少钱。这俩是生产环境最容易被忽视的隐形炸弹——我的 4 个 multi-agent 项目都吃过 observability 不到位的亏。

## 可观测性的三大支柱

任何 production multi-agent 系统都要有这 3 块：

**Trace（链路追踪）**——一次请求从进入到结束，每一步做了什么、花了多少时间、消耗多少 token。一次失败的 5-Agent 任务，不看 trace 根本不知道是哪个 Agent 出的问题。

**Metric（指标）**——聚合统计：每分钟调用次数、平均耗时、错误率、P95 延迟。Metric 是 dashboard 和 alert 的基础。

**Log（日志）**——详细记录：每次 LLM 调用的输入输出、每次工具调用的参数和结果。Log 比 trace 更细，trace 是结构化数据、log 是 free-form 文本。

3 块的关系：trace 告诉你「一次任务发生了什么」、metric 告诉你「整体系统怎么样」、log 告诉你「具体细节是什么」。3 块都要，缺一不可。

## Trace 数据结构

一次完整的 multi-agent 任务是嵌套的 span 树：

```
Trace（一次完整请求）
├── Span 1（Agent A 调用 LLM）
│   ├── 输入: prompt + tools
│   ├── 输出: response
│   ├── 耗时: 1.2s
│   └── tokens: 1500 input + 200 output
├── Span 2（Agent A 调用工具 get_weather）
│   ├── 输入: city="Tokyo"
│   ├── 输出: "22°C"
│   └── 耗时: 0.3s
└── Span 3（Agent B 调用 LLM）
    ├── 输入: prompt + 上一轮结果
    ├── 输出: response
    └── ...
```

每个 span 必须记录：开始时间、结束时间、输入摘要（不是全文，太长）、输出摘要、token 数、cost。如果记完整 prompt 内容会爆 disk——只记 hash + 前 200 字符。

我自己的 multi-agent 项目第 1 周没 trace 数据，3 个 user 投诉「任务卡死」，debug 时只能看 log 倒推——2 小时才找到 root cause（LLM 返回了空字符串导致下游解析失败）。加 trace 后，类似的 bug 5 分钟定位。

## LangSmith（最成熟的 multi-agent observability）

如果用 LangGraph / LangChain 生态，LangSmith 是 best choice。LangChain 官方产品，跟 LangChain 代码原生集成。

```python
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "lsv2_xxx"
os.environ["LANGCHAIN_PROJECT"] = "my-multi-agent"

from langgraph.graph import StateGraph
# ... 你的 LangGraph 代码
# 不用改代码，LangSmith 自动 trace 所有 LLM call + agent step
```

LangSmith dashboard 看：
- 每次任务完整 trace tree（哪个 agent 跑了什么）
- token / cost per span
- latency per step
- input / output diff

缺点：商业产品，免费额度有限（5000 traces/月），超量要付费；数据在 LangChain 自己的服务器（隐私敏感）。

## 自建 trace 系统

不想用商业产品可以自建。我自己的 hobby 项目用 PostgreSQL 存 trace：

```sql
CREATE TABLE traces (
    id UUID PRIMARY KEY,
    user_id TEXT,
    task TEXT,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    total_cost_usd NUMERIC,
    status TEXT  -- completed / failed / timeout
);

CREATE TABLE spans (
    id UUID PRIMARY KEY,
    trace_id UUID REFERENCES traces(id),
    parent_span_id UUID,
    step_index INT,
    type TEXT,  -- llm_call / tool_call / agent_step
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    input_hash TEXT,
    output_hash TEXT,
    input_preview TEXT,  -- 前 200 字符
    output_preview TEXT,
    cost_usd NUMERIC,
    metadata JSONB
);

CREATE INDEX ON traces (user_id, start_time DESC);
CREATE INDEX ON spans (trace_id, step_index);
CREATE INDEX ON traces USING GIN (metadata);
```

collector 50 行代码（参考 [Harness Engineering 06](../harness-engineering/06-observability/) 那章的 trajectory collector），异步写 DB 不阻塞 agent。

自建的好处：完全可控、数据自己掌握、零成本。坏处：UI 自己写（web dashboard 不是 1 天能做完）、scale 自己管。

我自己 side project 用自建 + 简单的 web dashboard（200 行 Flask），production multi-agent 用 LangSmith（团队 5 人用，免费额度够）。

## 成本监控

cost 是 multi-agent 的隐形炸弹。我自己跑过的 4 个项目都遇到过「单次任务成本超 $5」的事故。早期没监控，月账单出来才发现某 agent 一个月烧了 $800。

**cost dashboard 3 个 query**：

**每日 cost per user**：

```sql
SELECT DATE(start_time) AS day, user_id, SUM(total_cost_usd) AS daily_cost
FROM traces
WHERE start_time > NOW() - INTERVAL '30 days'
GROUP BY day, user_id
ORDER BY daily_cost DESC;
```

找出「哪些用户在烧钱」。我见过一个 user 一天 $200——他跑 deep research 任务，agent 反复调 search_web 抓大文档。

**cost by task type**：

```sql
SELECT metadata->>'task_type' AS task_type,
       AVG(total_cost_usd) AS avg_cost,
       PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_cost_usd) AS p95_cost
FROM traces
GROUP BY task_type;
```

找出「哪些任务类型最贵」。deep research 类型平均 $0.80，比普通 chat ($0.02) 贵 40 倍。

**failure cost**：

```sql
SELECT status, SUM(total_cost_usd) AS wasted_cost, COUNT(*)
FROM traces
WHERE start_time > NOW() - INTERVAL '7 days'
GROUP BY status;
```

「失败任务烧了多少钱」。我曾经一周 $30 浪费在失败任务上——harness 加 cost ceiling 后降到 $5。

**alert 阈值**：单用户单天 cost > $5、单 session cost > $1、failure cost > $10/天——这些 alert 在我自己的项目里都触发过，每次都救了一笔钱。

## 3 个 cost 优化杠杆

按 effort / impact 排序：

**杠杆 1：换小模型（最大杠杆）**

很多 multi-agent 任务用 Opus 跑没必要——研究 Crew 用 Haiku 够用、写作 Crew 用 Sonnet 平衡质量和成本、审稿 Crew 用 Haiku 又快又便宜。

我自己项目的优化：所有 agent 从 Sonnet → Haiku（研究和审稿）、写作从 Opus → Sonnet。月成本从 $800 降到 $320（-60%），质量评测 pass rate 从 81% 降到 78%（-3%）。ROI 极高。

**杠杆 2：减少 round 数**

multi-agent 任务平均 round 数跟 prompt 质量负相关。prompt 模糊 → agent 反复尝试 → round 数多 → cost 高。

我的优化：每个 agent 的 task description 加「最多 N 轮尝试就放弃」+ cost ceiling。round 中位数从 8 降到 5，cost -37%。

**杠杆 3：缓存重复 query**

同样 query 重复检索 100 次很常见——尤其是 RAG 任务。Redis cache 相同 query 直接返回，月成本降 20-30%。

我自己用 Redis + query hash 做 cache，命中 35% 左右。

3 个杠杆叠加：我自己的 production multi-agent 月成本从 $800 降到 $250（-69%），质量 pass rate 只掉 3%。

## 关键 metric 仪表盘

我盯的 5 个 metric：

| Metric | 阈值 | 告警 |
|---|---|---|
| 每分钟 trace 数 | > 1000 | 关注（rate limit 风险）|
| 平均 trace cost | > $0.10 | 关注 |
| 平均 trace 轮数 | > 10 | 关注（可能有死循环）|
| P95 trace latency | > 30s | 紧急（用户体验差）|
| Trace 失败率 | > 15% | 紧急 |

5 个 metric 在 Grafana / 自建 dashboard 都看。

## 上 production 前 checklist

- Trace 系统就绪（LangSmith 或自建）
- Cost dashboard 可查
- 3 个 alert 阈值设置（per user / per task / per session）
- 每个 session 有 cost ceiling（默认 $1）
- 每个 agent 有 max rounds 限制（默认 10）
- 失败有 retry 逻辑（指数退避 + max 3 次）
- Token 用量按 user 维度记录（账单和审计）
- 定期 review cost（每周看 cost dashboard）

[09. Code Review Project](../09-code-review-project/) 用一个完整项目（代码审查 multi-agent 系统）把前 8 章串起来——从需求到 production 部署。
