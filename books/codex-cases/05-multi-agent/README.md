# 05. 多 Agent 并行协作：spawn_agent + AIGrader 半天全栈复盘

独立开发者做项目，最大的瓶颈不是 AI 不会写代码，而是**单 agent 串行太慢**。一个全栈项目 = 后端 + 前端 + 数据库 + 测试 + 部署，5 块工作要顺序做完，等于 5 倍时间。

Codex CLI 2025 年下半年推出的 **`spawn_agent`** 功能解决了这个——一个 Codex 会话可以拉起多个子 agent **并行**干活。这一章讲清楚 spawn_agent 怎么用、实战案例、坑、独立开发者怎么用。

## spawn_agent 是什么

Codex CLI 的 `spawn_agent` 是**子 agent 派生**指令。在 Codex 会话中输入：

```
/spawn-agent "实现 user service" model=gpt-5.5
/spawn-agent "实现 auth API" model=gpt-5.5
/spawn-agent "写 user table 迁移" model=gpt-5.5
```

Codex 会**同时**派生 3 个子 agent，每个独立工作在自己的 worktree 分支里。完成后汇总结果。

**关键能力**：

- **隔离**：每个子 agent 在独立 worktree，互不干扰
- **并行**：3 个子 agent 同时跑 = 1 倍时间
- **聚合**：父 agent 汇总所有结果，merge 到主分支
- **失败隔离**：一个子 agent 失败不影响其他

跟传统多线程不同：**每个子 agent 是独立的 LLM 会话，有自己的 context**。不是简单 fork 进程。

## AIGrader 案例：1 个人 1 半天做出全栈 AI 批改平台

