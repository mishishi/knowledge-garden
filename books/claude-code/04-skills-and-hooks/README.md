# 04. Skills 与 Hooks：工作流自动化

我团队 2025 年 12 月每周开 1 次"code review 会议"——**3 个工程师 review 30 个 PR**。

**会议 2 小时**。**3 个人 6 小时人工 review**。

我装了 4 个 Skills（code-review / test-coverage / error-handling / security-audit）后——**会议从 2 小时变成 30 分钟**。**3 个人只需要 review Claude Code 标红的严重问题**。**剩下 90% 是 Claude Code 已经 review 过的**。

这一章讲 Skills + Hooks——**Claude Code 工作流自动化的两个核心机制**。

## Skills 是什么

Skills 上一本书讲过，**Claude Code 的 Skills 是按需加载的工作流**——**当任务匹配时，模型自动加载并按 Skill 规范执行**。

**Skills 的核心价值**：
- 把"重复说"的规范做成"自动应用"
- 把"每个项目都做"的工作做成"标准化"
- 把"团队经验"做成"可复用的能力包"

## Skills 在 Claude Code 里的 3 个用法

**用法 1：项目级 Skills（`.claude/skills/`）**

```text
项目根目录/
└── .claude/
    ├── CLAUDE.md
    └── skills/
        ├── code-review/
        │   └── SKILL.md
        ├── test-coverage/
        │   └── SKILL.md
        └── error-handling/
            └── SKILL.md
```

**作用域**：仅本项目。

**用法 2：用户级 Skills（`~/.claude/skills/`）**

```text
~/.claude/
└── skills/
    ├── frontend-design/
    │   └── SKILL.md
    ├── git-commit/
    │   └── SKILL.md
    └── ...
```

**作用域**：所有项目。

**用法 3：发到市场（公开 Skills）**

见上一本书的"市场与共享"章节。

## Skills 的触发机制

Skills 触发 = **description + when_to_use + paths 三层匹配**。

**案例：code-review Skill**

```yaml
---
name: code-review
description: 按团队规范审查 TypeScript 代码 PR（review / diff / 看看）。安全、性能、质量、错误 4 维度。涉及 src/ 时触发。
paths:
  - "src/**/*.{ts,tsx}"
  - "tests/**"
---

# Code Review
（步骤 + 模板）
```

**触发场景**：

```text
用户："帮我 review 一下这段代码"
   ↓
Claude Code 读所有 Skills 的 description
   ↓
匹配 "review 一下" 关键词 → code-review
   ↓
读 SKILL.md body + 跑审查流程
```

**3 个触发维度**：
1. **关键词匹配**（description 含用户说的词）
2. **场景匹配**（when_to_use 描述的任务）
3. **文件匹配**（paths 限定文件类型）

## 8 个"项目级"必备 Skills

我自己 2026 年项目里常驻 8 个 Skills（**完整版见上一本书的 Agent Skills 实战**）：

| Skill | 触发 | 节省时间 |
|---|---|---|
| code-review | PR / 改 src 代码 | 30 min → 8 min |
| frontend-design | 改 .tsx/.css | UI 颜值 1 档 |
| test-coverage | 补测试 / 问测试 | 25 min → 6 min |
| db-migration | 改 migrations | 90% 错 减 90% |
| git-commit | 提交代码 | commit msg 质量 10x |
| api-doc-gen | 写 API | 2h/接口 → 10 min |
| error-handling | 写新函数 | 线上事故 -80% |
| i18n-check | 改 UI 文案 | 硬编码 -95% |

**8 个 Skills 覆盖 90% 任务**。**剩余 10% 用 prompt 临时聊**。

## Hooks 是什么

Hooks 是**事件触发的 shell 命令**——**当 Claude Code 触发某个事件时，自动跑你定义的命令**。

**5 种事件**：
- `PreToolUse`：工具调用前
- `PostToolUse`：工具调用后
- `Stop`：Claude Code 停止时
- `SessionStart`：会话开始
- `SessionEnd`：会话结束

## 5 个"项目级"必备 Hooks

