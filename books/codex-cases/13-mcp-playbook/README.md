# 13. Codex + MCP 完整实战：把外部世界接进你的 agent

MCP（Model Context Protocol）2025 年 11 月由 Anthropic 推出，到 2026 年 5 月已经有 **9,723 个服务器、1.2 亿月下载**。这一章讲清楚 Codex + MCP 的完整实战——最常用的 8 个 MCP、配置方法、组合策略、避坑。

## MCP 是什么

MCP 是 **Agent 工具调用的 USB-C**。类比一下：

- USB-C 之前：每个设备一根线
- MCP 之前：每个 AI 工具写一套插件
- USB-C / MCP 之后：**一次编写，到处运行**

**核心价值**：

- 一次编写，**Claude Code / Codex CLI / Cursor / Windsurf 都能调同一个 MCP 服务器**
- 不用为每个 AI 工具单独写插件
- 生态共享——MCP 服务器可以发布到 registry，**像 npm 包一样安装**

## Codex CLI 装 MCP 的 3 种方式

### 方式 1：CLI 命令装（最简单）

```bash
codex mcp add <name> -- <command> [args...]
```

**示例**：

```bash
# 装 Context7（最新文档查询）
codex mcp add context7 -- npx -y @upstash/context7-mcp

# 装 Figma
codex mcp add figma -- npx -y @modelcontextprotocol/server-figma

# 装 GitHub
codex mcp add github -- npx -y @modelcontextprotocol/server-github
```

### 方式 2：配置文件（推荐）

在 `~/.codex/config.toml` 里：

```toml
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

[mcp_servers.feishu]
command = "/usr/local/bin/lark"
args = ["mcp"]
```

**环境变量从 `${VAR_NAME}` 读取**，**不在配置文件里 hardcode**。

### 方式 3：项目级 .codex/mcp.json

跟 `package.json` / `tsconfig.json` 一样，**项目级 MCP 配置可以随代码 commit**：

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

**好处**：新人 clone 仓库后，**MCP 自动就绪**，不用手动配。

## 8 个最常用 MCP（2026 独立开发者实测）

按"使用频率"和"价值密度"排：

### MCP 1：Context7（最新文档查询）

**解决的问题**：Codex 训练数据滞后，**官方文档更新比模型快**。

**安装**：

```bash
codex mcp add context7 -- npx -y @upstash/context7-mcp
```

**实战 prompt**：

```bash
codex chat "用 Context7 查 Next.js 15 的 Server Actions 文档，
然后实现一个表单提交 action。
要求：
- 包含 Zod 校验
- 错误处理
- 成功后 revalidatePath
"
```

**效果**：

- 不用 Codex 训练数据里的旧 API
- 实时查官方文档最新写法
- **避免"AI 用过时 API 写代码"的常见坑**

**适用场景**：

- 用新版本框架（Next.js 15 / React 19 / Vue 3.5）
- 查小众库的最新用法
- 看官方 changelog

**GitHub**：github.com/upstash/context7

### MCP 2：Figma（设计稿转代码）

**解决的问题**：设计师出 Figma → 你手动写代码。**Figma MCP 让 Codex 直接读 Figma 节点树**。

**安装**：

```bash
codex mcp add figma -- npx -y @modelcontextprotocol/server-figma
export FIGMA_TOKEN="figd_xxx"
```

**实战 prompt**：

```bash
codex chat "用 Figma MCP 读 https://figma.com/file/XXX/XXX，
读 'Login Screen' frame，然后实现 React 组件。
要求：
- 用项目里的设计 token
- 保持响应式
- 跑 typecheck + build 验证
- 用 Playwright 截图对比"
```

**效果**：

- 不再"看图写代码"——**Codex 直接读 Figma 节点树**
- 设计师改 Figma → Codex 重读 → 自动更新代码
- **设计到代码的延迟从天降到分钟**

**适用场景**：

- 跟设计师紧密协作
- 设计系统迭代频繁
- 想把"实现 UI"完全自动化

**GitHub**：github.com/modelcontextprotocol/servers（figma 子目录）

