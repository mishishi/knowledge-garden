# 07. 用户粒度 quota

前面 6 章都在讲"我"的成本——怎么让 LLM call 更便宜。这一章讲**怎么让别人怎么用我的 agent**。

agent 类产品跟传统 SaaS 不一样的点：**单个用户的成本是变量不是常量**。我之前定价 $9/月，假设用户每天用 10 次 = $0.03/次 × 30 = $0.9/月成本，毛利 90%。

但用户 A 每天用 100 次，附加大文档输入，成本 $9/月。我从他身上**一分不赚**。更糟的是用户 B 把整个项目代码粘进来 debug，单次 cost $2，触发 1 次毛利 -$1.9。

我那 $400 月账单的 8% 来自这种"超级用户"。

## 第一步：先知道每个用户花了多少

这个数字你心里得有。我之前是粗估——"100 用户 × 假设 10 次/天 × $0.005 = $50"。**实际差距 8 倍**。

实施：

```sql
-- 用 BigQuery / Postgres / DuckDB 都行
SELECT
  user_id,
  COUNT(*) as call_count,
  SUM(input_tokens) as total_input,
  SUM(output_tokens) as total_output,
  SUM(cost) as total_cost
FROM llm_logs
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY user_id
ORDER BY total_cost DESC
LIMIT 20;
```

跑完你会发现 80/20 法则在 agent 上更极端：**20% 的用户贡献 80% 的成本**。这 20% 一定要管。

## 第二步：per-user soft cap

不要直接 hard cap。hard cap 让用户撞墙的瞬间就流失了。soft cap 是"到额度了给警告"+"可临时超额"。

```python
USER_QUOTAS = {
    "free": {"daily_calls": 50, "monthly_tokens": 500_000},
    "pro": {"daily_calls": 500, "monthly_tokens": 5_000_000},
    "team": {"daily_calls": 5000, "monthly_tokens": 50_000_000},
}

def check_quota(user, call_estimate):
    usage = get_user_usage_today(user)
    quota = USER_QUOTAS[user.tier]

    if usage.calls >= quota["daily_calls"]:
        raise QuotaExceeded("daily calls exceeded, upgrade?")

    if usage.tokens + call_estimate > quota["monthly_tokens"]:
        # 不直接 block, 而是 warn + soft cap
        if usage.tokens + call_estimate > quota["monthly_tokens"] * 1.2:
            raise QuotaExceeded("monthly tokens exceeded")
        return "warning"  # 让 call 跑但记 warning

    return "ok"
```

**关键**：超 20% 还能跑但给用户一个明显的"你快用完了"提示。多数用户看到这个会自己克制。少数继续超的——是付费 tier 候选。

## 第三步：per-user hard cap + 计费

pro 用户用超 1.2x 还是超了怎么办。两条路：

**A. 涨价** — 通知用户"你本月已用 X，超过 $X 含量的部分按 $0.01/1K token 收费"

**B. 限速** — 限流到 1 call/min。用户体验差但能跑。

**A 比 B 好**。用户自己选要不要花钱。限速是被动损失信任。

我用的是混合：pro 用户超 1.2x 自动按 token 计费（overage billing），team 用户用 enterprise 价格包月。具体看 Stripe metered billing——它原生支持按用量计费。

```python
def track_and_bill(user, call_cost):
    usage = get_user_usage_this_month(user)
    quota = USER_QUOTAS[user.tier]
    overage = max(0, usage.cost - quota["included_cost"])

    if overage > 0:
        stripe.billing.create_usage_record(
            customer=user.stripe_id,
            quantity=call_cost,
            action="increment",
        )
```

## 第四步：成本底线 = 价格底线

定价时反推：

```
目标毛利 70%
单用户单月成本上限 = ARPU × 0.3

$9/月 ARPU → 单用户成本上限 $2.7/月
$29/月 ARPU → 单用户成本上限 $8.7/月
$99/月 ARPU → 单用户成本上限 $29.7/月
```

然后算"这个 ARPU 能让用户用多少次"：

```
$2.7 / $0.005 per call (avg) = 540 call/月 = 18 call/天
```

如果你的 agent 主要是文档处理，1 次 call 平均 $0.05（长 context），那 $2.7 只够 54 call/月 = 2 call/天。**你定的价格 + 你的平均 call 成本决定了用户每天能用几次**。

我重新算过之后发现 $9/月定价只够支持 2 call/天——这跟用户实际行为差距巨大（用户期望至少 10 call/天）。要么涨价到 $29，要么把 avg cost 砍到 $0.01。前者涨 3 倍容易丢用户，后者需要 cascade + cache 全部上线。

## 第五步：超级用户 = 升级机会

不要把超级用户当问题。**他们是你最值钱的客户**。

10 个超级用户（每天 100 call）成本 $90/月。如果定价 $29/月，他们付 $290/月，毛利 $200。**比 30 个普通用户（每天 10 call × 30 人 = 300 call/月 × $0.005 = $1.5/月成本 × 30 = $45，付 $9 × 30 = $270）更值钱**。

我现在的策略：

- 免费用户：50 call/天，超了切 mini
- pro 用户：500 call/天，超了按 token 计费
- team 用户：5000 call/天，限速 + 主动联系
- enterprise：定制 + 私有部署

不是一刀切。**让每个 tier 都有清晰的成本边界 + 超出后清楚的升级路径**。

## 实操：上线 quota 的 3 步

**第 1 周** — 加 usage tracking。**只看不挡**。所有 call 都记下来，让用户能看到自己的用量（"你今天用了 X call / Y token"）。这一步不动业务，只观察。

**第 2-3 周** — 加 soft warning。当用户超 80% 时开始弹 warning（不阻断）。看 80% 用户怎么反应——是自觉克制还是无视。

**第 4 周+** — 加 hard cap。超 120% 阻断或自动计费。**一定要在用户有心理预期之后再 hard cap**。

我见过最蠢的产品是上线第 1 天就 hard cap——用户没有 usage 数据，被挡完全不知道为什么。

下一章讲 budget circuit breaker——quota 是 per-user 的，circuit breaker 是 per-system 的，是"整个 agent 该停了"的安全阀。
