# 11. Codex 工具生态全景：4 条官方线 + 3 个第三方平替

国外独立开发者用 Codex 一年多了，**真正在生产环境跑的，不只是一个 CLI**。OpenAI 自己把 Codex 拆成了 4 条入口，社区又冒出了 3 个值得知道的平替工具。这一章把整张生态图完整画出来——每条线解决什么问题、什么场景用、跟谁配合。

## Codex 的 4 条官方入口

OpenAI 2025 年 5 月重启 Codex 项目，到现在一年。**4 条入口线**各自覆盖不同场景：

### 线 1：Codex CLI（终端党的起点）

**OpenAI 官方开源**（Apache-2.0），Rust 写，npm 一行装：

```bash
npm install -g @openai/codex
# macOS 也支持
brew install --cask codex
```

**这是大多数国外独立开发者的第一站**。原因简单：CLI 跟 git / vim / tmux / shell 脚本天然兼容，不绑架 IDE。

实际用法分三档权限模式：

```bash
# suggest：只建议不执行（最安全，新手 / 不熟悉项目用）
codex --approval-mode suggest "fix the failing test"

# auto-edit：自动改文件但命令要审批（日常开发首选）
codex --approval-mode auto-edit "重构 user service"

# full-auto：全自动（CI 脚本、定时任务用）
codex --approval-mode full-auto "跑全量测试 + 生成报告"

# yolo：连网络访问都放开（最危险，沙箱环境用）
codex --approval-mode yolo "..."
```

**为什么独立开发者都从 CLI 起**：

- 零 IDE 锁定，**能跟现有 shell 工具链组合**
- exec 模式跑完即退，**适合 cron / 定时任务 / CI 钩子**
- 配置文件 `~/.codex/config.toml` 可深度定制

**官方模型档位**：

- GPT-5.4：默认主力，日常开发够用
- GPT-5.3-Codex-Spark：优化过延迟，**Pro 用户专属**，实时交互更顺
- /model 或 --model 随时切换

**认证两种路径**：

- ChatGPT 账号登录（Plus $20/月，Pro $200/月各有不同 API 额度）
- 直接配 OpenAI API Key

**注意**：很多国内开发者不知道，**ChatGPT 订阅本身就含 Codex 使用额度**。Plus 用户有 $5、Pro 用户有 $50 的 API 额度。**很多人重复付费了**。

### 线 2：Codex Desktop App（多 Agent 指挥中心）

2026 年 2 月先发 macOS，3 月跟 Windows。**这是 Codex 跟 Claude Code 最大的差异点**——Claude Code 至今没有官方桌面 App。

**桌面端 3 个核心能力**：

**能力 1：worktree 隔离**

每个 agent 跑在独立 git worktree，**互不干扰**。你可以同时开 3-5 个任务（一个写新功能、一个修 bug、一个做 review），**它们各自在独立代码副本上工作**。

这就是第 5 章讲的"6 stream 并行"在桌面端的实现基础。

**能力 2：Skills 系统**

桌面端能调完整 skill 库——比如用 image generation skill 让 Codex 直接调 GPT Image 生成 UI 素材，然后嵌进前端代码里。**CLI 也能调 skill，但桌面端更直观**。

**能力 3：Automations（后台自动化）**

桌面端支持"自动化"任务——Issue 分类、CI 监控、告警响应，**有结果会推送到收件箱**。人不需要一直盯。

**我自己的桌面端工作流**：

- 主屏开 1 个长期跑的项目（Codex 自动跑测试 + 部署）
- 副屏开 2-3 个 worktree（不同 feature 分支）
- 通知栏接 Automations 推送

**适合谁**：同时推进多任务、需要 team 协作、想让 routine 工作 AI 化的独立开发者。

### 线 3：Codex VS Code 扩展

跟 Claude Code 的 VS Code 体验几乎一样——**侧边栏 Chat + Agent 模式 + Diff 预览 + 终端执行**。

**优势**：

- 在 IDE 里直接用，**学习成本最低**
- 实时代码补全（不是 agent 模式而是 inline 补全）
- 跟现有 VS Code 生态（extensions / themes / keybindings）兼容

**劣势**：

- 没法跑 worktree 并行
- 没法做完整的多 Agent 编排
- 必须开 VS Code 才用

**我的用法**：日常小改动（改个 bug、写个 component、调个 CSS）用 VS Code 扩展，**长任务用 CLI，长 + 多任务用 Desktop**。

### 线 4：Codex Web / Cloud（云端任务）

打开浏览器 → chatgpt.com/codex → 直接描述任务。**任务跑在 OpenAI 云端**，可以关闭电脑等通知。

**典型场景**：

- 跑 2-3 小时的迁移任务，去睡觉
- 早上起来看 Codex 自动生成的 PR
- 多人协作（把任务 URL 分享给队友）

**成本**：按 token 算，**2 小时任务可能 $5-$20**。比本地略贵，但**换来的是不用守在电脑前**。