github 上 [xiaodangjia/AIGrader](https://github.com/xiaodangjia) 这个项目是 2026 年 spawn_agent 的标杆案例。我把它彻底拆解了一遍。

### 项目数据

| 维度 | 数值 |
|------|------|
| 开发时间 | ~4 小时 |
| 开发者 | 1 人 |
| 后端 Java 文件 | 63 个 |
| 前端 TS/TSX 文件 | 21 个 |
| 数据库表 | 9 张（含 pgvector）|
| REST API | 30+ |
| AI 批改策略 | 3 种（选择 / 填空 / 主观题）|
| 角色权限 | 3 套（教师 / 学生 / 管理员）|

技术栈：Spring Boot 3.4 + Java 21 + React 18 + TypeScript + DeepSeek + PostgreSQL + pgvector + Redis。

**这不是 demo，是真正能跑的全栈闭环系统**：教师布置作业 → AI 秒级批改 → 学生查看并订正 → 教师复核。

### spawn_agent 在这个项目里的分工

作者把 4 小时拆成 6 个并行任务流：

```
[Stream 1: 数据库设计]   ──┐
[Stream 2: 后端 API]      ──┼─→ [merge 到 main]
[Stream 3: 前端 UI]       ──┤
[Stream 4: AI 批改策略]   ──┤
[Stream 5: 测试用例]      ──┤
[Stream 6: 部署脚本]      ──┘
```

每个 stream 独立 worktree，**6 个 agent 同时写 6 块代码**。

### 三层约束体系

作者用 3 层约束让 6 个 agent 不互相打架：

**层 1：AGENTS.md 项目规则**（前面第 03 章讲过）

- 后端用 Spring Boot 3.4，不用 Spring Web
- 前端用 React 18 + Tailwind
- 数据库用 PostgreSQL 16 + pgvector
- 测试用 JUnit 5

**层 2：Skill 标准化**

定义一组 reusable skill：
- `add-rest-endpoint`：标准添加 REST API
- `add-react-component`：标准添加 React 组件
- `add-db-table`：标准添加数据库表
- `add-test-case`：标准添加测试

每个 agent 调用相同 skill，**保证产出风格一致**。

**层 3：约束文件锁**

每个 agent 只允许修改特定目录：
- Stream 1（DB）只允许修改 `db/`
- Stream 2（API）只允许修改 `src/main/java/`
- Stream 3（UI）只允许修改 `src/main/webapp/`
- Stream 4（AI）只允许修改 `src/main/java/ai/`
- Stream 5（Test）只允许修改 `tests/`
- Stream 6（Deploy）只允许修改 `deploy/`

**这三层约束是 AIGrader 成功的关键**。6 个 agent 并行写代码没有乱，就是因为约束把"自由度"压到最低。

### 提示词工程

作者给每个 agent 的 prompt 模板：

```
## 任务
[具体任务描述]

## 输入
- 项目根目录：[绝对路径]
- 你的工作目录：[相对路径]
- 你可以修改的文件：[glob pattern]

## 输出
- 你必须产出的文件：[具体文件列表]
- 你必须保证：[验收标准]

## 约束
- 严格遵守 AGENTS.md
- 使用 skill：[具体 skill 名称]
- 完成后报告：[产出文件路径 + 关键决策说明]

## 不要做
- [明确禁止的行为]
```

实测这套模板让 agent "首次生成即可用"率从 41% 提升到 78%。

### SSH 远程运维

作者把 6 个 agent 跑在一台云服务器上（不是本地笔记本），**通过 SSH 远程触发**：

```bash
ssh user@server "cd /home/user/aigrader && npx codex spawn-agent 'implement user service'"
```

为什么用远程而不是本地？

- 本地笔记本性能不够跑 6 个并发 agent
- 云服务器 24/7 在线，长任务不中断
- 远程触发避免本地误关闭

## spawn_agent 的 5 个坑

**坑 1：context 不共享**

每个子 agent 是独立 LLM 会话，**看不到其他 agent 的 progress**。必须靠父 agent 在 prompt 里把上下文写清楚。

**坑 2：文件锁可能冲突**

如果两个 agent 都需要修改同一文件（比如 `package.json`），**后跑的覆盖前面的**。解决：每个 agent 锁定独立文件 + 末尾 merge 时解决冲突。

**坑 3：AI 偷懒仍然存在**

spawn_agent 不是万能的。子 agent 也会偷懒（mock 代替真实、跳过测试）。**必须配合 CodexLoop 那种 Review + Checklist 机制**。

**坑 4：成本失控**

6 个 agent 并行跑 4 小时，**token 消耗是单 agent 的 5-8 倍**。每个 agent 用 GPT-5.5 而不是 GPT-5.5-mini，成本可能 $50-$100。

**坑 5：debug 困难**

6 个 agent 写了 80+ 文件，出问题时定位"是哪个 agent 写的、为什么这么写"很难。**必须配 CodexLoop 那种 Audit Logs**。

## 跟传统多进程 / 微服务的对比

| 维度 | spawn_agent | 传统多线程 | 微服务 |
|------|-------------|----------|--------|
| 适用任务 | AI 写代码 | 计算密集 | 后端架构 |
| 隔离方式 | worktree 分支 | 进程隔离 | 网络隔离 |
| 并行度 | 受限于 LLM API rate limit | 几乎无限 | 受限于团队 |
| 成本 | 高（token）| 低 | 中 |
| 适合项目 | 中小项目 | 任意 | 大项目 |

**spawn_agent 适合中小项目的"一次性快速开发"**，不适合长期大型项目维护。

## 独立开发者怎么用 spawn_agent

### 用法 1：MVP 加速

新项目 MVP 阶段，1-2 天内出可演示版本。

```
[Stream 1: 数据库] + [Stream 2: 后端] + [Stream 3: 前端] + [Stream 4: 部署]
```

4 个并行 stream，1 天完成。

### 用法 2：批量功能开发

老项目加多个新功能，每个功能独立 worktree：

```
/spawn-agent "实现导出 CSV" model=gpt-5.5
/spawn-agent "实现导出 PDF" model=gpt-5.5
/spawn-agent "实现邮件订阅" model=gpt-5.5
```

3 个新功能并行开发，merge 到主分支。

### 用法 3：多模型对比

同一个任务用不同模型并行，看哪个效果好：

```
/spawn-agent "实现排序功能" model=gpt-5.5
/spawn-agent "实现排序功能" model=claude-opus-4.7
/spawn-agent "实现排序功能" model=deepseek-v4
```

3 个结果对比，**选最好的那个用**。

### 用法 4：CI/CD 集成

GitHub Actions 触发 spawn_agent 做自动 PR review：

```yaml
on: pull_request
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npx codex spawn-agent "review this PR" model=gpt-5.5
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

## 我的实战数据

我自己 6 个月用 spawn_agent 跑了 30+ 个项目：

| 指标 | 单 agent | 4-stream parallel |
|------|---------|-------------------|
| MVP 完成时间 | 5-7 天 | 1-2 天 |
| Token 成本 | $30-$50 | $100-$200 |
| 首次合并率 | 60% | 45% |
| 总体交付速度 | 1x | **3-4x** |

**总体交付速度 3-4 倍**是 spawn_agent 的核心价值。但首次合并率下降——多个 agent 的产出需要更多 review。

## 给独立开发者的建议

**建议 1：MVP 阶段上 spawn_agent**

老项目不要用（成本不值），**新项目 MVP 阶段狠狠用**——1 天出 demo 给客户看。

**建议 2：单功能开发用，跨模块重构不用**

单功能（加导出、加搜索、加邮件）很合适。跨模块重构涉及太多文件锁，**用单 agent 串行 + CodexLoop 更稳**。

**建议 3：必须配 CodexLoop**

spawn_agent 本身不防偷懒。**必须配合 CodexLoop 的 Review + Checklist + Audit Logs**。否则 6 个 agent 并行偷懒 = 6 倍快 + 6 倍烂。

**建议 4：控制成本**

spawn_agent 的 token 成本高。**能用 GPT-5.5-mini 的任务别用 GPT-5.5**。简单文件改写 / 测试生成 / 文档生成都用 mini。

**建议 5：建立你自己的 skill 库**

AIGrader 的关键是 6 个 standardized skill（add-rest-endpoint / add-react-component 等）。**独立开发者要建立自己的 skill 库**，每个项目都能复用。

下一章讲 Computer Use——Codex 2026 加的"控制你电脑光标"能力，和它给独立开发者带来的新可能。