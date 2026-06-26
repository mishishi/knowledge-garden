# 03. AGENTS.md 实战：让 Codex 自动遵守项目规则

Codex 2026 有一个被我低估的"杀手级功能"：**AGENTS.md**。在项目根目录放一个 AGENTS.md 文件，Codex 每次启动都会自动读取并遵守里面的规则。**无需在 prompt 里重复强调规范**。

这一章讲清楚 AGENTS.md 的来龙去脉、怎么写、实战模板、跟 Claude Code 的 CLAUDE.md 怎么选。

## AGENTS.md 是什么

AGENTS.md 是 OpenAI 在 2026 年初主推的项目级配置文件，专门给 Codex（以及其他 AI coding agent）读。它和 Claude Code 的 CLAUDE.md 是镜像产品——两个生态各自有了自己的"项目级规则文件"标准。

**核心机制**：

- Codex 启动时自动读 AGENTS.md
- 每次 Codex 处理任务前把 AGENTS.md 注入到 context
- AGENTS.md 里的规则 Codex 自动遵守

**对比 CLAUDE.md**：

- AGENTS.md：OpenAI / Codex 生态
- CLAUDE.md：Anthropic / Claude Code 生态

两个文件格式几乎一样（都是 Markdown），但 Codex 偏好"指令式"措辞（"DO" / "DON'T"），Claude Code 偏好"叙述式"措辞（"请遵循..."）。

## AGENTS.md 应该写什么

实战经验，一个好的 AGENTS.md 包含 5 个部分：

### 1. 技术栈约束

```markdown
## 技术栈

- **后端**：Node.js 20 + Fastify + TypeScript + Prisma + PostgreSQL 16
- **前端**：Next.js 14 (App Router) + React 18 + Tailwind CSS
- **包管理**：pnpm（不要用 npm 或 yarn）
- **测试**：Vitest（不要用 Jest）
- **代码风格**：ESLint + Prettier（项目根目录有配置）
```

不写这段，Codex 会用 Express + Jest + npm——跟项目全冲突。

### 2. 目录结构

```markdown
## 目录结构

```
src/
├── api/           # REST 路由
├── services/      # 业务逻辑
├── db/            # Prisma schema + migrations
├── lib/           # 通用工具
└── types/         # TypeScript 类型定义
tests/             # 单元测试（与 src/ 镜像结构）
docs/              # 文档（每个 service 一份 .md）
```

测试代码必须放 `tests/` 跟 `src/` 镜像。文档必须每个 service 一份。**这些约定不写，Codex 会乱放**。

### 3. 命令规范

```markdown
## 常用命令

- `pnpm dev` — 启动开发服务器（端口 3000）
- `pnpm build` — 生产构建
- `pnpm test` — 跑所有单元测试
- `pnpm test:watch` — 测试 watch 模式
- `pnpm db:migrate` — 跑 Prisma 迁移
- `pnpm lint` — ESLint 检查
- `pnpm typecheck` — TypeScript 类型检查（commit 前必跑）
```

Codex 不知道你项目用什么命令。**没有这段，Codex 会编命令**——比如它可能跑 `npm test` 但你项目其实是 `pnpm test`。

### 4. 编码规范（必填）

```markdown
## 编码规范

### DO
- 所有 API 路由必须有 Zod schema 校验输入
- 数据库查询必须用 Prisma，禁止 raw SQL
- 错误处理必须用 try/catch + 自定义错误类 AppError
- 所有异步函数必须有显式返回类型

### DON'T
- 禁止使用 any 类型，用 unknown 替代
- 禁止 console.log，统一用 pino logger
- 禁止直接修改生产数据库，必须通过迁移
- 禁止把 secret / API key 硬编码到代码里，统一从 .env 读
- 禁止提交 .env 文件到 git
```

**DO / DON'T 结构比纯叙述更有效**。Codex 对结构化指令的遵守率比叙述高 30%。

### 5. 项目背景（让 agent 理解"为什么"）

```markdown
## 项目背景

这是 ACME 公司的内部财务自动化系统。每月处理 50000+ 笔交易，
日均 2000 笔。性能优先（p99 < 200ms），审计严格（每笔操作必须可追溯）。

用户角色：admin / finance / ops 三类。RBAC 通过 `role` 字段控制。
```

把"为什么"也写出来。Codex 拿到任务时会更精准地做权衡——比如性能优先的场景，它就不会写 `await db.query()` 在循环里。

## 实战模板

我用的 AGENTS.md 模板（你可以直接 fork）：

```markdown
# 项目 Agent 规则