### MCP 3：GitHub（PR / Issue 操作）

**解决的问题**：Codex 直接读 PR diff、看 issue、评论、merge。

**安装**：

```bash
codex mcp add github -- npx -y @modelcontextprotocol/server-github
export GITHUB_TOKEN="ghp_xxx"
```

**实战 prompt**：

```bash
# 列出未读 issue
codex chat "用 GitHub MCP 列出仓库所有 open issues，按优先级排序"

# review PR
codex chat "用 GitHub MCP 读 PR #123 的 diff，给出 review 意见"

# 创建 PR
codex chat "用 GitHub MCP 创建 PR，从 feature/login 到 main，标题用 Conventional Commits 格式"
```

**适用场景**：

- 日常 GitHub workflow
- 自动 PR review
- Issue triage

**GitHub**：github.com/modelcontextprotocol/servers（github 子目录）

### MCP 4：PostgreSQL（直接查数据库）

**解决的问题**：Codex 直接查数据库，不用你来回 copy 数据。

**安装**：

```bash
codex mcp add postgres -- npx -y @modelcontextprotocol/server-postgres
export DATABASE_URL="postgresql://user:pass@host:5432/db"
```

**实战 prompt**：

```bash
# 查数据
codex chat "用 postgres MCP 查 user 表最近 24 小时的注册数据，按小时分组"

# 写 SQL
codex chat "用 postgres MCP 帮我写一个查询，找出 30 天没登录的用户"

# Schema 分析
codex chat "用 postgres MCP 分析 orders 表的索引使用情况"
```

**安全边界**：

- **只读查询优先**——别让 Codex 直接 DELETE / UPDATE
- 用单独 read-only 数据库账号
- 敏感字段（密码、token）**别查**

**GitHub**：github.com/modelcontextprotocol/servers（postgres 子目录）

### MCP 5：飞书 CLI（中文办公）

第 8 章详细讲过。这里给完整配置。

**安装**：

```bash
# 装飞书 CLI
npm install -g @larksuite/cli

# 加到 Codex MCP
codex mcp add feishu -- lark mcp
```

**实战 prompt**：

```bash
codex chat "用飞书 CLI 给我发一条测试消息"
codex chat "用飞书 CLI 创建多维表格，表头：日期 / SEO 检查 / 备注"
codex chat "用飞书 CLI 把今天完成的 commit 总结发到群里"
```

**GitHub**：github.com/larksuite/cli

### MCP 6：Playwright（浏览器自动化）

**解决的问题**：Codex 直接控制浏览器，**截图 / 点击 / 表单提交**。

**安装**：

```bash
codex mcp add playwright -- npx -y @modelcontextprotocol/server-playwright
```

**实战 prompt**：

```bash
# 截图对比
codex chat "用 Playwright 打开 http://localhost:3000，
桌面 1440px 和移动 375px 各截一张图。
保存到 ./screenshots/ 目录"

# E2E 测试
codex chat "用 Playwright 跑完整登录流程：
1. 打开登录页
2. 填表单
3. 提交
4. 验证跳转到 dashboard
5. 截图每个步骤"

# 抓数据
codex chat "用 Playwright 打开 https://news.ycombinator.com，
抓前 30 条新闻的标题 + 链接 + 分数，存到 markdown"
```

**适用场景**：

- 视觉回归测试
- E2E 自动化
- 数据抓取（**注意 robots.txt**）
- 跨页面测试

**GitHub**：github.com/microsoft/playwright-mcp

### MCP 7：Filesystem（文件操作）

**解决的问题**：Codex 跨目录操作文件，**比单项目 CLI 更灵活**。

**安装**：

```bash
codex mcp add filesystem -- npx -y @modelcontextprotocol/server-filesystem
```

**实战 prompt**：

```bash
# 批量重命名
codex chat "用 filesystem MCP 把 ~/Downloads 里所有 .jpeg 改成 .jpg"

# 跨项目搜索
codex chat "用 filesystem MCP 在 ~/projects 找所有 package.json，
提取所有用 TypeScript 的项目"

# 整理目录
codex chat "用 filesystem MCP 把 ~/Downloads 按文件类型分类到子目录：
图片 / 文档 / 视频 / 其他"
```

