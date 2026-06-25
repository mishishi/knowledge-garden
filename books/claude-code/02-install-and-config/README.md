# 02. 安装与 10 个关键设置

我第一次安装 Claude Code 时以为装好就能用。**结果一上来就卡住 4 个小时**。

不是我装错，是我没改 5 个默认设置。**这些默认设置是给"一次性 demo"用的，不是给"日常开发"用的**。

这一章把我**真正每天在用的 10 个设置**讲清楚——**少这 10 个你会抓狂**。

## 3 分钟装好

**Mac / Linux**：

```bash
# 用 npm（需要 Node.js 18+）
npm install -g @anthropic-ai/claude-code

# 验证
claude --version
```

**Windows**（PowerShell）：

```powershell
npm install -g @anthropic-ai/claude-code
claude --version
```

**登录**：

```bash
claude
# 第一次会打开浏览器，登录 Anthropic 账号
# 完成后回到终端，开始对话
```

**3 分钟搞定**。装完先跑一个 demo 确认能用。

## 5 个"必须改"的设置

默认装好之后，**5 个设置不改你会痛不欲生**。

**设置 1：默认权限模式（acceptEdits）**

**默认**：每次工具调用都弹"Allow / Deny"提示。**一上午 47 次确认**。

**改成**：`acceptEdits` ——**自动批准文件编辑**。

```json
// ~/.claude/settings.json
{
  "permissions": {
    "defaultMode": "acceptEdits"
  }
}
```

**适用**：**你信任的项目**。**新项目**用 `default`（每次确认）。

**设置 2：Allow 规则（白名单工具）**

**默认**：连 `git status` 都要确认。

**改成**：白名单常用工具。

```json
{
  "permissions": {
    "allow": [
      "Read",
      "Glob",
      "Grep",
      "Edit",
      "Write",
      "Bash(git:*)",
      "Bash(npm:*)",
      "Bash(pnpm:*)",
      "Bash(node:*)"
    ]
  }
}
```

**不写进 allow 的命令 = 每次确认**。**只把"你 100% 安全"的命令加白名单**。

**设置 3：Deny 规则（黑名单危险操作）**

**默认**：Claude Code 能读 `.env` 和 `.ssh` 目录。**这不行**。

**改成**：黑名单敏感文件。

```json
{
  "permissions": {
    "deny": [
      "Read(**/.env*)",
      "Read(**/.ssh/**)",
      "Read(**/secrets/**)",
      "Bash(sudo:*)",
      "Bash(rm -rf:*)",
      "Bash(curl * | bash)",
      "Bash(eval:*)"
    ]
  }
}
```

**deny 永远高于 allow**。**deny 列表 = 不可越线**。

**设置 4：自适应思考（关闭）**

**2026 年 2 月起 Claude 默认"自适应思考"**——它自己决定每轮分配多少算力。

**问题**：遇到"简单"任务直接跳过思考 → **灾难性下游 bug**。

**改成**：强制每轮都有推理预算。

```json
{
  "env": {
    "CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING": "1"
  }
}
```

**实测**：关掉后，模型"更稳"——**回答前会认真想**。

**设置 5：默认 effort（high）**

**2026 年 3 月 Anthropic 把默认 effort 从 high 调到 medium**——**默默没公告**。

**改回**：

```json
{
  "env": {
    "CLAUDE_CODE_DEFAULT_EFFORT": "high"
  }
}
```

**或临时在对话里**：`/effort high`。

## 5 个"建议改"的设置

**设置 6：MCP 工具数量限制**

**默认**：每个 MCP server 连接会**每轮加载 18000+ token**。

**问题**：挂 5 个空闲 server，**没敲 prompt 就烧 90000 token**。

**改法**：定期 `/mcp` 列出当前 server，**用不上的断掉**。

```bash
# 列出当前 MCP server
/mcp

# 断开不用的
> 断开 postgres (不再需要)
> 断开 docker (暂时不用)
```

**设置 7：模型路由（按任务选模型）**

**默认**：用主对话模型（通常是 Sonnet 或 Opus）。

**改法**：在对话里切：

```bash
/model opus    # 复杂任务
/model sonnet  # 日常编码
/model haiku   # 简单格式 / 文档
```

**节省规则**：**80% 日常用 sonnet，20% 重构用 opus，简单任务用 haiku**。

**Opus 比 Sonnet 贵 5 倍**——**别用 Opus 回答正则问题**。

**设置 8：自动格式化的 hook**

**问题**：Claude 写完代码我手动跑 Prettier。

**改法**：PostToolUse hook，写完 .ts 自动格式化。

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write(*.{ts,tsx,js,jsx})",
        "hooks": [{
          "type": "command",
          "command": "npx prettier --write $file"
        }]
      }
    ]
  }
}
```

**实测**：写完代码就格式化好，**省掉 1 个手动步骤**。

**设置 9：日志预过滤**

**问题**：让 Claude 读 10000 行 server log 直接撑爆 context。

**改法**：PreToolUse hook，过滤日志。

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

**Claude 看到的是过滤后的 50 行 ERROR/WARN**，**不是 10000 行原文**。

**设置 10：项目记忆（/memory）**

**问题**：每次新对话 Claude 都"失忆"——我每次都要重新说"用 pnpm 不是 npm"。

**改法**：用 `/memory` 持久化。

```bash
# 一次设置
/memory add "this project uses pnpm, not npm"
/memory add "测试覆盖率要求 80%"

