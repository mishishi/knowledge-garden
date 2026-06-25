# 09. Token 成本与性能调优

我 2025 年 11 月第一次看 Claude Code 月账单：**$340**。**一个月**。

我以为是正常使用，但 2026 年 4 月我优化后——**同样工作量，月账单 $85**。**节省 75%**。

这一章讲 Claude Code 的成本结构和 5 个最有效的优化。

## Claude Code 的成本结构

**3 个主要成本**：

**1. 模型调用（最大头）**

```text
Opus 4:   $15/M input  +  $75/M output
Sonnet 4: $3/M input   +  $15/M output
Haiku 4:  $0.25/M input +  $1.25/M output
```

**2026 年 4 月价格**。

**月账单计算（重度用户）**：

```text
每月调用：500 次
平均 input：30K token
平均 output：5K token

Sonnet 全月：
input  = 500 × 30K = 15M token × $3/M = $45
output = 500 × 5K = 2.5M token × $15/M = $37.5
合计 ≈ $82
```

**Opus 全月（同用量）**：

```text
input  = 15M × $15/M = $225
output = 2.5M × $75/M = $187.5
合计 ≈ $412
```

**Opus 比 Sonnet 贵 5 倍**——**别用 Opus 干日常活**。

**2. Skills 加载成本**

```text
每个 Skill：~100 token/次启动
10 个 Skills × 500 次启动 = 5000 token × $3/M = $0.015
```

**几乎免费**。

**3. MCP 工具成本**

```text
每个 MCP Server：~18K token/轮
5 个 MCP Server × 50 轮/天 × 30 天 = 7500K = 7.5M token
7.5M × $3/M = $22.5
```

**MCP 是隐性成本**——**用户没注意但烧钱**。

## 我自己 2025 年 11 月 vs 2026 年 4 月对比

- 月调用次数：800 → 500（-38%）
- 主模型：Opus 全程 → Sonnet + Opus 混用（换模型）
- MCP Server：8 个常驻 → 5 个常驻（减 3）
- Skills：5 个 → 8 个（加 3）
- 月费：$340 → $85（-75%）

**3 个优化**：
1. **换模型**：Opus → Sonnet 80% / Opus 20%
2. **减 MCP**：8 → 5
3. **少用 Opus**：复杂架构用，日常用 Sonnet

## 优化 1：模型路由

**3 个模型怎么选**：

| 任务 | 推荐模型 | 价格 | 节省 |
|---|---|---|---|
| 写代码、debug、review | Sonnet | $3-15/M | 基准 |
| 复杂架构设计 | Opus | $15-75/M | -5x |
| 格式整理、简单对话 | Haiku | $0.25-1.25/M | -10x |

**实战模型路由规则**（我自己）：

```text
80% 任务：Sonnet
15% 任务：Opus（架构、复杂重构）
5% 任务：Haiku（文档、简单 review）
```

**Opus 5 倍贵 = 必须有"必要性"才用**。

**Haiku 1/12 价 = "能用 Haiku 就不上 Sonnet"**。

## 优化 2：MCP 数量控制

**5 个 MCP Server 占用 90K token/轮**——**每天 50 轮 = 4.5M token = $13.5/天**。

**优化方法**：

**Step 1：用 `/mcp` 动态启停**

```bash
/mcp
> list
> enable postgres
> disable sentry  # 暂时不用
```

**Step 2：按 session 启停**

```bash
# 写代码 session
> enable filesystem, github

# debug session
> enable sentry, postgres

# CI/CD session
> enable docker
```

**Step 3：按需连接**

```bash
# 不用每次都连
claude mcp remove sentry  # 删掉不常用的
claude mcp add sentry ... # 临时加
```

**效果**：MCP token 消耗从 4.5M/天 → 1M/天。**节省 78%**。

## 优化 3：Context 优化

**Context 占用 = 直接成本**。**1M token input = $3-15**。

**4 个优化**：

**1. 定期 /clear**

长对话 context 累积。**每 30 分钟 `/clear` 重置**。

**2. 用 /compact 智能压缩**

```bash
# 保留关键架构决策 + 文件路径 + 错误信息
/compact preserve all architecture decisions, file paths mentioned, and error messages
```

**3. Skills 按需加载**

15 个 Skills × 100 token = 1500 token 启动。**但每次只用 1-2 个 Skill**。

**问题**：所有 Skills 都在候选 list 里。

**解法**：**手动控制**——用 `/skill-name` 手动触发。**而不是靠自动匹配**。

**4. 减少 MCP 工具轮次**

MCP 工具调用每轮 18K token。**减少工具调用次数**：

- **批量调用**：1 次调用做 5 件事（而不是 5 次调用）
- **缓存结果**：常用结果 cache 起来
- **避免重复查询**：不要反复查同一信息

## 优化 4：会话策略

**3 个会话策略**：

**1. 短 session**

```text
长 session（3 小时）= context 满
短 session（30 分钟）= context 清晰
```

**用 `/clear` 分隔任务**：

```bash
# Session 1：写后端 API
claude
[写 API]
/clear

# Session 2：写前端 UI
claude
[写 UI]
/clear
```

**2. 专门 session**

不同任务用不同 session：