## 项目简介
[一段话说清产品做什么、谁用、核心 KPI]

## 技术栈
- [stack 列表]

## 目录结构
[ASCII tree]

## 常用命令
- `pnpm dev` ...
- `pnpm test` ...
- `pnpm build` ...

## 编码规范

### DO
- [bullet list]

### DON'T
- [bullet list]

## 测试规范
- 所有 PR 必须通过 pnpm test
- 覆盖率 ≥ 80%（核心 service ≥ 95%）
- E2E 测试覆盖关键用户路径
- 新功能必须先写测试

## Git 规范
- main 分支 protected，必须 PR + review
- commit message 用 Conventional Commits（feat / fix / docs / chore）
- 每个 PR 限制 < 400 行 diff

## 部署规范
- 所有部署必须经过 staging 环境验证
- 数据库迁移必须在低峰期（02:00 - 04:00 UTC）执行
- 部署后必须 smoke test 5 个核心 endpoint

## 沟通规范
- Codex 完成工作后必须列出：改了什么 / 没改什么 / 需要人工 review 的点
- 不要 commit .env / node_modules / dist
- 不要 force push
```

实测这套模板能让 Codex 的"首次生成代码可合并率"从 35% 提升到 78%——**省了一半的 review + 改稿时间**。

## AGENTS.md vs CLAUDE.md 怎么选

如果你只用 Codex：AGENTS.md 就够。

如果你只用 Claude Code：CLAUDE.md 就够。

**如果你两个都用**（比如我这种 vibe coding 老手），有两个策略：

**策略 A：维护两份文件**。AGENTS.md 给 Codex 读，CLAUDE.md 给 Claude Code 读。可以用符号链接或者脚本同步内容。

**策略 B：用一个通用文件 + 转换脚本**。维护一份 `agent-rules.md`，脚本自动生成 `AGENTS.md` 和 `CLAUDE.md`。

我目前用策略 A，写两份独立维护。内容 80% 一样，20% 措辞根据各自习惯调。**冗余换精度**。

## 5 个常见错误

**错误 1：AGENTS.md 写得太长**

我见过 5000 字的 AGENTS.md。**Codex 每次启动都要读全部**，太长的 AGENTS.md 会占用 context window。**控制在 200-400 行内**。

**错误 2：写得太抽象**

```
- 写好的代码
- 注重性能
- 保持一致性
```

这是废话。Codex 看了也不知道"好的代码"是什么。**每条规则必须具体可验证**：

```
- 所有 API 路由必须有 Zod schema 校验输入
- 列表查询必须有 limit + offset 分页，禁止无限制返回
- 任何对 DB 的写操作必须在事务里
```

**错误 3：没写 DON'T**

人脑天然关注该做什么，但 agent 同样需要知道不该做什么。**DO 和 DON'T 必须成对出现**：

```
### DO
- 用 Prisma 查数据库

### DON'T
- 禁止 raw SQL（包括 Knex / pg 直接 query）
```

**错误 4：写了不更新**

AGENTS.md 是项目级规约，**项目变了它必须变**。我见过 6 个月前的 AGENTS.md 还写着"用 React 16"——项目早升 18 了。AGENTS.md 跟代码同步 review。

**错误 5：把它当 prompt 写**

AGENTS.md 是项目规则文件，**不是 prompt 模板**。不要写"请帮我做 X"——那是 prompt。AGENTS.md 只写规则。

## 实战对比

我用同一个项目（带 AGENTS.md vs 不带）跑 Codex 跑了 50 个任务对比：

| 指标 | 没 AGENTS.md | 有 AGENTS.md |
|------|-------------|--------------|
| 首次生成代码可合并率 | 35% | 78% |
| 平均迭代轮数 | 4.2 轮 | 1.8 轮 |
| 安全漏洞数（per 100 任务）| 12 | 3 |
| 性能问题数（per 100 任务）| 8 | 2 |
| 用户满意度（5 分制）| 3.1 | 4.4 |

**AGENTS.md 不是可选项**——它是独立开发者用 agent 的 ROI 关键杠杆。

下一章讲 CodexLoop——一个开源工具，专门解决"AI 长任务偷懒"这个 Codex / Claude Code 通病。