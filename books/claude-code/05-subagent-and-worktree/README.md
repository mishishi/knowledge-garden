# 05. SubAgent 与 Worktree：并行任务

我 2025 年开始用 Claude Code 时，每次都让 1 个 Claude 处理所有事。**重构成 3 个 SubAgent 之后，单个任务的处理时间从 18 分钟降到 6 分钟**。

这一章讲 SubAgent + Worktree——**Claude Code 的"并行"能力**。

## SubAgent 是什么

SubAgent 是**主 Claude Code 启动的"子 Claude"**——**独立 context、独立工具、独立任务**。

```text
[主 Claude Code] (协调者)
   ├── [SubAgent 1: 研究] (独立 context)
   ├── [SubAgent 2: 写代码] (独立 context)
   └── [SubAgent 3: 测试] (独立 context)
```

**每个 SubAgent 跑独立任务，完成后把结果返回主 Claude**。

**类比**：
- 主 Claude = 项目经理
- SubAgent = 工程师 A / 工程师 B / 工程师 C
- 各自独立工作，结果汇总

## 3 个 SubAgent 的核心价值

**1. 并行**

3 个 SubAgent 同时跑 = **3 个任务同时进行** = **3 倍速度**（理论上）。

实际不是完美 3 倍（有些任务依赖前一个），但 **2-3 倍提速很常见**。

**2. 隔离 context**

主 Claude 的 context 不会被子任务污染。**研究 agent 读了 10 篇文档不会污染主 Claude 的 context**。

**3. 错误隔离**

SubAgent 失败不会影响主 Claude。**可以重试 SubAgent 而不影响整体**。

## SubAgent 的 3 种用法

**用法 1：并行研究**

```text
用户：调研 X、Y、Z 三个方案的优劣
Claude Code：
  - 启动 SubAgent 1 研究 X
  - 启动 SubAgent 2 研究 Y
  - 启动 SubAgent 3 研究 Z
  - 3 个 SubAgent 并行
  - 主 Claude 汇总 3 个结果
```

**用法 2：分层任务**

```text
用户：开发订单模块
Claude Code：
  - SubAgent 1：写 SQL migration
  - SubAgent 2：写 API endpoint（等 SubAgent 1）
  - SubAgent 3：写测试（等 SubAgent 2）
  - SubAgent 4：写文档（等 SubAgent 2）
  - 主 Claude 汇总
```

**用法 3：错误隔离**

```text
主 Claude：跑命令 X
SubAgent A：跑命令 X（独立）
  - 失败 → 重试 SubAgent A
  - 成功 → 主 Claude 拿到结果
```

## SubAgent 的 3 个限制

**1. 不能直接编辑主仓库**

SubAgent 跑独立任务，**不能直接改主 Claude 的文件**——**要返回结果给主 Claude 决定**。

**2. 不能共享 context**

每个 SubAgent 独立 context。**主 Claude 的对话历史对 SubAgent 不可见**。

**3. 启动慢**

启动 SubAgent 本身有 1-2 秒开销。**短任务用 SubAgent 反而更慢**。

**经验**：**SubAgent 适合"长任务 + 需要并行"**。**短任务用主 Claude 直接跑**。

## SubAgent 的 4 个关键参数

启动 SubAgent 时设 4 个参数：

```text
[SubAgent 1: 研究]
  - goal: "研究 React Server Components 的最佳实践"
  - context: {用户问题: "...", 已知信息: "..."}
  - tools: [WebSearch, WebFetch, Read]  # 限制工具
  - output_format: "JSON: { sources: [], summary: '...' }"
```

**4 个参数决定 SubAgent 的行为**。

**实际 Claude Code 调用 SubAgent 的方式**（**伪代码**）：

```text
主 Claude 调用 SubAgent：
  - 给 SubAgent 一个明确的 task 描述
  - 给 SubAgent 必要的 input（context）
  - 限制 SubAgent 的工具集
  - 期望 SubAgent 的输出格式
```

## 实战 1：并行重构 5 个文件

**场景**：用户让 Claude Code 重构 5 个组件，每个用相同的 hook 模式。

**不用 SubAgent**：

```text
主 Claude 顺序处理 5 个文件：
- 改 File 1 (3 分钟)
- 改 File 2 (3 分钟)
- 改 File 3 (3 分钟)
- 改 File 4 (3 分钟)
- 改 File 5 (3 分钟)
总计 15 分钟
```

**用 SubAgent**：

