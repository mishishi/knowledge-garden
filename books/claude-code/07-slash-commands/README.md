# 07. Slash Commands：自定义命令

我团队 2025 年 12 月每周开 1 次"代码规范检查会议"——3 个人 1 小时。**改成 slash command 后，每周 5 分钟跑一次**。

这一章讲 Claude Code 的 slash commands——**把"重复命令"做成"1 个 `/xxx` 调用"**。

## Slash Command 是什么

Slash command = **Claude Code 的自定义命令**。`/review`、`/test`、`/commit` 这些内置命令之外，**你可以定义自己的**。

```text
内置：/help, /clear, /compact, /mcp
自定义：/review-pr, /deploy-staging, /format-code
```

**输入 `/xxx` 触发对应 prompt**——**Claude Code 跑 prompt 定义的工作流**。

## 3 种用法

**用法 1：项目级命令（团队共享）**

```text
项目根目录/
└── .claude/
    └── commands/
        ├── review-pr.md
        ├── deploy-staging.md
        └── format-code.md
```

**用法 2：用户级命令（个人）**

```text
~/.claude/
└── commands/
    ├── daily-standup.md
    ├── weekly-summary.md
    └── ...
```

**用法 3：Skills 内嵌（条件触发）**

某些 Skills 内部用 slash command 作为入口。

## 写一个 Slash Command

**3 个步骤**：

**Step 1：创建命令文件**

```bash
mkdir -p .claude/commands
touch .claude/commands/review-pr.md
```

**Step 2：写 markdown 内容**

```markdown
# Review PR

审查当前分支的所有未提交改动，按以下清单：
1. 安全问题（SQL 注入、XSS、权限校验、敏感信息泄露）
2. 性能问题（N+1 查询、内存泄漏、不必要的循环）
3. 代码质量（命名、单一职责、可测试性）
4. 错误处理（try-catch、错误信息、日志）

按严重程度输出：
- 🔴 严重（必须修）
- 🟡 警告（应该修）
- 🟢 建议（可选）

不要重复已知问题。
```

**Step 3：触发命令**

```bash
# 在 Claude Code 里
/review-pr
```

**Claude Code 跑这个 prompt 的工作流**。

## 5 个"项目级"必备 Slash Commands

**Command 1：/review-pr** — 审查当前分支所有改动。

```markdown
# Review PR

按 [code-review Skill] 的清单审查当前分支所有改动。

输出格式：
## Review
- 🔴 严重：[问题] in [文件:行号] — [修复建议]
- 🟡 警告：[问题] in [文件:行号] — [修复建议]
- 🟢 建议：[优化] in [文件:行号]

## 总结
- 阻塞 [N] 个严重问题
- [N] 个警告需要修复
- [N] 个建议可优化
```

**Command 2：/commit** — 按团队规范 commit。

```markdown
# Commit

按 [git-commit Skill] 的规范提交当前改动：

1. 跑 `git diff --staged --stat` 看 staged 改动
2. 跑 `git status` 看 untracked 文件
3. 按 conventional commits 规范生成 commit message
4. 跑 `git add -A` + `git commit -m "<message>"`
5. 跑 `git log -1` 确认 commit 成功

不要 force push。不要修改 main 分支。
```

**Command 3：/deploy-staging** — 部署到 staging 环境。

```markdown
# Deploy to Staging

部署当前 main 分支到 staging：

1. 确认当前分支是 main：`git branch --show-current`
2. 拉最新：`git pull origin main`
3. 跑测试：`npm test`
4. 跑构建：`npm run build`
5. 部署：`./scripts/deploy.sh staging`
6. 报告部署结果

如果任何步骤失败，停止并报告。
```

**Command 4：/format** — 格式化所有代码。

```markdown
# Format Code

格式化项目所有代码：

1. 跑 `npx prettier --write .`
2. 跑 `npx eslint --fix .`
3. 跑 `git status` 看哪些文件改了
4. 如果有改动，提示用户 commit

不要 commit 改动。
```

**Command 5：/weekly-summary** — 生成本周工作总结。

```markdown
# Weekly Summary

生成本周工作总结：

1. 跑 `git log --since="7 days ago" --author="me" --oneline`
2. 列本周 commit
3. 按 [code / test / docs / config] 分类
4. 总结本周做了什么
5. 下周计划（基于未关闭的 issue 和 TODO）

输出 markdown 格式。
```

## Slash Command 的 3 个核心优势

**1. 团队标准化**

```text
团队每个工程师都跑 /review-pr
   ↓
输出格式完全一致
   ↓
review meeting 不用讨论格式
```

**2. 重复操作 1 个命令**

```text
原本 5 步操作：add → diff → commit message → commit → log
现在 1 步：/commit
```

**3. 知识沉淀**

```markdown
# /deploy-staging
# ... 完整步骤
```

新人入职第一天，**看 commands 目录就知道团队所有工作流**。

## 4 个 Slash Command 模板

**模板 1：简单命令** — 1-2 句话能说清的。

```markdown
# Commit

按团队规范提交当前改动。
```

**模板 2：步骤命令** — 5-10 步流程。

```markdown
# Review PR

审查当前分支：

1. 跑 `git diff main --stat`
2. 列出所有改动文件
3. 按安全 / 性能 / 质量 4 维度审查
4. 输出 markdown 格式
```

**模板 3：模板命令** — 固定输出格式。

```markdown
# Daily Standup

生成本日 standup：

```markdown
## 今天
- [做了什么]

## 昨天
- [昨天做了什么]

## 阻塞
- [什么问题]
```
```

**模板 4：Skill 引用命令** — 和 Skills 配合的命令。

```markdown
# Code Review

按 [code-review Skill] 审查当前分支。

不要重复 Skill 已经做的事——只做 Skill 没覆盖的。
```