Notion 的资深工程师 **会设置 Codex agent 夜间跑任务，有时连续 8 小时**。这是 Claude Code 至今没原生支持的场景。

## 3 个值得知道的第三方工具

OpenAI 官方 4 条线已经很完整，但**社区冒出了 3 个真正值得知道的工具**——分别解决不同问题。

### 工具 1：Codex++（国内开发者用 DeepSeek 跑 Codex）

**github.com/BigPizzaV3/CodexPlusPlus**（Stars 不多但活跃）。

**解决的问题**：用第三方 API 跑 Codex（DeepSeek / GLM / Qwen / Kimi / MiniMax），**成本降到官方的 1/10**。

**安装**：

1. 选对应系统的 release
2. 安装（提供 Windows / Mac / Linux 安装包）
3. 买 DeepSeek token（platform.deepseek.com）
4. 配到 Codex++ 设置里

**实测成本对比**（单月重度使用）：

- OpenAI 官方：$200-$400
- Codex++ + DeepSeek：$15-$30
- **节省 90%+**

**适合谁**：国内独立开发者、预算敏感、对数据出境有要求。

### 工具 2：OpenCode（开源阵营的旗舰）

**opencode.ai**（GitHub 14 万 star，月活 650 万开发者）。SST 团队（Serverless Stack 那个）用 Go 写。

**跟 Codex CLI 的 3 个核心区别**：

**区别 1：模型自由度**

OpenCode 支持 **75+ 模型提供商**——Anthropic / OpenAI / Google / Mistral / Groq / OpenRouter / Ollama（本地）。你甚至可以同一个项目里"用 Claude Sonnet 4.5 写代码，用 DeepSeek 跑 review"。

**区别 2：零订阅费**

OpenCode 本身 MIT 协议完全免费。费用只取决于用哪个模型的 API。**接 Copilot 认证或免费 tier 的模型，零成本**。

**区别 3：TUI 体验**

OpenCode 终端界面用 Bubble Tea 框架做的，体验相当流畅。**内置 Build 和 Plan 两个 agent，Tab 键切换**——Plan 模式只分析不改代码，**适合先让 AI 出方案再决定要不要执行**。

**我自己的用法**：

- 测试新模型（接 Claude 4.5 Opus / Gemini 3 Pro）
- 需要非 OpenAI 模型的项目（用 Claude 做 review）
- 学习 / 研究项目（不想花 token 钱）

**安装**：

```bash
curl -fsSL https://opencode.ai/install | bash
# 或
brew install anomalyco/tap/opencode
```

### 工具 3：OpenClaw（把 Codex 变成你的私人助理）

**OpenClaw 的定位不是 coding agent**，是跨平台个人 AI 助手框架。核心思路是通过 WhatsApp / Telegram / Slack / Discord / 微信等消息渠道跟 AI agent 交互。

**架构**：

- 本地跑一个 Gateway 进程
- WebSocket 连接各种消息渠道
- Agent 后端可以调 Codex、Claude Code 等

**安装**：

```bash
npm install -g openclaw@latest
openclaw onboard --install-daemon
```

**用 OpenClaw 编排 Codex**：

```bash
# 在 OpenClaw 中调度 Codex 做后台任务
bash pty:true workdir:~/project background:true \
  command:"codex --yolo exec 'Build a REST API for todos'"
```

**这个组合的意义**：你可以在**手机上通过 WhatsApp 给 agent 布置编程任务**，它在服务器上用 Codex 执行，**完成后推送通知给你**。真正的异步 coding workflow。

**适合谁**：折腾能力强、想深度定制 AI 工作流的开发者。**学习曲线陡**，安全设置需要注意（默认 Gateway 开放，**必须做认证配置**）。

## 第三方工具横评

| 工具 | 解决什么问题 | 模型选择 | 成本 | 学习曲线 |
|------|----------|---------|------|---------|
| Codex++ | 国内 + 便宜 | OpenAI + 国产 | 极低 | 低 |
| OpenCode | 多模型 + 零订阅 | 75+ 提供商 | 按 API | 中 |
| OpenClaw | 移动端 + 异步 | 后端 agent | 取决于后端 | 高 |

**这三者不冲突，可以组合**：

- **日常开发**：Codex CLI（主力）
- **省钱场景**：Codex++ 接 DeepSeek
- **测试新模型 / 多模型协作**：OpenCode
- **远程异步任务**：OpenClaw + Codex

## 决策树：怎么选

我自己做了个简单决策树，新手可以直接照搬：

```
问：你现在要做什么？

Q1: 写代码、改 bug、跑测试？
├─ 是 → 单文件小改用 VS Code 扩展
│        跨文件重构用 Codex CLI
│        多任务并行用 Codex Desktop
│
Q2: 跑长任务（>30 分钟）？
├─ 是 → 离开电脑用 Codex Web
│        不离开电脑用 Codex CLI exec
│
Q3: 想用非 OpenAI 模型？
├─ 是 → OpenCode（多模型）+ 选 Claude / Gemini / 本地
│
Q4: 在手机上布置任务？
├─ 是 → OpenClaw + Codex 后端
│
Q5: 预算敏感 / 数据出境限制？
├─ 是 → Codex++ + DeepSeek / GLM
```