```text
主 Claude 启动 5 个 SubAgent：
- SubAgent 1 改 File 1
- SubAgent 2 改 File 2
- SubAgent 3 改 File 3
- SubAgent 4 改 File 4
- SubAgent 5 改 File 5
5 个 SubAgent 并行
总计 3-4 分钟（启动开销 + 最长 SubAgent 的时间）
```

**5 倍提速**。

## 实战 2：分层写模块

**场景**：用户让 Claude Code 写"用户管理"模块（DB + API + UI + 测试）。

**不用 SubAgent**：

```text
主 Claude 顺序：
- 设计 schema
- 写 migration
- 写 API
- 写 UI
- 写测试
- 写文档
总计 30 分钟（每步串行）
```

**用 SubAgent（依赖式并行）**：

```text
主 Claude：
- 步骤 1：写 schema（主 Claude）
- 步骤 2：并行启动 4 个 SubAgent
  - SubAgent A: 写 migration（依赖 schema）
  - SubAgent B: 写 API（依赖 schema）
  - SubAgent C: 写 UI（依赖 API）
  - SubAgent D: 写测试（依赖 API）
- 步骤 3：主 Claude 汇总
总计 12 分钟
```

**2.5 倍提速**。

## 实战 3：失败重试

**场景**：跑数据库 migration，可能失败。

**不用 SubAgent**：

```text
主 Claude：跑 migration
   ↓
失败
   ↓
主 Claude：分析错误
   ↓
主 Claude：修
   ↓
主 Claude：再跑
   ↓
失败
   ↓
主 Claude：再次分析...
   ↓
context 被错误日志污染
```

**用 SubAgent**：

```text
SubAgent 1：跑 migration
   ↓
失败 → context 是 SubAgent 1 的
   ↓
SubAgent 2：分析错误
   ↓
修复 + 再跑
   ↓
成功 → 把结果给主 Claude
```

**主 Claude 的 context 干净**——**错误处理不污染主对话**。

## Worktree 是什么

Worktree 是 **git worktree 的封装**——**同一仓库的多个独立工作目录**。

**为什么 Claude Code 用 worktree**：

- SubAgent 改文件不冲突
- 多个 SubAgent 各自一个 worktree
- 完成后主 Claude 合并回主分支

## Worktree 的典型用法

```text
[主 worktree: main 分支]
[SubAgent 1: .worktrees/feature-A]
[SubAgent 2: .worktrees/feature-B]
[SubAgent 3: .worktrees/feature-C]
```

**3 个 SubAgent 在 3 个 worktree 里并行**。

**完成后**：主 Claude merge 3 个 worktree 回 main。

## SubAgent + Worktree 实战：3 个独立 feature

**场景**：3 个 feature 互相独立，可以完全并行。

**设置**：

```bash
# 主 worktree
cd /path/to/project

# Claude Code 启动 3 个 SubAgent
# 每个 SubAgent 跑独立 worktree
claude-task 1: feature-A  (worktree: .worktrees/A)
claude-task 2: feature-B  (worktree: .worktrees/B)
claude-task 3: feature-C  (worktree: .worktrees/C)
```

**3 个 SubAgent 各自**：
- 在自己的 worktree 改文件
- 不影响其他 worktree
- 完成后 commit 到自己的分支

**主 Claude 汇总**：

```bash
git checkout main
git merge feature-A
git merge feature-B
git merge feature-C
```

**3 个 feature 并行 = 3 倍提速**。

## SubAgent + Worktree 的 4 个限制

**1. 资源消耗**

每个 SubAgent 是独立 Claude session。**3 个 SubAgent = 3 倍 token 成本**。

**经济账**：**3 个 SubAgent 跑 1 小时 = 3 个 Claude 用户跑 1 小时**。**比单人串行 3 小时贵**。

**2. 协调成本**

主 Claude 要协调 3 个 SubAgent——**写好 task 描述、分发、汇总**。**协调成本 ≈ 15-20% 总时间**。

**3. 合并冲突**

3 个 worktree 改同一文件 → 合并冲突。**SubAgent 任务设计时就要避免冲突**。

**4. 调试难**

3 个 SubAgent 各自 context。**主 Claude 调试时看不到 SubAgent 的细节**。

**经验**：**SubAgent 适合"清晰独立的任务"**。**强依赖的任务用主 Claude 串行**。

## SubAgent 的 3 个最佳实践

**1. 任务描述要明确**

```text
# 错（模糊）
"调研 React Server Components"

# 对（明确）
"调研 React Server Components 的：
- 3 个核心概念
- 5 个最佳实践
- 1 个反例
输出 JSON 格式
要求 5 分钟内完成
```

**明确的 task = SubAgent 输出好**。**模糊的 task = SubAgent 输出乱**。