**安全边界**：

- **必须配 allowed_paths**——不要让 Codex 读整个硬盘
- 不要给 root 权限

```toml
[mcp_servers.filesystem]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/Downloads", "/Users/me/projects"]
```

**GitHub**：github.com/modelcontextprotocol/servers（filesystem 子目录）

### MCP 8：Puppeteer（替代 Playwright）

**Playwright 之外的浏览器自动化选择**。**对老项目 / 简单抓取更友好**。

**安装**：

```bash
codex mcp add puppeteer -- npx -y @modelcontextprotocol/server-puppeteer
```

**用法**跟 Playwright 几乎一样。**选 Playwright 还是 Puppeteer 看团队习惯**。

## MCP 组合策略

**真实场景很少只用 1 个 MCP**。我自己的高频组合：

### 组合 1：Context7 + Playwright（学习新框架）

```bash
codex chat "用 Context7 查 Next.js 15 文档，实现一个 todo list 页面。
要求：
- 用 Server Actions
- 跑 typecheck
- 用 Playwright 打开页面，桌面 + 移动各截图
- 跑 lint + build 验证"
```

**3 个 MCP 各司其职**：Context7 给最新文档 / Codex 写代码 / Playwright 验证。

### 组合 2：Figma + Playwright（设计稿转代码 + 验证）

```bash
codex chat "用 Figma MCP 读 'Dashboard' frame，
实现 React 组件。
要求：
- 用项目设计 token
- 跑 typecheck + build
- 用 Playwright 打开，跟 Figma 截图对比
- 修正差异
- 最后输出报告"
```

### 组合 3：Postgres + GitHub（数据库 + 仓库联动）

```bash
codex chat "用 postgres MCP 查 user 表最近 7 天的活跃用户数，
跟 GitHub MCP 上周 commit 数对比，
输出 '活跃用户 vs 提交频率' 报告"
```

### 组合 4：飞书 CLI + Filesystem（办公 + 文件）

```bash
codex chat "用 filesystem MCP 读 ~/reports/ 这个月所有周报，
提取关键指标，
用飞书 CLI 发到团队群"
```

## MCP 性能与成本

**性能数据**（国外独立开发者实测）：

| MCP | 启动时间 | 单次调用延迟 | 影响 Codex 速度 |
|-----|---------|------------|----------------|
| Context7 | 2-3s | 200-500ms | 小 |
| Figma | 3-5s | 500-1500ms | 中 |
| GitHub | 2-3s | 300-800ms | 小 |
| Postgres | 1-2s | 50-200ms | 极小 |
| Playwright | 5-8s | 1-3s | 大 |
| Filesystem | <1s | 10-50ms | 极小 |
| 飞书 CLI | 1-2s | 100-300ms | 小 |

**关键发现**：

- **Playwright 最慢**——启动浏览器本身就要 5-8 秒
- **不要同时开 5+ MCP**——会拖慢 Codex 启动
- **按需加载**——Codex 支持 `--mcp-config` 指定本次会话用哪些 MCP

```bash
# 只在需要时启用 Playwright
codex --mcp-config ./configs/with-playwright.toml chat "..."
```

## MCP 安全 4 个不要做

MCP 跟 agent 一样，**有 4 个常见安全坑**：

### 不要 1：不要 hardcode token

```toml
# ❌ 错误
[mcp_servers.github]
env = { GITHUB_TOKEN = "ghp_xxxx" }

# ✅ 正确
[mcp_servers.github]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
```

**token 必须从环境变量读**。**commit 到 git = 公开泄露**。

### 不要 2：不要给 root / admin 权限

```toml
# ❌ 错误
[mcp_servers.postgres]
env = { DATABASE_URL = "postgresql://root:pass@host/db" }

# ✅ 正确：read-only 账号
[mcp_servers.postgres]
env = { DATABASE_URL = "postgresql://readonly:pass@host/db" }
```

**MCP 用最窄权限**。**读数据的别给写权限**。