## 8 个"用户级"必备 Slash Commands

我自己的 `~/.claude/commands/`：

```text
daily-standup.md       # 每日 standup
weekly-summary.md      # 每周总结
monthly-review.md      # 每月 review
brainstorm.md          # 头脑风暴
research.md            # 调研模板
write-doc.md           # 写文档模板
explain-code.md        # 解释代码
refactor-plan.md       # 重构计划
```

**8 个常驻**——**每天用 1-2 个**。

**Command 1：daily-standup.md**

```markdown
# Daily Standup

生成本日 standup：

1. 问用户 3 个问题：
   - 今天打算做什么？
   - 昨天做了什么？
   - 有什么阻塞？
2. 整理成 markdown 格式：

```markdown
## [日期]

### 昨天
- ...

### 今天
- ...

### 阻塞
- ...
```

3. 保存到 `daily/[日期].md`
```

**Command 2：brainstorm.md**

```markdown
# Brainstorm

头脑风暴模板：

1. 问题：[用户填]
2. 约束：[用户填]
3. 目标：[用户填]

按以下结构生成 10 个方案：
- 方案 1：[名字] — [实现思路] — [优劣] — [复杂度]
- 方案 2：...
- 方案 3：...

每个方案不少于 50 字描述。
```

**Command 3：refactor-plan.md**

```markdown
# Refactor Plan

生成重构计划：

1. 分析目标文件 / 目录
2. 列出所有"代码异味"（长函数 / 重复代码 / 高耦合）
3. 按优先级排序（高频改动 / 关键路径优先）
4. 每个异味给 1 个具体重构方案
5. 输出 markdown 计划：

```markdown
## 重构目标
[文件 / 目录]

## 代码异味
### 1. [异味名]
- 位置：[文件:行号]
- 严重度：[高/中/低]
- 重构方案：[具体步骤]

### 2. ...
```
```

## Slash Command 调试技巧

**命令不触发**：

1. 检查文件位置（`.claude/commands/` 或 `~/.claude/commands/`）
2. 重启 Claude Code（`/exit` 然后 `claude`）
3. 检查文件名（小写 + .md 后缀）

**命令执行了但不对**：

1. 命令 prompt 写得太模糊——**加具体步骤**
2. 上下文没传——**明确"当前分支"等**
3. 模型不理解——**给 1 个示例**

## Slash Command + Skills 的协同

**Slash Command 是"入口"**——**Skills 是"工作流"**。

**实际用法**：

```markdown
# /code-review

按 [code-review Skill] 审查当前分支。

如果发现严重问题，列出后停止——不要自动修改。
如果没有严重问题，输出"READY TO MERGE"。
```

**用户输入 /code-review** → **触发 command** → **command 引用 code-review Skill** → **Skill 加载详细规范**。

**3 层配合**：command（入口）+ skill（流程）+ CLAUDE.md（项目背景）。

## 4 个常见错误

**错 1：命令写得太长**

```markdown
# 错（5K 字命令）
（包含所有规范、所有流程、所有 FAQ）
```

**问题**：加载浪费。**改**：**短 + 具体**。

**错 2：命令和 Skill 重复**

```markdown
# 错
/review-pr 命令里有 1000 行 code review 规范
code-review Skill 也有 1000 行 code review 规范
```

**改**：**Skill 放详细规范，command 引用 Skill**。

**错 3：命令不写步骤**

```markdown
# 错
# Review PR
审查当前分支。
```

**改**：**写具体步骤**——**Claude Code 不知道"审查"是什么意思**。

**错 4：命令硬编码敏感信息**

```markdown
# 错
# Deploy
跑 `kubectl apply -f https://internal-api.company.com/deploy`
```

**改**：**用环境变量**——**`$DEPLOY_URL`**。

## Slash Command 与"AI 工程师"工作流

2026 年 4 月的"AI 工程师"工作流：

```text
1. 早上 /daily-standup → 自动写 standup
2. 上午写代码（Claude Code + Skills）
3. 中午 /commit → 规范 commit
4. 下午 /review-pr → 自动 review
5. 晚上 /weekly-summary → 自动总结
```

**5 个 slash command 覆盖 1 天工作流**。

## 我自己 2026 年 4 月的 Commands 数量

```text
项目级：5 个（review-pr, commit, deploy, format, ...）
用户级：8 个（daily-standup, weekly-summary, brainstorm, ...）
```

**13 个 total**。**每天用 5-7 个**。

## 真实数字：Commands 节省时间

我自己测过 4 周：

| Command | 每周用 | 节省时间 |
|---|---|---|
| /commit | 20 次 | 5 min/次 = 100 min |
| /review-pr | 5 次 | 20 min/次 = 100 min |
| /format | 10 次 | 2 min/次 = 20 min |
| /daily-standup | 5 次 | 5 min/次 = 25 min |
| /weekly-summary | 1 次 | 30 min = 30 min |

**每周节省 4.5 小时**。**4 周 18 小时**。

## Slash Command 的 4 个未来趋势

**1. 命令市场**

类似 Skills 市场——**2026 年下半年出现"slash command 市场"**。

**2. 跨 IDE 标准化**

Claude Code 的 slash command 格式成为标准——**Cursor / Continue.dev 也支持**。

**3. AI 生成的 commands**

```text
用户：每次都要 review React 组件
Claude Code：自动生成 /review-react-component.md
```

**4. Commands 链式调用**

```text
/commit 内部调用 /format + /lint + /test
```

**Slash commands 2026 年下半年会成为"AI 工程师的标准工作流"**。

下一章讲 10 个真实场景实战——**完整看一遍 Claude Code 怎么用**。
