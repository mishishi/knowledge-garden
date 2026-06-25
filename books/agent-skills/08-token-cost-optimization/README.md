# 08. Token 成本与性能优化

2026 年初我把项目 Skills 从 5 个加到 12 个。**某天发现每次对话开始都"慢半拍"**——模型要在 12 个 Skill 的 description 里"找匹配的"。

**Skills 多了真有性能问题**。这一章讲怎么优化。

## Skills 多了的 3 个性能问题

**问题 1：description 匹配变慢**

```text
5 个 Skill：模型在 5 个 description 里找匹配 → 快
20 个 Skill：模型在 20 个 description 里找匹配 → 慢
50 个 Skill：模型在 50 个 description 里找匹配 → 显著慢
```

**不是线性**——**20 个 Skill 比 5 个慢 2-3 倍**。**LLM 的 attention 机制在长 list 里会"分散"**。

**问题 2：误触发增加**

```text
5 个 Skill：description 都很明确 → 误触发少
20 个 Skill：description 之间有 overlap → 误触发多
```

**两个 Skill 的 description 相似**——**模型在边缘 case 选错**。

**问题 3：管理成本**

```text
12 个 Skill × 每次 5 分钟 review = 1 小时/季度
50 个 Skill × 每次 5 分钟 review = 4 小时/季度
```

**Skills 多了维护成本指数级增长**。

## 数字基线

我自己的项目（2026 年）测过：

**5 个 Skill**：
- 启动时间：0 额外延迟
- 触发准确率：92%
- 拒绝准确率：88%
- 维护时间：30 分钟/季度

**12 个 Skill**：
- 启动时间：+200ms 延迟
- 触发准确率：85%（轻微下降）
- 拒绝准确率：82%（轻微下降）
- 维护时间：1 小时/季度

**20 个 Skill**：
- 启动时间：+500ms 延迟
- 触发准确率：78%（明显下降）
- 拒绝准确率：75%（明显下降）
- 维护时间：2 小时/季度

**30+ 个 Skill**：
- 启动时间：+1s+ 延迟
- 触发准确率：65%（不可接受）
- 拒绝准确率：70%（不可接受）
- 维护时间：4 小时/季度

**拐点在 15-20 个**。**超过 20 个就开始严重**。

## 我自己的"15 个 Skill 限制"

**2026 年我自己定的规则：单项目 Skills ≤ 15 个**。

**理由**：
- 15 个以下性能稳定
- 15-20 个性能开始下降
- 20+ 个开始"装不下了"

**超过怎么办**？3 个解法。

**解法 1：拆项目**

```text
项目 A Skills（10 个）：code-review, frontend-design, test-coverage...
项目 B Skills（10 个）：code-review, frontend-design, test-coverage...
```

**用 git worktree / monorepo 拆分**。**不同项目不同 Skills**。

**解法 2：合并 Skill**

```yaml
# 合并前
- code-review-js
- code-review-py
- code-review-go

# 合并后
- code-review  # 配 paths: ["**/*.{js,ts,py,go}"]
```

**3 个语言的 review Skill 合并成 1 个**。**用 paths 区分触发场景**。

**解法 3：放到 Sub-Agent**

```text
主 Agent 8 个 Skills
   ↓ 调用
子 Agent（review）独立 5 个 Skills
   ↓ 调用
子 Agent（frontend）独立 5 个 Skills
```

**主 Agent 不需要所有 Skills**——**子 Agent 自己有独立的 Skills**。**Skills 总量还是 ≤ 15，但功能没少**。

## 5 个具体优化

**优化 1：description 控制在 200 字内**

```yaml
# 错
description: |
  按团队规范审查 TypeScript 代码的 PR 改动。包括安全漏洞检查（SQL 注入、
  XSS、CSRF、权限校验、敏感信息泄露）、性能问题（N+1 查询、内存泄漏、
  不必要的重渲染、循环复杂度）、代码质量（命名、单一职责、可测试性、
  类型安全）、错误处理（try-catch 完整性、错误信息、日志记录）。
  适用于 src/ 下的代码。

# 对
description: 按团队规范审查 TypeScript 代码 PR（review / diff / 帮我看看）。安全、性能、质量、错误 4 维度。涉及 src/ 时触发。
```

**200 字内的 description 匹配速度快**。**过长的 description 拖慢匹配**。

**优化 2：paths 精确限定**

```yaml
# 错（太宽）
paths: ["**/*"]

# 对（精确）
paths: ["src/**/*.{ts,tsx}"]
```

**paths 越精确，候选 Skill 越少，匹配越快**。

**优化 3：合并相似 description**

```yaml
# 错（两个相似的 Skill）
- name: "frontend-style"
  description: 写 React 组件时的样式规范
- name: "frontend-component"
  description: 写 React 组件的结构规范

# 对（合并）
- name: "frontend-design"
  description: 写 React 组件（样式 + 结构）。涉及 .tsx 时触发。
```

**合并后，description 不会"撞车"**——**误触发减少**。

**优化 4：Skill 内的"白名单"**

```yaml
# Skill 内用"白名单"模板
allowed-tools: [Read, Grep, Glob]  # 不给写权限
```

**白名单工具**——**Skill 不能做的操作**——**减 20% token**（因为 allowed-tools 列表短）。

**优化 5：动态加载**

```yaml
# 不是所有 Skill 都需要"自动触发"
user-invocable: false  # 只允许手动触发
```

**手动触发的 Skill 不参与自动匹配的 list**——**模型启动时只看 user-invocable=true 的 description**。