### 不要 3：不要暴露 filesystem 到根目录

```toml
# ❌ 危险
[mcp_servers.filesystem]
args = ["/"]

# ✅ 安全
[mcp_servers.filesystem]
args = ["/Users/me/projects"]
```

**Filesystem MCP 必须限制 allowed_paths**。

### 不要 4：不要在公开材料展示 MCP 输出

**真实 chat_id / open_id / token / 内部 URL 都不应该出现在公开材料**。演示用脱敏数据。

## MCP 调试 3 个技巧

### 技巧 1：开启 MCP 日志

```bash
export CODEX_MCP_DEBUG=1
codex chat "..."
```

**日志写到 ~/.codex/logs/mcp.log**。

### 技巧 2：单 MCP 隔离测试

```bash
# 只启一个 MCP，测试它
codex --mcp-only github chat "列出最近 5 个 PR"
```

### 技巧 3：MCP 健康检查

```bash
# 列出已安装的 MCP
codex mcp list

# 检查某个 MCP 状态
codex mcp status github

# 重启 MCP
codex mcp restart github
```

## MCP 替代方案

**不是所有场景都需要 MCP**。如果某个需求很简单，**直接用 Bash / Skill 替代**：

| 需求 | 用 MCP | 替代方案 |
|------|--------|---------|
| 查最新文档 | Context7 | Codex 训练数据（**注意时效**）|
| 读 Figma | Figma MCP | 手动看 Figma + 截图 |
| 查数据库 | Postgres MCP | psql 命令行 |
| 浏览器操作 | Playwright MCP | 写 Playwright 脚本 + 跑 |
| 文件操作 | Filesystem MCP | 写 shell 脚本 |

**判断标准**：

- 任务**经常重复** → 用 MCP（一次配置，永久受益）
- 任务**只跑一次** → 用 shell 脚本（更快）

## 我的 MCP 配置（参考）

`~/.codex/config.toml`：

```toml
model = "gpt-5.4"
model_provider = "openai"
approval_mode = "auto-edit"

# === MCP 配置 ===

[mcp_servers.context7]
command = "npx"
args = ["-y", "@upstash/context7-mcp"]

[mcp_servers.filesystem]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem",
        "/Users/me/projects",
        "/Users/me/Downloads"]

[mcp_servers.postgres]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-postgres"]
env = { DATABASE_URL = "${DATABASE_URL}" }

[mcp_servers.github]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }

[mcp_servers.playwright]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-playwright"]

[mcp_servers.feishu]
command = "lark"
args = ["mcp"]

# === Profile 配置 ===

[profiles.cheap]
model = "deepseek-chat"
model_provider = "deepseek"

[profiles.review]
model = "gpt-5.4"
approval_mode = "suggest"

[profiles.expensive]
model = "gpt-5.4"
approval_mode = "full-auto"
```

**8 个 MCP + 3 个 profile = 我的"个人 ECC 操作系统"**。

## 国外独立开发者的 MCP 选型（按场景）

**场景 1：全栈 Web 开发**

- 必装：Context7 / Playwright / GitHub
- 可选：Postgres / Filesystem
- 用不到：Figma

**场景 2：跟设计师协作**

- 必装：Figma / Playwright
- 可选：Context7
- 用不到：Postgres

**场景 3：数据 / 后端**

- 必装：Postgres / GitHub
- 可选：Filesystem / Context7
- 用不到：Figma / Playwright

**场景 4：移动 App**

- 必装：Filesystem / GitHub
- 可选：Context7
- 用不到：Postgres / Figma

**场景 5：办公自动化（国内）**

- 必装：飞书 CLI / Filesystem
- 可选：Context7
- 用不到：Figma / Postgres

## MCP 2026 趋势

**趋势 1：MCP Registry 成熟**

跟 npm 一样，**MCP 服务器有官方 registry**。发布 / 安装 / 评分 / 付费全流程成熟。

**趋势 2：MCP 性能优化**

启动时间从 5-8s 优化到 1-2s。**常驻进程 + 池化**逐渐成为标准。

**趋势 3：MCP 安全标准化**

