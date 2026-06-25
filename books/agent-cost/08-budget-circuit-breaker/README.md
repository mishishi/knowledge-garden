# 08. 预算告警 + 熔断

quota 解决 per-user 的成本。circuit breaker 解决 **per-system** 的成本——整个 agent 失控时怎么办。

quota 是用户级 safeguard。circuit breaker 是 platform 级 safeguard。两者都要有。

## 失控是怎么发生的

我的 agent 第一次失控是个周末的凌晨。一个新上线的 RAG indexing 任务有 bug，凌晨 2 点开始每秒跑 5 次 LLM call，每次 $0.05。**2 小时烧掉 $1800**。我周一早上醒来看到 Stripe 邮件 "$1800 in charges from OpenAI"。

事后看 log：周六晚上 11:50 我上线了 v2 indexing（"优化 RAG 检索质量"），凌晨 2 点开始触发 retry loop（一个失败的 retrieval 触发 5 次重试）。我周末没看监控。

quota 在 per-user 维度能拦住单个用户的 cost，**拦不住平台级故障**。我需要 system 维度。

## 3 个 budget 层

**Layer 1 — Daily soft budget**（每日软上限）

```
daily_budget = $50
如果当日 total spend > $40 (80%): 发告警给我 + Slack/email
如果 > $50 (100%): 自动 degrade (切到 mini)
如果 > $75 (150%): 熔断，全站 stop
```

**Layer 2 — Monthly hard budget**（每月硬上限）

```
monthly_budget = $1000
如果 > $700: 降级（所有 call 切 mini，新功能不开放）
如果 > $900: 熔断，只允许 free tier
如果 > $1000: 全站 stop，all users get "monthly budget exceeded" 提示
```

**Layer 3 — Per-call spike detection**（异常检测）

如果单个 call 成本 > 历史 P99 的 3x，立刻告警。**这种是 bug 信号**——一个 call 不应该突然变贵 3 倍。

## 实时告警

每 5 分钟跑一次 check，比"月度账单出来才看"早 28 天。

```python
def check_budgets():
    today_cost = sum_costs_since_midnight()
    month_cost = sum_costs_this_month()

    # Layer 1: Daily
    if today_cost > 0.8 * DAILY_BUDGET:
        alert(f"Daily spend ${today_cost:.2f} / ${DAILY_BUDGET} (80%)")
    if today_cost > DAILY_BUDGET:
        degrade_to_mini()  # 切到 gpt-4o-mini 全局
        alert(f"DEGRADED: daily budget ${DAILY_BUDGET} exceeded")
    if today_cost > 1.5 * DAILY_BUDGET:
        circuit_breaker_trip("daily 150% exceeded")
        alert(f"TRIPPED: ${today_cost:.2f} / ${DAILY_BUDGET}")

    # Layer 2: Monthly
    if month_cost > 0.7 * MONTHLY_BUDGET:
        alert(f"Monthly spend ${month_cost:.2f} / ${MONTHLY_BUDGET} (70%)")

    # Layer 3: Spike
    recent_costs = get_costs_last_5min()
    p99 = percentile(recent_costs, 99)
    latest = recent_costs[-1]
    if latest > 3 * p99 and latest > $0.5:
        alert(f"SPIKE: single call ${latest:.2f} (3x p99)")
```

`degrade_to_mini()` 是渐进降级——不是直接停服务，而是把模型换成便宜的 mini，质量降但功能还在。**用户体验比"突然打不开"好太多**。

`circuit_breaker_trip()` 是真熔断。trip 之后所有 call 直接返回 503 / 提示"系统临时维护"，直到我手动 reset。

## Circuit breaker 的状态机

3 个状态：

```python
class CircuitBreaker:
    def __init__(self):
        self.state = "closed"  # closed=正常, open=熔断, half_open=试探

    def call(self, fn):
        if self.state == "open":
            raise CircuitOpen("service temporarily unavailable")

        try:
            result = fn()
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise

    def record_failure(self):
        if self.failures_in_window > THRESHOLD:
            self.state = "open"
            self.open_until = time.time() + COOLDOWN_SEC

    def record_success(self):
        self.failures = 0
        if self.state == "half_open":
            self.state = "closed"  # 恢复
```

`half_open` 状态：冷却期后允许少量请求通过试探，成功就恢复 `closed`，失败就回 `open`。

我用的 cooldown 是 30 分钟。trip 后 30 分钟自动半开，1 个请求试探——成功恢复，失败再 30 分钟。

## 渐进降级比熔断更常用

实际跑下来我 90% 的 incident 用的是渐进降级，不是熔断。

降级策略分 3 档：

**档 1 — 切 mini** (默认触发)
所有 4o call 换成 mini。新功能照常上。质量评估 -3% 用户基本无感。

**档 2 — 关闭非核心 feature**
比如关掉 agent 主动建议、关掉自动 summarization、关掉 background indexing。**保留**主对话能力。这是降本的主力。

**档 3 — 限速**
所有用户每分钟最多 5 call。用户体验下降但还能用。

**档 4 — 熔断**（最后手段）
全停。**只在 manual intervention 之前用**。

```python
DEGRADATION_LEVELS = {
    1: "switch_to_mini",
    2: "disable_optional_features",
    3: "rate_limit",
    4: "circuit_breaker_open",
}

def apply_degradation(level, reason):
    if level >= 1:
        global_model_override = "gpt-4o-mini"
    if level >= 2:
        disable_features(["proactive_suggestions", "background_indexing"])
    if level >= 3:
        apply_rate_limit(5, per_minute=True)
    if level >= 4:
        circuit_breaker.trip(reason)
    log_degradation(level, reason)
```

## 那个 $1800 的事后复盘

我现在的 guard rail（事后补的）：

1. **每个 retry loop 加 max_retries=3**（之前的 bug 是无限重试）
2. **每个 RAG task 加 cost ceiling**（task 超过 $5 自动 stop）
3. **每 5 分钟跑 budget check**（之前是 daily）
4. **周末班告警**（之前周末不发，凌晨事故没人管）
5. **P99 spike detection**（一个 call 突然贵 3x 立刻告警）

补完 5 项之后**单次最大事故是 $40**（一次 eval 任务有 bug 跑了 4 小时）。从 $1800 降到 $40，是 45x 改善。

最关键的 lesson：**circuit breaker 不只是工程问题，是 ops 纪律**。你不写 hard cap、不挂告警、不真熔断，下次失控就是下次失控。

下一章讲工具调用省钱——前面都是 prompt/model 层，工具调用（function call、browser use、shell）是另一类成本中心。