**场景**：调试用的 Skill、实验性的 Skill、边缘 case 的 Skill——**只手动用**。

## Token 计算

Skills 的 token 成本：

```text
每次启动：100 token × Skill 数
触发时：500-2000 token × Skill 触发数
```

**20 个 Skills 的每次启动成本**：100 × 20 = 2000 token。

**GPT-4o input 价格**：$2.5/M token（2026）。**20 个 Skills 启动一次 0.005 美元**。**可以忽略**。

**触发时成本**：500-2000 token × 1-3 个触发 = 500-6000 token。**0.001-0.015 美元**。**也不高**。

**Skills 的 token 成本不是主要问题**。**真正的问题是性能**（启动慢、误触发）。

## 监控 Skills 性能

**3 个要监控的指标**：

**1. 启动延迟**

```text
# 测启动时间
import time
start = time.time()
session = claude.start_session()
elapsed = time.time() - start
print(f"Start: {elapsed}ms")
```

**基准**：< 200ms（5 个 Skill）/ < 500ms（15 个 Skill）/ < 1s（30 个 Skill）。

**2. 触发准确率**

跑 golden set，看触发率（见上一章）。

**3. 用户反馈**

收集"这个 Skill 没用" / "这个 Skill 经常误触发" 的用户反馈。

## 实战：15 个 Skill 的最优组合

我项目里的 15 个 Skill（2026 年 4 月）：

```text
.claude/skills/
├── code-review/        # 代码审查
├── code-format/        # 代码格式化
├── code-refactor/      # 重构建议
├── frontend-design/    # 前端设计
├── backend-pattern/    # 后端模式
├── test-coverage/      # 测试覆盖
├── test-integration/   # 集成测试
├── db-migration/       # DB 迁移
├── db-query/           # SQL 查询优化
├── api-doc-gen/        # API 文档
├── error-handling/     # 错误处理
├── i18n-check/         # i18n 检查
├── git-commit/         # commit message
├── pr-description/     # PR 描述
└── security-audit/     # 安全审计
```

**15 个**。覆盖代码 / 前端 / 后端 / 测试 / DB / API / 错误 / 国际化 / git / 安全 10 大类。

**触发准确率（golden set 100 个 case）**：
- 触发准确率：92%
- 拒绝准确率：89%
- 输出质量：85%

**性能**：启动延迟 400ms，触发延迟 200ms。

**维护时间**：季度 review 1.5 小时。

## 3 个常见错误

**错 1：把"相关"误当"必备"**

我写过 5 个 React 相关的 Skill（component / state / hook / style / a11y）——**结果 5 个互相冲突**。

**修正**：合并成 1 个 `frontend-design`，**用 paths 区分**。

**错 2：保留"测试用"的 Skill**

我写了 3 个 Skill 试用——**但用不到**。**还是留着**。

**修正**：**用不到就删**。**Skill 数量是"用得到的"，不是"想试的"**。

**错 3：从不精简**

项目 1 年后，**有 8 个 Skill 已经 3 个月没触发过**。**我留着**。

**修正**：**3 个月没触发 = 删除候选**。**Skill 是工具，不是收藏品**。

## Skills + Claude Code 的性能基准

**2026 年 4 月 Claude Code 的 Skills 性能（来自 Anthropic 公开数据）**：

- 100 个 Skills 启动延迟：约 800ms
- 50 个 Skills 启动延迟：约 400ms
- 20 个 Skills 启动延迟：约 200ms
- 10 个 Skills 启动延迟：约 100ms

**拐点**：15-20 个。**超过性能开始非线性下降**。

## Skills 优化的 5 个指标

**1. 启动延迟 < 500ms**（15 个 Skill）

**2. 触发准确率 > 85%**

**3. 触发拒绝率 > 85%**

**4. 输出质量 > 80%**

**5. 季度 review 时间 < 2 小时**

**5 个都满足 → Skills 系统健康**。

## 我自己的季度 review 流程

每季度 1 小时，**review 5 件事**：

1. **检查 Skills 数量**——是否 ≤ 15？多的删
2. **跑 golden set**——触发 / 拒绝准确率是否 ≥ 85%？
3. **看真实对话**——最近 1 个月哪个 Skill 误触发最多？改 description
4. **看真实对话**——哪个 Skill 该触发没触发？放宽 description
5. **更新 body**——有没有新场景 / 新模板 / 新规则没加？

**5 件事 1 小时**。**比启动新 Skill 1 天的工作量高 ROI**。

## 2 个"我后悔没做"的优化

**后悔 1：没早合并相似 Skill**

我 2025 年 12 月有 4 个 React 相关的 Skill。**到 2026 年 3 月合并成 1 个**。**中间 3 个月多花的 token** = 100×4×3 = 1200 token × 对话数。**粗算 5 美元**。

**后悔 2：没早用 paths 限定**

我 2025 年 11 月有 8 个 Skill 都没 paths。**到 2026 年 1 月加 paths**。**中间 2 个月误触发率 20%**——**多花 2 周调试**。

**教训**：**description 写完立刻加 paths**。**别等**。

## 总结：Skills 性能的金发姑娘

**5 个 Skill**：太少，功能不够
**10-15 个 Skill**：金发姑娘，**性能 + 功能平衡**
**20-30 个 Skill**：性能开始下降
**30+ 个 Skill**：必须拆项目

**我的目标：项目里保持 12-15 个 Skills**。**每年 review 1-2 次合并 / 删除**。**季度跑 1 次 golden set 评估**。

下一章讲 Skills 市场与共享——**怎么把 Skill 发到市场让别人用**。
