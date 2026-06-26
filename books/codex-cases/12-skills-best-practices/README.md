# 12. AGENTS.md + Skills 最佳实践：个人 ECC 系统

国外独立开发者用 Codex 一年后，沉淀出一套"个人 ECC（Engineering Capability Center）"——围绕 Codex 打造的个人工程能力系统。这一章讲清楚 AGENTS.md + Skills + MCP + Plan 模式的完整组合，给你一套**今天就能抄走的工作流**。

## 为什么需要"个人 ECC"

Codex CLI 不是只能生成代码片段，它能在你选定的目录里读取仓库、编辑文件、执行命令。**但默认行为是"通用"——它不知道你的项目约定**。

我之前在第 3 章讲过 AGENTS.md。但这次**重点不是单个文件，是整个体系**——AGENTS.md / config.toml / Skills / MCP / Plan / 截图视觉闭环 / 自动化，**七层组合起来**。

国外独立开发者管这套叫"个人 ECC"——**Engineering Capability Center**，**围绕 Codex 打造的个人工程能力系统**。当你从 0 到 1 做一个产品时，在需求、设计、架构、开发、测试、部署、维护这些阶段，**都有合适的 skill 帮你把工作推进得更稳**。

## 7 层 ECC 系统

### 层 1：任务上下文（AGENTS.md）

第 3 章详细讲过。这里再补 4 个国外独立开发者的进阶技巧。

**技巧 1：AGENTS.md 分两层**

```markdown
# ~/.codex/AGENTS.md（全局，跨项目）
## 通用规则
- 默认中文回答
- 改文件前先说明
- 不要硬编码 secret

# ~/projects/my-app/AGENTS.md（项目级）
## 项目特定规则
- 用 pnpm 不用 npm
- 数据库用 PostgreSQL
- API 必须有 OpenAPI 注解
```

**项目级覆盖全局级**——这跟 CSS 优先级一样。

**技巧 2：AGENTS.md 用结构化指令**

**DO / DON'T 列表**比纯叙述有效 30%。Codex 对结构化指令的遵循率显著高。

**技巧 3：把截图当 AGENTS.md 附件**

```bash
codex --sandbox workspace-write \
       --ask-for-approval on-request \
       -i ./screenshots/home-desktop.png \
       -i ./screenshots/home-mobile.png \
       "请基于两张截图实现当前项目首页..."
```

**图片只负责视觉目标，不负责工程上下文**。两张截图（桌面 + 移动）能稳定还原度 90%+。

**技巧 4：AGENTS.md 不要太长**

200-400 行是黄金区间。**每行必须可验证**——不要写"写好代码"这种废话。

### 层 2：个人默认配置（~/.codex/config.toml）

Codex CLI 的个人配置文件是 TOML。**独立开发者的最佳实践是把它当成"个人操作系统配置"**。

**最小配置**：

```toml
# 默认模型
model = "gpt-5.4"
model_provider = "openai"

# 审批模式
approval_mode = "auto-edit"

# 沙箱
sandbox = "workspace-write"

# 网络
network_access = "restricted"
allowed_domains = ["github.com", "npmjs.com", "*.openai.com"]

# 日志
log_level = "info"
log_file = "~/.codex/logs/codex.log"

# 主题
theme = "dark"
```

**多 profile 配置**（国外独立开发者很常用）：

```toml
[profiles.default]
model = "gpt-5.4"
approval_mode = "auto-edit"

[profiles.expensive]
model = "gpt-5.4"
approval_mode = "full-auto"

[profiles.cheap]
model = "deepseek-chat"
model_provider = "deepseek"
approval_mode = "auto-edit"

[profiles.review]
model = "gpt-5.4"
approval_mode = "suggest"
```

**用法**：

```bash
# 日常开发用 default
codex chat

# CI 脚本用 expensive（高质量）
codex --profile expensive chat "..."

# 测试用 cheap（省钱）
codex --profile cheap chat "..."

# 重要 review 用 review（最严格）
codex --profile review chat "..."
```

**实测省钱数据**：

- 简单任务用 cheap profile：$0.14/M tokens
- 复杂任务用 expensive profile：$2.5/M tokens
- **混合 profile：月成本从 $300 降到 $50**

### 层 3：重复任务沉淀成 Skills

