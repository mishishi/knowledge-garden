# 10. Cost dashboard 自建

最后一章。

前面 9 章都讲了具体的优化技巧，但**没有 dashboard 你看不到效果**。我最早是每月看一次 OpenAI 账单——这等于"开车不仪表盘，下车看油表"。

我现在每天看 3 个数字。每个数字对应一个 action。

## 必看的 3 个数字

**1. 今日 cost vs budget**
- 数字：当日 LLM cost（real + batch）
- 阈值：>$40 yellow，>$50 orange，>$75 red
- action：yellow 看一眼，orange 切 mini，red 熔断

**2. cost per success (rolling 7d)**
- 数字：过去 7 天 cost / 成功 task 数
- 阈值：>2 倍 baseline 告警
- action：检查 routing、cache、prompt 改动

**3. top 5 user by cost (this week)**
- 数字：本周前 5 名用户 cost
- 阈值：超过本月预算 30% 的用户 yellow
- action：联系用户是否升级 / 是否异常

这 3 个数字不能漏。**漏掉任何一个都会在某个凌晨被告警叫醒**。

## Dashboard 的最小自建栈

我前后用过 3 个方案，按成本排序：

**方案 1 — Langfuse（自托管）** $0/月
- 开源 LLM observability 平台
- 自带 cost tracking、tracing、prompt management
- 需要 Docker 部署一个 container
- 完整 dashboard，UI 直接用
- 缺点：自托管要维护

**方案 2 — Helicone（云）** $0 - $20/月
- LLM proxy，自动记录每次 call
- Cloud 版本免费 100K events/月
- 自带 cost dashboard
- 缺点：第三方服务，要信任；数据出境

**方案 3 — 自己写 + Grafana** $0/月（但要花时间）
- 把 LLM log 发到 Postgres
- Grafana 接 Postgres 写 SQL dashboard
- 完全可控，schema 你定
- 缺点：要写 SQL 和 dashboard 面板，初始成本 1-2 天

**方案 4 — 直接 OpenAI dashboard** $0/月
- 用 OpenAI 自己的 Usage dashboard
- 缺点：延迟 24 小时 + 没 user 维度 + 没 cache 命中

我用的是**方案 1**（Langfuse 自托管）。一次部署，长期省心。Helicone 也行，如果你不想自己维护 infra。

如果你连 Langfuse 都不想部署，**方案 4 + 一个简单的 Postgres query** 也能凑合用。但 24 小时延迟意味着你看到超支时已经亏了一天。

## 自建 dashboard 的最小 schema

如果你决定自己写（方案 3），Postgres schema 长这样：

```sql
CREATE TABLE llm_calls (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model TEXT NOT NULL,
    call_type TEXT,  -- 'realtime' | 'batch'
    input_tokens INT NOT NULL,
    output_tokens INT NOT NULL,
    cached_input_tokens INT DEFAULT 0,
    cost NUMERIC(10, 6) NOT NULL,  -- USD
    task_type TEXT,  -- 'qa' | 'extraction' | 'tool_orchestration' | ...
    success BOOLEAN,
    duration_ms INT,
    metadata JSONB
);

CREATE INDEX idx_llm_user_time ON llm_calls (user_id, timestamp);
CREATE INDEX idx_llm_timestamp ON llm_calls (timestamp);
```

**3 个查询就是我的 dashboard**：

```sql
-- 1. 今日 cost vs budget
SELECT
  SUM(cost) AS today_cost,
  COUNT(*) AS call_count,
  COUNT(DISTINCT user_id) AS active_users
FROM llm_calls
WHERE timestamp > CURRENT_DATE;

-- 2. cost per success (7d)
SELECT
  SUM(cost) / NULLIF(COUNT(*) FILTER (WHERE success), 0) AS cost_per_success
FROM llm_calls
WHERE timestamp > NOW() - INTERVAL '7 days';

-- 3. top 5 user by cost
SELECT
  user_id,
  SUM(cost) AS user_cost,
  COUNT(*) AS call_count
FROM llm_calls
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY user_id
ORDER BY user_cost DESC
LIMIT 5;
```

把这 3 个查询扔到 Grafana 配 3 个 panel，加 5 分钟自动 refresh——这就是你的 dashboard。

## 必加的告警

dashboard 给你看过去。告警告诉你现在出事。我挂了 4 个告警：

```python
def check_alerts():
    today = daily_cost()
    week_p99 = percentile(weekly_costs(), 99)
    latest = latest_call_cost()

    # 1. 今日 > 80% budget
    if today > 0.8 * DAILY_BUDGET:
        send_alert("today_cost_80pct", today)

    # 2. 今日 > 100% budget → 切 mini
    if today > DAILY_BUDGET:
        send_alert("today_cost_100pct", today)
        apply_degradation(level=1)

    # 3. P99 spike > 3x
    if latest > 3 * week_p99 and latest > 0.5:
        send_alert("spike_detected", latest)

    # 4. 任何 user 单日 > $20
    for user_cost in top_user_costs_today():
        if user_cost > 20:
            send_alert("user_over_20", user_cost)
```

`send_alert` 走 Slack webhook（#agent-alerts 频道）+ email 双重。我有 3 次因为 Slack 没及时看，靠 email 才发现。

## 仪表盘升级路径

我跑 8 个月的 dashboard 进化：

**v1 — 0 仪表盘**（第一个月）
- 每月看 OpenAI 账单
- 第一次 $400 看到时已经晚了
- 教训：**"我以为"是最大敌人**

**v2 — Postgres + SQL 手查**（第 2-3 月）
- 写 3 个 query 跑 30 秒看一次
- 每天花 5 分钟
- 找到 $400 的根因：3 个客服用户用得多

**v3 — Grafana 实时**（第 4-5 月）
- 5 分钟 auto refresh
- 看到 P99 spike 立刻发现 retry bug
- 月账单降到 $110

**v4 — 加 Langfuse**（第 6 月+）
- tracing + cost + prompt 改动关联
- 改 prompt 前能看 eval 分数
- 改 prompt 后能看 cost 变化

**v5 — 加告警 + circuit breaker**（第 7 月+）
- 5 个告警 + 3 档降级
- 周末也工作
- 第二次差点失控 $40 就被拦下

## 怎么从 0 开始

如果你现在 dashboard 是 0：

**第 1 步** — 加 logging。**所有 LLM call 都记 user_id / timestamp / model / cost**。先记不发愁。1 行代码。

**第 2 步** — 写 3 个 SQL query（上面的 1/2/3）。每周跑一次。

**第 3 步** — 接 Grafana 或自建 HTML dashboard。1 天工作。

**第 4 步** — 加 4 个告警。半天工作。

**第 5 步** — 把 4 个告警接到降级 / 熔断。1 天工作。

总计 3-4 天投入，回本是第 1 次失控发生的时候。**我的 $1800 就是没做这套的学费**。

## 这个系列到此为止

10 章下来，省钱的核心 insight：

1. **算 unit economics** — cost per success 是单位，不是 cost per call
2. **routing 比 model 选型重要** — 任务难度方差大，dispatcher 比单 model 强
3. **caching 是 ROI 最高** — prefix cache 0 行代码就有 60% 命中
4. **batch 是被低估的杠杆** — 后台 30% 工作量拿 50% 折扣
5. **quota + circuit breaker 是 ops 纪律** — 不写就等失控

整个 series 的精神就一句话：**算得清才活得久**。

下一本书想写什么我还没定。但这个 site 上 5 个系列已经够读半年了，先消化再说。

—— 写于 2026 春，账单从 $400 降到 $90 那天