OAuth 2.1 标准化、scope 精细化、**审计日志强制化**。**MCP 安全白皮书 2026 Q3 发布**。

**趋势 4：MCP 跨生态**

Claude Code / Codex / Cursor / Windsurf / Gemini CLI 全部支持。**同一 MCP 服务器 5 个工具都能调**。

**趋势 5：垂直 MCP 兴起**

医疗 / 法律 / 金融 / 教育 行业的垂直 MCP。**专业度 = 商业化护城河**。

## 实战 1：Figma 设计稿 → Next.js 组件（完整流程）

```bash
# 1. 装 Figma MCP
codex mcp add figma -- npx -y @modelcontextprotocol/server-figma
export FIGMA_TOKEN="figd_xxx"

# 2. 准备 prompt
cat > /tmp/figma-prompt.md <<'EOF'
用 Figma MCP 读这个设计稿：
https://www.figma.com/file/XXXXX/MyApp?node-id=1234-5678

要实现的 frame: "Dashboard - Desktop" 和 "Dashboard - Mobile"

要求：
1. 用项目里的设计 token（看 src/styles/tokens.css）
2. 复用现有组件（Card / Button / Avatar）
3. 响应式（桌面 1440 / 移动 375）
4. 跑 typecheck + lint + build
5. 用 Playwright 截图对比，桌面 + 移动各一张
6. 报告差异 + 改动文件
EOF

# 3. 跑
codex --sandbox workspace-write \
       --ask-for-approval on-request \
       chat "$(cat /tmp/figma-prompt.md)"
```

**这套流程**：从 Figma 到可运行代码 + 视觉验证，**全程不需要人写一行代码**。

## 实战 2：Context7 + Postgres 写一份数据库迁移

```bash
# 1. 装 Context7 + Postgres MCP
codex mcp add context7 -- npx -y @upstash/context7-mcp
codex mcp add postgres -- npx -y @modelcontextprotocol/server-postgres

# 2. 准备 prompt
codex chat "用 Context7 查 Prisma 最新文档（关于 migration），
用 postgres MCP 看现有 user 表的 schema，
然后：
1. 写一份 migration：把 email 字段从 varchar(255) 改为 citext
2. 生成 Prisma migration 文件
3. 评估影响（数据量 / 索引 / 锁）
4. 给出回滚方案
5. 不实际执行 migration，只生成文件 + 报告"
```

**3 个 MCP 协作**：Context7 给最新文档 / Codex 写 migration / Postgres 查现有 schema。

## 1 个真实坑：MCP 启动慢导致 Codex 反应迟钝

**问题**：装 5+ 个 MCP 后，**Codex 启动慢到无法接受**（10+ 秒）。

**根因**：每个 MCP 启动要 2-5 秒，5 个就 10+ 秒。**Codex 启动时串行加载**。

**解决**：

**方案 A：项目级 MCP 配置**

```json
// .codex/mcp.json（项目根目录）
{
  "mcpServers": {
    "github": { ... },
    "playwright": { ... }
  }
}
```

**只装项目需要的**。**全局配置瘦身**。

**方案 B：--mcp-config 按需**

```bash
codex --mcp-config ./configs/dev.toml chat "..."
codex --mcp-config ./configs/prod.toml chat "..."
```

**不同任务不同 MCP 集**。

**方案 C：用 Skill 代替 MCP**

如果某个 MCP 用得不多，**改成 skill**。Skill 启动开销更小。

**我的经验**：**全局配置不超过 4 个 MCP**。项目级按需加。

## 我的判断

**短期（3-6 个月）**：MCP 成为 Codex 标配。**8 个核心 MCP 是"独立开发者必装"**。

**中期（6-12 个月）**：MCP Registry + 付费 MCP 成熟。**写一个垂直行业 MCP 卖 $20/月**完全可行。

**长期**：**MCP 协议成为 agent 工具调用的事实标准**。**MCP 服务器 = agent 时代的 npm 包**。

下一章讲 Codex vs Claude Code vs Cursor 横评——三种哲学 + 场景选择 + 组合策略。