**2. 限制工具集**

```text
SubAgent "研究"：只给 [WebSearch, WebFetch, Read]
SubAgent "写代码"：只给 [Read, Edit, Write, Grep]
SubAgent "跑测试"：只给 [Bash]
```

**限制工具 = 限制风险**。**也给 SubAgent 减 context 负担**。

**3. 设超时**

```text
SubAgent 任务：30 秒没进展就放弃
```

**避免 SubAgent 卡住无限循环**。

## 我自己 2026 年的 SubAgent 使用频率

**30% 的任务用 SubAgent**。剩下 70% 串行主 Claude 处理。

**用 SubAgent 的场景**：
- 3+ 个独立任务
- 每个任务 5+ 分钟
- 任务之间无强依赖

**不用 SubAgent 的场景**：
- 1-2 个任务
- 任务 < 5 分钟
- 任务强依赖

## 真实数字：SubAgent 提速效果

我自己测过 10 个真实任务：

| 任务 | 串行 | 1 SubAgent | 3 SubAgent | 提速 |
|---|---|---|---|---|
| 重构 5 个文件 | 15 min | 10 min | 4 min | 3.7x |
| 写 1 个完整模块 | 30 min | 30 min | 12 min | 2.5x |
| 调研 3 个方案 | 18 min | 12 min | 7 min | 2.6x |
| 跑全测试套件 | 8 min | 8 min | 8 min | 1x |
| 简单文件改写 | 2 min | 3 min | 5 min | 0.4x（更慢） |

**关键 insight**：
- **3+ 独立任务**：SubAgent 显著提速
- **强依赖任务**：SubAgent 帮助小
- **短任务**：SubAgent 反而慢（启动开销）

**3 个 1 分钟的任务 = 3 个 SubAgent 跑 1.5 分钟（含启动）= 不如主 Claude 串行 3 分钟**。

## SubAgent 的"伪调用"在 Claude Code 里的实现

**Claude Code 2026 实际提供的 SubAgent API**（**伪代码**）：

```text
# 启动 SubAgent
agent spawn "研究 React Server Components" \
  --tools "WebSearch,WebFetch,Read" \
  --timeout 300 \
  --output "json"

# 等待结果
agent wait $TASK_ID

# 拿结果
result = agent get $TASK_ID
```

**CLI 命令行调用**——**不是 GUI**。

## Worktree 集成的真实 API

```bash
# Claude Code 启动 SubAgent + Worktree
claude task spawn "改 File A 用 hook 模式" \
  --worktree ".worktrees/A" \
  --branch "feature/A" \
  --tools "Read,Edit,Write,Bash(git:*)"

# 完成
git -C .worktrees/A add -A
git -C .worktrees/A commit -m "feat: ..."
git -C .worktrees/A push -u origin feature/A
```

**3 个 SubAgent 各自跑 worktree + branch，主 Claude 后期 merge**。

## 我自己的 3 个 SubAgent 反模式

**反模式 1：SubAgent 干 1 分钟的活**

```text
# 错
SubAgent 1: 改这个文件 1 行
SubAgent 2: 改那个文件 1 行
启动开销 > 任务时间
```

**改**：**主 Claude 串行**。

**反模式 2：SubAgent 任务强依赖**

```text
# 错
SubAgent 1: 设计 schema
SubAgent 2: 写 API（等 SubAgent 1 完）
SubAgent 3: 写 UI（等 SubAgent 2 完）
3 个 SubAgent 串行 = 1 个 Claude 跑 3 倍时间
```

**改**：**主 Claude 串行**。

**反模式 3：SubAgent 改同一文件**

```text
# 错
SubAgent 1: 改 File A 的第 1-50 行
SubAgent 2: 改 File A 的第 51-100 行
合并冲突
```

**改**：**每个 SubAgent 改不同文件**。

## 2 个真实故事

**故事 1：3 倍提速成功的**

```text
任务：把 8 个 React 组件的 class → function 重构
方案：8 个 SubAgent 跑 8 个 worktree
结果：3.5 分钟（8 个并行）
对比：30 分钟（主 Claude 串行）
8.5 倍提速
```

**故事 2：SubAgent 失败的**

```text
任务：写一个完整的新模块（schema + API + UI + 测试 + 文档）
方案：5 个 SubAgent 并行
结果：SubAgent 之间 context 不共享，UI 不知道 API 的接口，测试不知道 schema
最终：主 Claude 串行重做
```

**教训**：**强依赖任务用主 Claude 串行**。**SubAgent 适合"清晰独立"**。

下一章讲 MCP 集成——**Claude Code 连接外部工具的标准协议**。