# 后续每次会话启动自动加载
```

**我自己的 2026 年 4 月项目**：

```text
/memory:
- "use pnpm, not npm"
- "测试覆盖率 80%+"
- "用 TypeScript strict mode"
- "不引入新依赖不解释"
- "代码风格: 函数 < 50 行"
```

**5 行规则，省掉每天 5 分钟"重新教学"**。

## 完整 settings.json 模板

```json
{
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "Read", "Glob", "Grep", "Edit", "Write",
      "Bash(git:*)", "Bash(npm:*)", "Bash(pnpm:*)", "Bash(node:*)",
      "Bash(ls:*)", "Bash(cat:*)", "Bash(mkdir:*)"
    ],
    "deny": [
      "Read(**/.env*)",
      "Read(**/.ssh/**)",
      "Read(**/secrets/**)",
      "Bash(sudo:*)",
      "Bash(rm -rf:*)",
      "Bash(curl * | bash)",
      "Bash(eval:*)"
    ]
  },
  "env": {
    "CLAUDE_CODE_DEFAULT_EFFORT": "high",
    "CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING": "1"
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write(*.{ts,tsx,js,jsx})",
        "hooks": [{
          "type": "command",
          "command": "npx prettier --write $file"
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
      }
    ]
  }
}
```

**这套配置我用了 3 个月没改过**。

## 3 个常见配置错误

**错 1：把 .env 加到 allow**。

```json
// 错
"allow": ["Read(**/.env*)"]
```

**危险**——Claude 可能把 API key 写到 log。

**永远 deny 敏感路径**。

**错 2：defaultMode 选 bypassPermissions**。

```json
// 错
"defaultMode": "bypassPermissions"
```

**完全无确认**——Claude 跑什么你都不知道。**适合测试，不适合生产**。

**用 `acceptEdits`**——自动批准 Edit/Write，但其他命令仍确认。

**错 3：env 变量里放真 token**。

```json
// 错
"env": {
  "GITHUB_TOKEN": "ghp_xxxxx"
}
```

**Token 进 settings.json = 永久明文**。**用 `~/.bashrc` 或 `direnv` 注入**。

## 配置文件位置

```text
~/.claude/
├── settings.json          # 全局配置（每个用户一台电脑）
├── CLAUDE.md              # 全局规则（所有项目都用）
├── memory/                # 持久化项目记忆
│   └── ...
└── skills/                # 全局 Skills
    └── ...

每个项目：
.claude/
├── settings.local.json    # 项目级配置（覆盖全局）
├── CLAUDE.md              # 项目级规则（覆盖全局）
├── skills/                # 项目级 Skills
└── commands/              # 自定义 slash commands
```

**优先级**：项目级 > 全局。**项目里能改的不要在全局改**。

## 检查你的配置

跑这个命令，看配置是否正确：

```bash
claude config show
```

**会显示**：
- 当前模型
- 默认权限模式
- 已启用的 hooks
- MCP server 列表
- Skills 列表

**每周 review 1 次**——**避免配置漂移**。

## 调试配置问题

**配置不生效**：
1. 重启 Claude Code（`/exit` 然后 `claude`）
2. 检查 JSON 格式（`python -m json.tool ~/.claude/settings.json`）
3. 检查路径（绝对路径 vs 相对路径）

**hooks 不工作**：
1. 检查 matcher 模式（glob 是否匹配）
2. 检查命令路径（绝对路径）
3. 用 `echo` 加在 hook 开头看是否触发

**deny 不工作**：
1. deny 必须有 `**` glob（不能只写 `.env`）
2. 检查是否有冲突的 allow（deny 永远高于 allow）

## 4 个"配置哲学"

**1. 越严越好**。**deny 多加几条没事，allow 漏一条就要 47 次确认**。

**2. 全局配置最少**。**全局只放"用得到的"**——**项目特定的放项目级**。

**3. 一次改 1-2 个**。**别一次改 10 个**——**不知道哪个搞坏了**。

**4. 季度 review**。**每 3 个月看一次**——**用习惯变了配置也要变**。

## 1 个"我后悔没早做"的事

**后悔**：没早用 `acceptEdits` + hooks。

**6 个月前我**：
- 每次 Edit 都点"Allow"
- 每次写完代码手动跑 Prettier
- 每次 cat log 都被 10000 行撑爆 context

**改成现在**：
- 自动批准
- 自动格式化
- 自动过滤日志

**6 个月省下大约 30 小时**。**1 个小配置改对了 ROI 巨大**。

下一章讲 CLAUDE.md——**项目级"团队记忆"的详细写法**。