**Skill 是 Codex 的"工作流说明书"**。第 11 章讲过，**核心原则是"重复 3 次以上的任务就该沉淀成 skill"**。

**Skill 的目录结构**：

```
~/.codex/skills/
├── create-plan/
│   └── SKILL.md
├── review-code/
│   └── SKILL.md
├── run-tests/
│   └── SKILL.md
└── deploy-staging/
    └── SKILL.md
```

每个 skill 一个目录，**里面必有一个 SKILL.md**。

**SKILL.md 模板**：

```markdown
---
name: skill-name
description: 一句话说明（30 字内）
trigger: 触发关键词（多个用逗号）
---

# Skill 名称

## 何时使用
- 场景 1
- 场景 2

## 执行步骤
1. 步骤 1（具体到命令级别）
2. 步骤 2
3. 步骤 3

## 输出格式
- 必含字段
- 可选字段

## 注意事项
- 边界 1
- 边界 2

## 失败处理
- 错误 X：怎么办
- 错误 Y：怎么办
```

**Skill 触发两种方式**：

**显式调用**：

```bash
codex chat "使用 create-plan skill，为我做一个用户系统"
```

**隐式触发**：

```bash
codex chat "我准备做一个用户系统，先帮我出计划"
# Codex 自动匹配 create-plan skill
```

## 10 个必装 Codex Skills（2026 实测）

国外独立开发者社区（openai/skills 仓库 19.3k+ stars）沉淀了**10 个最常用的 skill**。我按"独立开发者价值"排：

### Skill 1：create-plan（输出执行计划）

**价值**：强制 Codex 写代码前拆任务、出可审阅计划。

**触发关键词**：plan / 设计 / 拆解 / 怎么做

**SKILL.md 核心内容**：

```markdown
## 执行步骤
1. 阅读项目结构
2. 列出涉及的文件
3. 拆解为 5-10 个子任务
4. 估算每个子任务时间
5. 输出 Markdown 计划
6. 等待用户确认

## 输出格式
# [项目名] 执行计划

## 目标
[一句话]

## 涉及文件
- [文件路径 + 作用]

## 子任务
1. [子任务 1]（估计 X 分钟）
2. [子任务 2]（估计 X 分钟）
...

## 风险点
- [风险 1]
- [风险 2]

## 不做的事
- [边界 1]
```

**为什么必装**：Codex 经常"跑太快"——拿到任务就开干，**没有确认就改了一堆文件**。create-plan 强制它先出计划你 review。

### Skill 2：review-code（代码审查）

**价值**：以独立 reviewer 身份读 diff，输出优先级化问题。

**触发关键词**：review / 审一下 / 看看改动

**输出格式**：

```markdown
# Review 报告

## 严重问题（必须修）
- [文件:行号] 描述 + 建议

## 建议改进（可选）
- [文件:行号] 描述 + 建议

## 优点
- [值得保留的做法]

## 安全性
- [安全相关发现]

## 性能
- [性能相关发现]
```

**关键**：review mode **不修改工作树**，只输出报告。

### Skill 3：run-tests（跑测试套件）

**价值**：自动发现测试框架 + 跑全量 + 输出报告。

**触发关键词**：跑测试 / test / 验证

**执行步骤**：

```bash
1. 检测项目测试框架
   - 找 package.json / Cargo.toml / go.mod / requirements.txt
2. 跑全量测试
3. 收集失败用例
4. 输出报告
```

### Skill 4：commit-msg（生成 commit message）

**价值**：基于 diff 生成 Conventional Commits 格式 commit。

**触发关键词**：commit / 提交 / 记录

**输出**：

```
feat(user): add login endpoint

- POST /api/auth/login with JWT
- bcrypt password hashing
- rate limiting (5 req/min)
```

### Skill 5：refactor-safe（安全重构）

**价值**：跨文件重构前先列影响范围 + 备份。

**触发关键词**：refactor / 重构 / 改造

**执行步骤**：

```bash
1. 列出当前改动会影响的文件
2. 跑一遍基线测试
3. 提示备份 git stash
4. 分小步执行（每步跑测试）
5. 失败立即回滚
```

### Skill 6：debug-investigator（Bug 排查）

**价值**：基于日志 + 范围定位 bug，给出可能根因。

**触发关键词**：bug / 报错 / 不工作 / crash

**执行步骤**：