## 反代成 API：把订阅额度榨干

这是一个**灰色但很多人用的技巧**——把 ChatGPT 订阅的 Codex 额度反代成 OpenAI 兼容 API，给 Cursor / Windsurf / Cline 等其他工具用。

**方案 A：config.toml 自定义 Provider**

```toml
# ~/.codex/config.toml
model = "gpt-5.4"
model_provider = "proxy"

[model_providers.proxy]
name = "My LLM proxy"
base_url = "http://proxy.example.com"
env_key = "OPENAI_API_KEY"
wire_api = "responses"
```

**方案 B：CLIProxyAPI**

**github.com/router-for-me/CLIProxyAPI**（Go 项目）。把 Codex / Claude Code / Gemini CLI 的 OAuth 认证封装成 OpenAI 兼容 API 端点。

```bash
git clone https://github.com/router-for-me/CLIProxyAPI.git
cd CLIProxyAPI
make run
```

启动后你的 Cursor 配置：

```
Base URL: http://localhost:8317/v1
Model: gpt-5-codex
```

**就能用 ChatGPT 订阅的额度调 Codex 模型**，不需要额外 API 费用。

**方案 C：codex-lb 负载均衡**

**codex-lb**——专门做 Codex 负载均衡代理，支持多账号轮转、WebSocket 转发、用量追踪。**适合团队场景**，多个开发者共享几个 Codex 账号。

**风险提示**：

- 反代使用本质是灰色地带
- OpenAI TOS 没明确态度，**但理论存在账号风控风险**
- 个人使用问题不大
- **大规模商业化搞这个不推荐**

## 国外独立开发者的真实选型

我扒了一圈 Reddit r/ClaudeCode / r/Codex / r/LocalLLama / Hacker News，**总结出 2026 年国外独立开发者的主流选型**：

**类型 1：纯终端党（40%）**

- 主力：Codex CLI
- 备选：Claude Code CLI
- 工具：tmux + nvim + fzf + ripgrep
- 优势：极轻量、跟 shell 工具链完全兼容
- 劣势：可视化差、批量改不直观

**类型 2：IDE 党（30%）**

- 主力：Cursor / Codex VS Code
- 备选：JetBrains + AI 插件
- 工具：VS Code / JetBrains
- 优势：可视化好、改动直观
- 劣势：资源占用大、跑多任务不便

**类型 3：多 Agent 党（20%）**

- 主力：Codex Desktop
- 备选：Claude Code + worktree 脚本
- 工具：git worktree + iTerm2
- 优势：能并行多个 feature
- 劣势：必须用 Desktop App

**类型 4：远程异步党（10%）**

- 主力：Codex Web / OpenClaw
- 备选：GitHub Actions 触发 Codex
- 工具：手机 + 云服务器
- 优势：24/7 不用守在电脑前
- 劣势：调试不便、成本偏高

**Notion 工程师的真实选择**：

- 初级 / 简单任务 → Claude Code（"擅长预判意图，需求不精准也能执行"）
- 资深 / 长任务 → Codex（"擅长复杂、耗时任务，夜间跑 8 小时"）
- 共存策略：不同任务用不同工具，**不绑定单一**

## 1 个我自己的最佳实践

我自己 6 个月的组合拳：

**主工作流（80% 时间）**：

- **日常写代码**：Codex VS Code 扩展
- **跨文件重构**：Codex CLI（auto-edit 模式）
- **长任务 / 跑测试**：Codex CLI exec 模式 + cron
- **多任务并行**：Codex Desktop（3-5 个 worktree 同时跑）

**省钱 / 备选**：

- **预算敏感任务**：Codex++ + DeepSeek
- **需要 Claude review**：OpenCode 接 Anthropic
- **远程布置任务**：OpenClaw + Codex

**核心原则**：

- 单一任务用最轻量工具（VS Code / CLI）
- 复杂任务用最强工具（Desktop / Web）
- 不同模型用不同工具（Codex = OpenAI 模型 / OpenCode = 其他）
- **永远不绑死在一个工具上**——**Notion 工程师的共存策略是正解**

## 我的判断

**短期（3-6 个月）**：Codex 4 条官方线 + OpenCode / OpenClaw 形成稳定生态。**选型决策看任务类型，不看工具品牌**。

**中期（6-12 个月）**：第三方反代 API 工具成熟，**Codex 订阅变成"通用 AI token"**——能驱动多个 IDE 和 CLI。

**长期（12+ 个月）**：agent OS 概念成熟后，**4 条线 + 3 个平替会融合成 1-2 个产品**。但**多入口共存**仍是主流（不同场景需要不同 UX）。

下一章讲 AGENTS.md + Skills 最佳实践——国外独立开发者沉淀出来的"个人 ECC"系统。