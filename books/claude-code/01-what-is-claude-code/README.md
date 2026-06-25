# 01. Claude Code 是什么

2025 年初 Anthropic 推出 Claude Code。我同事说"就是个 CLI 工具"。我用了一周后跟他说："这不是 CLI 工具，是 AI 工程师的'工地'。"

Claude Code 是**终端原生**的 AI 编程 agent，**主打 vibe coding 工作流**——你描述想要什么，它写代码；它写代码，你审；你审，commit。

这一章讲 Claude Code 的核心定位 + 它和 Cursor / Windsurf / Copilot 的根本差别。

## Claude Code 的 3 个关键特征

**1. 终端原生（Terminal Native）**

Claude Code 是 CLI 工具，跑在终端里。你打开 iTerm / Windows Terminal / VS Code 终端，输入 `claude` 就开始对话。

**为什么是终端而不是 IDE 插件**？
- 不绑定 IDE（VS Code / JetBrains / Vim / Emacs 都用）
- 适合远程开发（SSH / Docker / 云开发机）
- 适合自动化（脚本调用 Claude Code）
- 适合 code review 流程（CI 集成）

**2. Agentic（能自主行动）**

Claude Code 不是一个"代码补全工具"——它是一个"agent"。它能：

- 读文件、写文件
- 跑命令（npm install / git / docker / psql）
- 用 git 提交、推代码
- 跨多个文件修改
- 自己 debug（读错误、查 stack trace、找根因、修复）

**你不用"提示它写代码"**——**你说需求，它做完整的事**。

**3. 工具化（Tool-based）**

Claude Code 通过"工具"操作你的代码：
- Read / Write / Edit（文件操作）
- Bash（执行 shell）
- Grep / Glob（搜索）
- WebFetch / WebSearch（联网）
- 自定义工具（MCP）

**这种"工具化"让 Claude Code 可以做任何事**——**只要你能用命令做，Claude Code 就能做**。

## Claude Code vs Cursor / Windsurf / Copilot

**3 个常见对比维度**：

**1. 形态：**

- **Cursor**：IDE 改造版（VS Code fork + AI 增强）
- **Windsurf**：类似 Cursor
- **Copilot**：VS Code 插件
- **Claude Code**：终端 CLI

**2. 工作方式：**

- **Cursor**：Composer / Chat 双模式，文件 diff 预览
- **Windsurf**：Flow 模式，AI 主动编辑
- **Copilot**：行级补全为主
- **Claude Code**：自然语言驱动 + 工具调用

**3. 上下文：**

- **Cursor**：单项目 IDE 上下文
- **Windsurf**：单项目 IDE 上下文
- **Copilot**：当前文件 + 部分项目
- **Claude Code**：整个项目 + git + 终端 + 文件系统 + 联网

**关键差别**：
- Cursor / Windsurf **在 IDE 里工作**——视觉化但受限
- Claude Code **在终端工作**——抽象但自由
- 两者**目标用户不同**：GUI 派 vs CLI 派

## 2026 年的真实使用情况

**2026 年 4 月 Claude Code 的市场数据**：

- 月活用户：~300 万（Anthropic 公开数据）
- 月下载量（npm）：~500 万
- GitHub Trending：2025-2026 多次月度冠军
- 平均用户：月调用 500+ 次
- 重度用户：月 $100-300 token 费

**主要用户群**：
- 独立开发者（30%）
- 创业公司工程师（40%）
- 大厂 R&D 团队（20%）
- 研究 / 学术（10%）

**最适合**：
- 后端 / 全栈开发
- 脚本 / 自动化
- DevOps / SRE
- 数据库 / 迁移
- 重构大型代码库

**不太适合**：
- 前端 UI 设计（视觉化 IDE 优势）
- 教学 / 演示（终端不直观）
- 团队协作（个人工具）

## 我自己的 5 年 vibe coding 故事

我自己 2020 年开始写 side project，那时候用 Copilot。2022 年用 Cursor。2025 年开始用 Claude Code。

**3 个工具的体验差**：
- **Copilot**（2020-2022）：补全快速但**只能写片段**，**要我自己整合**。写完整功能 30 分钟 → 12 分钟。
- **Cursor**（2022-2024）：Composer 模式能改多文件，但**总被"是不是改对了"卡住**。写完整功能 12 分钟 → 5 分钟，但 review 还要 5 分钟。
- **Claude Code**（2025-）：**我口述需求，它做完整的事**。写完整功能 5 分钟 → 1 分钟，review 2 分钟。

**不是工具本身变强了，是工作流变了**——**从"我写代码它补"变成"它写代码我审"**。

## 2026 年 4 月真实工作流

我自己 90% 的项目开发都在 Claude Code 里跑。**典型一天**：

早上 9 点打开终端，启动 Claude Code。

```bash
claude
```

加载 CLAUDE.md（项目规范）+ Skills（按需）。开始当天工作：

```text
[我] 帮我给订单模块加个 refund API
[Claude] 我看到了 orders 表。让我先查 schema...
[我] 用 RESTful 风格，路径 /api/v1/orders/:id/refund
[Claude] 好。我先写 service 层，再写 controller，最后加测试
[Claude] [生成 3 个文件，1 个测试文件]
[我] 跑测试
[Claude] [跑 npm test]
[Claude] 8/10 通过，2 个失败。我看了一下是 mock data 没设。我修...
[Claude] 10/10 通过。要 commit 吗？
[我] /commit
[Claude] [git add + commit + push]
```

**整个流程 12 分钟**——**包括 review + commit**。

**3 年前同样任务需要 1.5 小时**。**7.5 倍提速**。

## Claude Code 的"非工具"价值

Claude Code 不只是一个"开发工具"——**它是一个"AI 工程师工作流"**。

**真实价值不在"写代码变快"，在"：**

1. **降低写代码的认知负担**——你不用记 API / syntax / edge case
2. **强制你描述清楚需求**——说错话 Claude 答错，逼你想清楚
3. **让你专注于"做什么"而不是"怎么做"**——架构师视角而不是打字员视角
4. **AI 处理重复工作，你处理判断**——你审代码、做决策、commit

**这个"角色转换"是 Claude Code 最大的价值**。**你不再是"写代码的人"，你是"指挥 AI 写代码的人"**。

## 接下来 9 章

- **ch02** 安装 + 10 个关键设置
- **ch03** CLAUDE.md 项目记忆（深入）
- **ch04** Skills + Hooks（工作流自动化）
- **ch05** SubAgent + Worktree（并行任务）
- **ch06** MCP 集成（连接外部工具）
- **ch07** 自定义 slash commands
- **ch08** 10 个真实场景实战
- **ch09** Token 成本 + 性能调优
- **ch10** 局限 + 与 Cursor/Codex/TRAE 的对比

如果你 2026 年只学一个新工具，**学 Claude Code**。**1 周上手，永久受益**。
