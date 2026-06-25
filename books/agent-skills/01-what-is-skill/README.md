# 01. Skills 是什么

2025 年 10 月 16 日，Anthropic 推出一项新功能叫 Skills。我当时没太在意——以为是 Claude Code 的小升级。

3 个月后看到数据才反应过来：公开可用的 Agent Skills 已经超过 85,000 个，27 家平台支持这个标准。

**Skills 不是"Claude Code 的小升级"，是 Agent 能力的"模块化封装标准"**。

这一章讲 Skills 的核心概念 + 它跟其他 Claude 能力（Projects / MCP / Custom Instructions）的差别。

## Skills 的核心概念

Skills = **一个标准化的能力包**。形式上是一个文件夹，里面包含：
- `SKILL.md`（必备）：技能描述 + 使用规则，YAML frontmatter + Markdown body
- `scripts/`（可选）：可执行脚本（Python / Bash）
- `references/`（可选）：参考文档（API 文档、规范说明）
- `assets/`（可选）：附件素材（模板、图片、配置）

**关键创新：渐进式披露（Progressive Disclosure）架构**。

每次会话启动时，Claude 只读每个 Skill 的 `name` 和 `description`，约 100 token。**几十个 Skill 同时挂着不撑爆 context window**。

当你发起任务时，Claude 语义匹配当前意图，**只在需要时才加载完整的 Skill 内容**（SKILL.md 全文 + 关联资源）。

**这套架构解决了"AI 工具越多 context 越乱"的核心问题**。

## Skills vs 其他 Claude 能力

Claude 有 4 类"上下文注入"机制：Custom Instructions、Projects、MCP、Skills。**4 者用途不同，混着用**：

**Custom Instructions**（系统级固定）：每个对话都加载。比如"用中文回答"、"代码风格用 camelCase"。**适合高频、不变的指令**。

**Projects**（项目级固定）：只对 Project 内的对话生效。可以上传文件、设定指令。**适合团队协作的"项目级别"上下文**。

**MCP**（工具协议）：连接 AI 应用和外部工具服务。**适合"读文件 / 查数据库 / 调 API"等动作型操作**。

**Skills**（能力模块）：按需加载的执行规范。**适合"做某类事情的最佳实践"**。

具体差异：

| 维度 | Instructions | Projects | MCP | Skills |
|---|---|---|---|---|
| 加载时机 | 始终 | 项目内始终 | 连接时 | 按需 |
| 占用 token | 全部 | 全部 | 工具定义 100/token | 默认 100/技能 |
| 适合什么 | 风格/规则 | 项目背景 | 外部工具 | 工作流程 |
| 谁维护 | 用户 | 用户/团队 | 协议方 | 用户/社区 |
| 复用 | 个人 | 团队 | 跨应用 | 跨应用 |

**实际用法**：
- **始终加载**：用 Custom Instructions（"中文 + 简洁"）
- **项目级背景**：用 Projects（"我们产品是 X，用户是 Y"）
- **外部工具**：用 MCP（"读 postgres、查 GitHub、发 Slack"）
- **工作流程**：用 Skills（"用这个 Skill 写代码 review"、"用那个 Skill 生成 API 文档"）

## Skills 的真实价值

**Skills 解决了 Claude 长期存在的"失忆"问题**。

LLM 的通病：每次对话都从零开始。你每次都要重复"项目用 pnpm 不是 npm"、"错误处理用 try-catch"、"测试覆盖率 80% 起"。**每个新会话前 10 分钟都在"重新教学"**。

Skills 把"教学"打包成可复用的能力包。**第一次写完，所有未来的会话自动加载**。

更关键的是 Skills 是**版本化、可分享、可审计**的。团队可以把内部最佳实践做成 Skills，工程师入职第一天就拥有"团队的标准工作流"。**Skills = 工程化的"团队记忆"**。

## Skills 在 2026 年的位置

**Skills 是"能力工程"时代的开端**。

之前的"提示词工程"是"针对单次交互优化指令"。**Skills 是"把可复用的能力做成可重用模块"**。

类比：
- 提示词工程 = 写 SQL 脚本
- Skills = 写软件库
- Custom Instructions = 全局配置
- MCP = 外部 API 集成
- Skills = 内部业务逻辑

**这是从"提示词调优"到"能力工程"的范式跃迁**。**2026 年是 Skills 元年**——像 2010 年代的 iOS App Store，所有人开始建 Skills 市场。

## Skills 不是什么

**Skills 不是 prompt 的替代品**。每个 Skill 内部仍然是 LLM 在执行推理——Skill 提供的是"上下文规范"，不是"替代推理"。

**Skills 不是 fine-tuning**。Skill 不修改模型权重，只是"在合适的时候给模型喂合适的信息"。

**Skills 不是 RAG**。RAG 召回的是"事实性信息"，Skills 加载的是"工作流程规范"。

**Skills 是"程序化的工作流说明书"**。**当 Claude 接到某类任务时，按 Skill 定义的步骤执行**。

## 谁在用 Skills

2026 年 4 月我自己的项目里，**Skills 已经成为 Claude Code 工作流的标准配置**。我装的 8 个 Skills：

- `frontend-design`：写前端时强制按设计系统规范
- `code-review`：PR review 时按团队标准检查
- `api-doc-gen`：写 API 文档时自动生成 OpenAPI spec
- `db-migration`：写数据库迁移时按团队规范
- `test-coverage`：补测试时按 80% 覆盖率
- `git-commit`：写 commit message 时按 conventional commits
- `error-handling`：写错误处理时按 try-catch + log
- `i18n-check`：写代码时检查中英文支持

**这 8 个 Skills 把我"每次重复说"的话变成了"自动加载"**。**每天省 1-2 小时"重新教学"**。

## 接下来的 9 章

- **ch02** SKILL.md 文件结构详解
- **ch03** Skills 触发机制：手动 / 自动 / paths
- **ch04** CLAUDE.md vs Skills 分工（最关键的边界问题）
- **ch05** 8 大实用 Skills 拆解
- **ch06** 写你的第一个 Skill
- **ch07** Skills 测试与评估
- **ch08** Token 成本优化（Skills 多了会撑 context 吗？）
- **ch09** Skills 市场与共享
- **ch10** Skills 生态与未来

如果 2026 年你只学一个新概念，**Skills 是性价比最高的**。**1 周学会，永久受益**。