```bash
# 写代码 session（不用 MCP）
claude --mcp-disable

# Debug session（用 sentry）
claude --mcp sentry
```

**3. 团队 session**

```text
每个工程师独立 session
避免 1 个 session 多工程师串台
```

## 优化 5：模型切换时机

**什么时候用 Opus**：

- 复杂架构设计（多文件、多模块）
- 关键 bug（生产事故）
- 重构大型代码库
- 写文档（要求高）

**什么时候用 Sonnet**（默认）：

- 写新功能
- code review
- 写测试
- debug 一般问题

**什么时候用 Haiku**：

- 简单格式整理
- 文档总结
- 简单问答
- 1-2 句话的修改

**实际比例**（我自己 2026 年 4 月）：

```text
Sonnet：80%
Opus：15%
Haiku：5%
```

**Opus 5 倍贵**——**只有 15% 任务真的需要 Opus**。

## 优化 6：节省 75% 的 5 步流程

**Step 1：审计**

```bash
# 看 Claude Code 月账单
claude usage --month
```

**Step 2：找大头**

```bash
# 哪些任务最贵？
# 哪些 MCP Server 占 token 多？
claude usage --by-task
claude usage --by-mcp
```

**Step 3：换模型**

把所有"日常任务"从 Opus 换 Sonnet。**节省 60%**。

**Step 4：减 MCP**

只留 5 个最常用的 MCP。**节省 20%**。

**Step 5：日常优化**

- 每 30 分钟 `/clear`
- 简单任务用 Haiku
- 不需要的 Skill 移除

**节省 5-10%**。

**5 步总计节省 75-85%**。

## 性能优化（速度）

**不只是钱，还有速度**。

**1. 短 context 更快**

```text
context 10K token：响应 2 秒
context 100K token：响应 8 秒
context 200K token：响应 20 秒
```

**短 context = 快 + 准 + 便宜**。

**2. 模型切换速度**

```bash
/model sonnet  # 切换快
/model opus    # 切换也快
```

**3. 并行 SubAgent**

3 个 SubAgent 并行 = **3 倍速度**（详见 ch05）。

## 性能 vs 成本的平衡

**不是"越便宜越好"——**也不是"越快越好"**。

**4 个象限**：

```text
          便宜
           |
    Haiku  |  Sonnet
   + Skills|  + Skills
   + 短 sess| + 中 sess
           |
-----------+---------- 快
           |
    Opus   |  Opus
   + 短 sess| + 长 sess
   + 少 MCP|  + 多 MCP
           |
          贵
```

**实战选择**：
- **日常 80%**：Sonnet + 短 session + 5 MCP（**右上象限**）
- **复杂 15%**：Opus + 中 session + 5 MCP（**右下象限**）
- **简单 5%**：Haiku + 短 session（**左上象限**）

## 3 个常见优化错误

**错 1：完全用 Opus 追求"最好"**

```text
# 错：所有任务用 Opus
月费 $400
```

**改**：**Sonnet 80% + Opus 20%**。**月费 $85**。**效果差异 5-10%**。

**错 2：MCP Server 一直挂着**

```text
# 错：8 个 MCP Server 一直启用
每天 90K token MCP 开销
```

**改**：**5 个常驻 + 按需启停**。

**错 3：不 /clear 长 session**

```text
# 错：3 小时 session 不 clear
context 满 → 慢 + 贵 + 准
```

**改**：**每 30-60 分钟 `/clear` 或 `/compact`**。

## 我自己 2026 年 4 月的"成本清单"

```text
Sonnet 80% × 500 次 = $65
Opus 15% × 75 次 = $15
Haiku 5% × 25 次 = $1
MCP 工具 = $4
合计 ≈ $85
```

**每天 $3**。**每 token 平均 $0.0002**。

**对比 2025 年 11 月 $340 = 节省 75%**。

## 真实数字：优化前后

**5 个指标同时改善：**

- 月费：$340 → $85（-75%）
- 平均响应时间：8 秒 → 3 秒（-63%）
- 触发准确率：78% → 92%（+18%）
- Skills 数量：5 → 8（+60%）
- MCP 数量：8 → 5（-38%）

**5 个指标同时改善**。**这是"优化"的力量**。

**5 个指标同时改善**。**这是"优化"的力量**。

## 5 个未来趋势

**1. 定价下降**

2026 年下半年模型定价继续下降——**Opus 5 倍价差会缩窄到 2-3 倍**。

**2. Context caching**

```bash
# 系统级 cache 常用 context
claude cache set "我项目的所有 doc" 5MB
```

**节省 50%+ token**。

**3. 智能模型路由**

Claude Code 2026 Q3 计划：自动判断任务复杂度 → 自动选模型。

**4. 更便宜的模型**

Haiku 替代品——**2026 年下半年会出现**"Haiku Opus"（介于两者之间，3-4 倍便宜但接近 Opus 质量）。

**5. 量化 / 订阅模式**

2026 年可能推出"Claude Code 订阅"——**月费 $20-50 不限用量**。**类似 GitHub Copilot**。

下一章讲局限 + 未来——**Claude Code 不是万能的，2026 年它和 Cursor/Codex/TRAE 怎么选**。