```markdown
1. 读相关日志
2. 列出可疑文件（最多 5 个）
3. 给出 2-3 个可能根因
4. 跑最小复现
5. 最小修改
6. 验证
7. 报告根因 + 改动
```

### Skill 7：doc-generator（生成文档）

**价值**：从代码自动生成 README / API doc / 注释。

**触发关键词**：文档 / doc / 注释

### Skill 8：type-migrate（TypeScript 类型补全）

**价值**：给 JS 项目补 TypeScript 类型。

**触发关键词**：ts / type / 类型

### Skill 9：i18n-extract（提取 i18n 文案）

**价值**：把硬编码文案提取到 i18n 文件。

**触发关键词**：i18n / 国际化 / 多语言

### Skill 10：db-migrate（数据库迁移）

**价值**：生成 Prisma / Drizzle / Flyway 迁移脚本。

**触发关键词**：migration / 迁移 / schema

## Skill 的 3 个作用域

**作用域 1：个人（~/.codex/skills/）**

跨项目私有 skill。**所有项目都能用**。比如 `commit-msg` / `review-code`。

**作用域 2：项目（.agents/skills/）**

团队共享，**随代码一起 clone**。比如项目特定的 `add-rest-endpoint` / `add-react-component`。

**作用域 3：管理员（/etc/codex/skills/）**

容器或机器级默认配置。**所有用户共享**。比如公司统一的 `security-review` / `compliance-check`。

**优先级**：项目级 > 管理员级 > 个人级（同 name 时覆盖）。

**国外独立开发者实践**：**80% 用个人 scope，20% 用项目 scope**。管理员 scope 很少用（除非团队 / 公司场景）。

## Skill 的"个人 ECC"组合

我自己的 ECC 系统按"产品交付链路"组织：

```
想法 → 需求分析 → UI/UX → 架构设计 → 数据库设计
     → 后端开发 → 前端开发 → 联调测试 → 安全审查
     → 部署上线 → 上线观察 → 文档沉淀 → ECC 维护
```

每个阶段配 2-3 个 skill：

**需求分析阶段**：

- `brainstorming`（头脑风暴）
- `requirement-doc`（需求文档模板）

**架构设计阶段**：

- `arch-diagram`（画架构图）
- `tech-debt-analyzer`（技术债扫描）

**后端开发阶段**：

- `add-rest-endpoint`（添加 REST 端点）
- `add-db-table`（添加数据库表）
- `api-test-gen`（API 测试生成）

**前端开发阶段**：

- `add-react-component`（添加 React 组件）
- `frontend-design`（截图转代码）
- `playwright-verify`（Playwright 视觉验证）

**部署阶段**：

- `deploy-staging`（部署到 staging）
- `smoke-test`（烟雾测试）
- `rollback`（一键回滚）

**总 skill 数**：20-25 个。**不多不少**——多了记不住，少了覆盖不全。

## MCP 增强：把外部世界接进 Codex

MCP（Model Context Protocol）是 Anthropic 2025 年推的开放协议，**标准化 LLM/Agent 与外部工具/数据源的通信**。

**MCP 的核心价值**：

- 一次编写，**到处运行**：MCP 服务器写一次，Claude Code / Codex CLI / Cursor / Windsurf 都能调
- 降低开发门槛：不用为每个 AI 工具单独写插件
- **生态共享**：跟 npm 包一样，可以发布 / 安装

**2026 年 5 月 MCP 生态**：

- MCP 服务器总数：**9,723 个**
- 月度下载量：**1.2 亿次**
- 最受欢迎：filesystem / github / google-search / postgres
- 支持 MCP 的 AI 工具：Claude Code / Codex CLI / Cursor / Windsurf / Notion Agent SDK

**Codex CLI 装 MCP 极简**：

```bash
# 装 Context7（最新文档查询）
codex mcp add context7 -- npx -y @upstash/context7-mcp

# 装 Figma（设计稿转代码）
codex mcp add figma -- npx -y @modelcontextprotocol/server-figma

# 装 PostgreSQL（直接查数据库）
codex mcp add postgres -- npx -y @modelcontextprotocol/server-postgres
```

**国外独立开发者最常用的 5 个 MCP**：

**MCP 1：Context7（最新文档查询）**

```bash
codex chat "用 Context7 查 Next.js 15 的 Server Actions 文档，然后实现一个表单"
```