**Hook 1：自动格式化**

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write(*.{ts,tsx,js,jsx,css,scss,json,md})",
        "hooks": [{
          "type": "command",
          "command": "npx prettier --write $file"
        }]
      }
    ]
  }
}
```

**触发**：Claude 写完 .ts/.css/.json/.md 时 → 自动跑 prettier。

**节省**：每次 commit 不用手动 `npx prettier --write .`。

**Hook 2：日志预过滤**

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash(cat *log*)",
        "hooks": [{
          "type": "command",
          "command": "grep -n 'ERROR\\|WARN' $file | head -50"
        }]
      }
    ]
  }
}
```

**触发**：Claude 想 cat 日志时 → 先 grep 过滤。

**节省**：10000 行日志 → 50 行 ERROR/WARN。

**Hook 3：自动跑测试**

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit(*.{ts,tsx})",
        "hooks": [{
          "type": "command",
          "command": "npm test -- --silent --bail"
        }]
      }
    ]
  }
}
```

**触发**：Claude 改完 .ts 时 → 自动跑测试。

**节省**：不用 Claude 手动 `npm test` 验证。

**Hook 4：禁止读敏感文件**

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read(**/.env*)",
        "hooks": [{
          "type": "command",
          "command": "echo 'BLOCKED: cannot read .env files' && exit 1"
        }]
      }
    ]
  }
}
```

**触发**：Claude 想读 .env 时 → 阻止 + 返回 1。

**注意**：还要在 deny 列表加 .env ——**双重保险**。

**Hook 5：commit 前 review**

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash(git commit:*)",
        "hooks": [{
          "type": "command",
          "command": "git diff --staged --stat"
        }]
      }
    ]
  }
}
```

**触发**：Claude 跑 `git commit` 前 → 先打印 staged diff stats。

**节省**：commit 不会偷偷藏大改动。

## 完整 hooks 配置模板

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write(*.{ts,tsx,js,jsx,css,scss,json,md})",
        "hooks": [{
          "type": "command",
          "command": "npx prettier --write $file 2>/dev/null || true"
        }]
      },
      {
        "matcher": "Edit(*.{ts,tsx})",
        "hooks": [{
          "type": "command",
          "command": "npm test -- --silent --bail 2>&1 | tail -20"
        }]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash(cat *log*)",
        "hooks": [{
          "type": "command",
          "command": "grep -n 'ERROR\\|WARN' $file | head -50"
        }]
      },
      {
        "matcher": "Read(**/.env*)",
        "hooks": [{
          "type": "command",
          "command": "echo 'BLOCKED' && exit 1"
        }]
      },
      {
        "matcher": "Bash(git commit:*)",
        "hooks": [{
          "type": "command",
          "command": "git diff --staged --stat"
        }]
      }
    ]
  }
}
```

**5 个 hook 覆盖 90% 自动化场景**。

## Skills + Hooks 的协同

**Skills** = **Claude 自己知道"该做什么"**
**Hooks** = **环境自动执行"配套动作"**

**实际工作流**：

```text
1. 用户：帮我给 X 函数加单元测试
2. Claude Code 触发 test-coverage Skill（自动匹配 "测试" 关键词）
3. Skill 加载：跑测试覆盖率
4. Claude 写测试代码
5. Write 工具调用 → PostToolUse Hook 触发
6. Hook 自动跑：prettier + npm test
7. 测试通过 → 继续
8. 测试失败 → Hook 输出错误 → Claude 看到
9. Claude 修复 → 重复 5-8
10. 通过 → 用户 /commit
11. git commit 触发 PreToolUse Hook
12. Hook 输出 staged diff
13. Claude 确认 diff 合理 → 跑 commit
```

**整个流程 0 手动**。

## 3 个常见错误

**错 1：Hook 太严格**

```json
// 错：每次 Edit 都跑测试（太频繁）
{
  "matcher": "Edit(*.{ts,tsx})",
  "hooks": [{
    "type": "command",
    "command": "npm test"
  }]
}
```

**问题**：编辑 1 行也跑全套测试，**慢**。

**改**：只在 Edit `tests/` 或 Edit 关键文件时跑。

**错 2：Hook 失败中断流程**

```json
// 错：prettier 失败让 Claude Code exit
{
  "type": "command",
  "command": "npx prettier --write $file"
}
```

**问题**：prettier 配置问题 → hook 失败 → Claude Code 整个中断。