**解决痛点**：AI 训练数据滞后，**官方文档更新比模型快**。Context7 让 Codex 实时查最新文档。

**MCP 2：Figma（设计稿转代码）**

```bash
codex chat "用 Figma MCP 读这个设计稿，然后实现对应组件"
```

**解决痛点**：设计师出 Figma → 你手动写代码。**Figma MCP 让 Codex 直接读 Figma 节点树**。

**MCP 3：GitHub（PR / Issue 操作）**

```bash
codex chat "用 GitHub MCP 列出仓库所有 open issues，按优先级排序"
```

**MCP 4：PostgreSQL（直接查数据库）**

```bash
codex chat "用 postgres MCP 查 user 表最近 24 小时的注册数据"
```

**MCP 5：飞书 CLI（中文办公）**

```bash
codex chat "用飞书 CLI 给我发一条测试消息"
```

第 8 章详细讲过。

**个人 ECC 系统的 MCP 配置**：

```bash
# ~/.codex/config.toml
[mcp_servers.context7]
command = "npx"
args = ["-y", "@upstash/context7-mcp"]

[mcp_servers.figma]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-figma"]
env = { FIGMA_TOKEN = "${FIGMA_TOKEN}" }

[mcp_servers.postgres]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-postgres"]
env = { DATABASE_URL = "${DATABASE_URL}" }
```

**Codex 启动时自动加载**——不写每次命令都加。

## 复杂任务先 Plan 再执行

国外独立开发者用 Codex 8 个月总结出的核心心法：

> **越是模糊、跨模块、影响面大的任务，越应该先让它规划、定位、确认边界，再让它改代码。**

**先进入 Plan 模式，让 Codex 收集上下文、提出问题、形成计划后再实现。**

**Plan 模式实战 prompt 模板**：

```markdown
我准备 [任务描述]。先不要改代码。

请输出：
1. 当前涉及的文件和它们的作用
2. 改动会影响哪些模块
3. 推荐的实现方案（A / B / C 三个选项 + 各自优劣）
4. 估计的代码量
5. 估计的实现时间
6. 可能的风险点
7. 不建议现在动的部分
```

**等 Codex 输出后**，**你 review 方案 → 选一个 → 才让它改代码**。

**这个流程的价值**：

- **不是省时间，是省返工**——Codex 直接开干经常跑偏，Plan 模式**逼它先把模糊需求转成清晰指令**
- **发现遗漏和矛盾**——你写需求时的盲区，Plan 阶段会暴露
- **风险点提前识别**——"动这块会影响 X" 这种判断，Codex 比你更准

## 截图视觉闭环

国外独立开发者最爱的功能之一——**截图 + Playwright 闭环**。

**完整工作流**：

```
参考图 → Codex 实现页面 → 启动 dev server → Playwright 打开
     → 截图对比 → 修正差异 → 再检查 → 完成
```

**prompt 模板**：

```markdown
请实现这张参考图对应的页面，并使用 Playwright 做视觉验证：

1. 先确认本项目如何启动本地开发服务（pnpm dev / npm run dev）
2. 实现页面
3. 启动 dev server
4. 使用 Playwright 打开页面（http://localhost:3000）
5. 桌面（1440px）和移动（375px）各截图
6. 对比参考图和当前截图，修正明显差异
7. 至少检查 desktop 和 mobile 两个断点
8. 最后输出差异说明和验证结果
```

**效果**：Codex 不只生成代码，**还自己验证**。**人只在最后 review 差异**。

## 实战工作流 5 套

### 工作流 1：截图转页面

**步骤 1：先分析不写代码**

```bash
codex -i ./screenshots/home.png "先不要改代码。请分析这张截图：
1. 页面结构
2. 组件拆分
3. 样式系统映射
4. 需要新增/复用的组件
5. 可能不清晰的截图细节
6. 实现计划"
```

**步骤 2：按计划实现**

```bash
codex resume --last "按照上一步计划实现页面。要求小步修改，优先复用已有组件。完成后运行 lint、typecheck、build。"
```

**步骤 3：自动对比修复**

```bash
codex resume --last \
  -i ./references/target.png \
  -i ./screenshots/current.png \
  "第一张是目标图，第二张是当前实现效果。请对比差异，只修复视觉差异，不要重构无关代码。"
```

### 工作流 2：Bug 排查

```bash
codex "日志在 History.log
请基于日志排查问题。

工作方式：
- 先不要改代码
- 找到可能相关的页面、组件、状态管理、接口请求和样式文件
- 说明最可能的 2-3 个原因
- 如果可以运行项目，请尝试复现
- 确认根因后，做最小修改
- 修改后运行相关检查
- 最后说明根因、改动文件、验证方式"
```

**关键**：给 Codex **清晰的错误范围**——日志 + 报错 + 复现步骤。**不要只说"代码不工作了"**。

### 工作流 3：大重构

```bash
codex "我准备重构当前项目的组件结构。先不要改代码。请输出：
1. 当前组件目录结构和主要职责
2. 重复代码和可抽象点
3. 高风险文件
4. 推荐的目标目录结构
5. 分阶段迁移计划
6. 每阶段的验证方式
7. 哪些地方不建议现在动"
```

**老项目改时千万不要让 AI 直接改**——老项目本身就够复杂，AI 理解起来也困难。**拆成 4 层让 AI 跑比较稳**：理解现状 → 识别风险 → 制定迁移计划 → 分批执行。

### 工作流 4：自审工作流

```bash
codex "请审查当前未提交改动。重点检查：
1. 是否有行为回归
2. 是否有类型风险
3. 是否破坏响应式
4. 是否有无关文件改动
5. 是否有可维护性问题
6. 是否缺少必要测试

只输出高风险问题和建议修复方案，不要改代码。"
```

**这是 review-code skill 的触发**。

### 工作流 5：风险任务用 review / diff / sandbox 控制

**3 个核心机制**：

- **review**：让独立 reviewer 身份读 diff
- **diff**：每步改动跟上一版对比
- **sandbox**：在隔离环境跑（worktree / Docker）

```bash
# 在 worktree 跑
codex --sandbox worktree "重构 user service"

# 改完看 diff
git diff feature/refactor-user

# review
codex --profile review "请审查这个 diff，重点看 N+1 查询"
```

## MCP 实战 2 个最常用

### 实战 1：Figma 设计稿转代码

```bash
# 装 Figma MCP
codex mcp add figma -- npx -y @modelcontextprotocol/server-figma

# 拿 Figma 链接
codex chat "用 Figma MCP 读 https://figma.com/file/XXX/XXX，
读 'Login Screen' frame，然后实现 React 组件。
要求：
- 用项目里的设计 token
- 保持响应式
- 跑 typecheck + build 验证
- 用 Playwright 截图对比"
```

**效果**：设计师出 Figma → 你不用再"看图写代码" → **Codex 直接读 Figma 节点树 + 翻译成 React**。

### 实战 2：Context7 实时文档

```bash
# 装 Context7
codex mcp add context7 -- npx -y @upstash/context7-mcp

# 用法
codex chat "用 Context7 查 Next.js 15 Server Actions 文档，
然后实现一个表单提交 action。
要求：
- 包含 Zod 校验
- 错误处理
- 成功后 revalidatePath
"
```

**解决痛点**：Codex 训练数据截止 2025 年初，**很多新 API 它不知道**。Context7 让它查最新文档。

## 1 个我自己的真实心得

我用 Codex 8 个月的最大心得：

> **很多人用 AI 写代码觉得不稳定，问题不一定出在工具本身，而是我们还在用"提需求"的方式使用它，却没有用"带团队"的方式管理它。你不给项目背景，它就只能猜；你不给边界，它就可能乱改；你不给验证标准，它就不知道什么叫完成；你不做最后判断，它就可能把一个看似能跑的方案交给你。**

**AI 的上限取决于使用 AI 的人的专业能力 + 认知能力**。

工具本身不产生价值，**使用工具的方式才产生价值**。

## 我的判断

**短期（3-6 个月）**：AGENTS.md + Skills + MCP 三件套成为 Codex 标准配置。**不会用的开发者会显著落后**。

**中期（6-12 个月）**：Skills 市场出现——**卖 skill 像卖 Substack newsletter**。垂直行业 skill（医疗 / 法律 / 金融）有商业化空间。

**长期**：**个人 ECC 系统 = 独立开发者的"操作系统"**。项目级 AGENTS.md + 个人级 Skills + 公司级 MCP = 完整的"AI 工程能力中心"。

下一章讲 Codex + MCP 完整实战——Figma / Context7 / Playwright / 飞书 CLI 全部接法。