**改**：`|| true` 兜底。

**错 3：Hook 不限定 matcher**

```json
// 错：所有 PostToolUse 都跑 prettier
{
  "matcher": "*",  // 太宽
  "hooks": [...]
}
```

**问题**：连 `Read` 工具都触发——**浪费**。

**改**：`Write(*.{ts,tsx,js,jsx})` 精确限定。

## Skills + Hooks 实战 1：Code Review 自动化

**3 个机制配合**：

```text
1. Skill: code-review
   - 触发：用户说"review"
   - 加载：审查清单
   - 输出：严重/警告/建议 3 档

2. Hook: PostToolUse (Edit)
   - 触发：编辑完 .ts
   - 跑：npm test

3. Hook: PreToolUse (git commit)
   - 触发：commit 前
   - 跑：git diff --staged --stat
```

**完整工作流**：

```text
用户：改完 X 函数后，review + commit
   ↓
Claude Code 改 X（Skill 不触发，自动改）
   ↓
PostToolUse Hook：自动跑 npm test
   ↓
测试通过 → 用户：review
   ↓
code-review Skill 触发
   ↓
按清单输出严重/警告/建议
   ↓
用户：commit
   ↓
PreToolUse Hook：git diff stat
   ↓
Claude Code 看到 diff → commit
```

**0 手动步骤**。

## Skills + Hooks 实战 2：Test + Commit 自动化

**目标**：Claude Code 改完代码 → 自动跑测试 → 自动 commit。

**3 个配置**：

```yaml
# Skill: auto-test
# 描述：自动跑测试 + 失败时修复
# 触发：Edit 完 .ts 后
```

```json
// Hook 1: Edit 后跑测试
{
  "matcher": "Edit(*.{ts,tsx})",
  "hooks": [{
    "type": "command",
    "command": "npm test -- --silent --bail 2>&1 | tail -10"
  }]
}

// Hook 2: 测试通过后自动 commit
{
  "matcher": "Bash(npm test:*)",
  "hooks": [{
    "type": "command",
    "command": "if [ $? -eq 0 ]; then git add -A && git commit -m 'auto: pass tests'; fi"
  }]
}
```

**结果**：Claude 改完代码 → 自动跑测试 → 通过 → 自动 commit。

**节省 1-2 小时/天**。

## 我自己 2026 年的 Skills + Hooks 数量

```text
Skills: 8 个常驻 + 2 个实验
Hooks: 5 个
```

**8 + 2 = 10 个 Skills**（在 15 个上限内）。
**5 个 Hooks**（自动化 90% 重复操作）。

**组合效果**：**每天 2-3 小时"重复操作"省掉**。

## Skills 调试技巧

**Skill 不触发**：

1. 改 description（更具体）
2. 加 paths 限定（更精确）
3. 加 when_to_use（更多场景）

**Skill 过度触发**：

1. 改 description（加"不适用"）
2. 加 paths 限定（更严格）
3. 设 user-invocable: false

**Skill 输出不对**：

1. 改 body（更详细的步骤）
2. 加模板（强制输出格式）
3. 加清单（强制检查项）

## Hooks 调试技巧

**Hook 不触发**：

1. 检查 matcher（glob 匹配？）
2. 检查命令路径（绝对路径？）
3. 加 `echo "fired"` 看是否触发

**Hook 失败**：

1. 单独跑命令看错误
2. 加 `|| true` 兜底
3. 改 hook 改成只 log 不 fail

**Hook 慢**：

1. 减少 hook 命令的运行时间
2. 加 cache（如 npm install 用 cache）
3. 减少 matcher 范围

## 我自己的 3 个后悔

**后悔 1：没早用 Hooks 自动跑测试**

我手动跑了 3 个月测试。**改成 hook 后省了 30+ 小时**。

**后悔 2：没早把"项目规范"放 Skills**

我之前放 CLAUDE.md，**加载 1.5K 浪费**。**改成 Skills 按需加载**。

**后悔 3：没早用 PreToolUse 过滤敏感文件**

我之前没 deny .env，**Claude 偶然读到过 1 次**。**改成 hook + deny 双重保险**。

下一章讲 SubAgent + Worktree——**Claude Code 的"并行任务"机制**。
