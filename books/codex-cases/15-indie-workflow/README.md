# 15. 独立开发者 Codex 工作流模板：5 套真实可复制

最后一章给你 5 套**国外独立开发者真实在跑**的 Codex 工作流——**复制 prompt + 配置 + 步骤**。这一章是"工具书"，**打开就能用**。

## 工作流 1：截图转页面（视觉闭环）

**适用场景**：把设计稿 / 截图 / 参考图直接变成项目里的页面。

**前置**：

- 项目已建好，有 AGENTS.md
- 装好 Playwright MCP（可选，用 Codex 浏览器也行）
- 截图保存到 `./references/` 或 `./screenshots/`

**完整 prompt 模板**：

```markdown
请基于以下截图实现当前项目页面。

## 输入
- 截图：./references/home-desktop.png
- 截图：./references/home-mobile.png
- 项目根：/Users/me/projects/my-app

## 要求
1. 先阅读项目结构（AGENTS.md / package.json / src/ 目录）
2. 实现页面，**优先复用现有组件和设计 token**
3. 跑 lint / typecheck / build
4. 启动 dev server
5. 用 Playwright 打开，桌面 1440 + 移动 375 各截图
6. 对比参考图和当前截图
7. 修正明显差异
8. 输出报告：改了哪些文件、哪些是推断的、哪些需要人工确认

## 不要做
- 不要重构无关代码
- 不要新增设计 token（用项目里现有的）
- 不要修改路由结构
```

**执行命令**：

```bash
codex --sandbox workspace-write \
       --ask-for-approval on-request \
       -i ./references/home-desktop.png \
       -i ./references/home-mobile.png \
       chat "请基于以上截图实现当前项目首页..."

# 第二轮（自动修复）
codex resume --last \
  -i ./references/target.png \
  -i ./screenshots/current.png \
  chat "第一张是目标图，第二张是当前实现。请对比差异，只修复视觉差异。"
```

**实测时间**：

- 简单页面（首页 / 落地页）：**5-10 分钟**
- 中等页面（dashboard / list）：**15-30 分钟**
- 复杂页面（多状态 / 表单 / 图表）：**30-60 分钟**

**关键技巧**：

- 截图越丰富结果越准——**多状态覆盖**（hover / empty / loading / mobile）
- 第一遍"先别写代码，先分析"——**发现遗漏**
- 第二遍"按计划实现"——**保证范围**
- 第三遍"对比修复"——**视觉闭环**

## 工作流 2：Bug 排查（4 步定位）

**适用场景**：线上 bug、本地报错、测试 fail。

**4 步 prompt 模板**：

### 步骤 1：定位范围

```bash
codex chat "[报错信息或现象]

请基于以上信息排查。

工作方式：
- 先不要改代码
- 找到可能相关的页面、组件、状态管理、接口请求和样式文件
- 说明最可能的 2-3 个原因
- 如果可以运行项目，请尝试复现
- 确认根因后，做最小修改
- 修改后运行相关检查
- 最后说明根因、改动文件、验证方式"
```

### 步骤 2：跑测试复现

```bash
codex resume --last "用 run-tests skill 跑全量测试，确认 bug 可复现"
```

### 步骤 3：最小修改

```bash
codex resume --last "用 debug-investigator skill 给出最小修改方案"
```

### 步骤 4：验证 + 报告

```bash
codex resume --last "用 run-tests skill 跑全量测试，确认修复。
输出：
- 根因
- 改动文件
- 验证命令和结果
- 未验证项
- 剩余风险"
```

**关键技巧**：

- **给 Codex 清晰的错误范围**——日志 + 报错 + 复现步骤
- **不要只说"代码不工作了"**
- 多次迭代用 `codex resume --last` 保留上下文
- **关键 bug 用 review skill 再过一遍**

**实测数据**：

- 一般 bug：**10-20 分钟定位 + 修复**
- 难 bug（N+1 / 竞态 / 内存泄漏）：**30-60 分钟**
- 极端 bug（生产环境偶发）：**2-4 小时**

## 工作流 3：大重构（4 层递进）

**适用场景**：组件重构、目录结构改造、API 升级。

**关键心法**：

> 越是模糊、跨模块、影响面大的任务，越应该先让它规划、定位、确认边界，再让它改代码。

**4 层 prompt 模板**：

### 层 1：理解现状

```bash
codex chat "我准备重构当前项目的 [具体目标]。

先不要改代码。请输出：
1. 当前 [相关结构] 的目录和主要职责
2. 重复代码和可抽象点
3. 高风险文件
4. 推荐的目标结构
5. 分阶段迁移计划
6. 每阶段的验证方式
7. 哪些地方不建议现在动"
```

### 层 2：识别风险

```bash
codex resume --last "用 review skill 审查建议的重构方案。重点检查：
- 破坏性变更
- 性能回退
- 类型风险
- 测试覆盖
- 文档更新"
```

### 层 3：制定迁移计划

```bash
codex resume --last "把方案拆成 5-8 个 PR 任务，每个 PR 限制 < 400 行。
输出每个 PR 的：
- 改动范围
- 验证方式
- 风险等级
- 估计时间
- 依赖关系"
```

### 层 4：分批执行

```bash
# 第一个 PR
codex chat "执行 PR 1：[任务描述]
要求：
- 不超出范围
- 跑全量测试
- 用 commit-msg skill 写 commit
- 创建 GitHub PR
- 输出报告"

# 第二个 PR
codex chat "执行 PR 2：[任务描述]
[同上]"
```

**关键技巧**：

- **PR 限制 < 400 行**——超过这个数字 review 难度指数级上升
- **每个 PR 跑全量测试**——避免"重构破坏老功能"
- **用 git worktree 隔离**——可以并行 review + 修复
- **CI 跑 lint / typecheck / test**——不要本地跑完就推

**实测数据**：

- 中型重构（50 个文件）：**1-2 周**
- 大型重构（200+ 个文件）：**3-4 周**
- 单 PR 平均 200-400 行

## 工作流 4：CI/CD + Git 自动化

**适用场景**：自动 PR review、自动 issue triage、自动 changelog、自动部署。

**前置**：

- 仓库有 GitHub Actions workflow 配置
- OpenAI API key 在 secrets 里

**4 个工作流模板**：

### 模板 1：自动 PR Review

`.github/workflows/codex-review.yml`：

```yaml
name: Codex Auto Review
on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  codex-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Run Codex Review
        uses: openai/codex-action@v1
        with:
          api-key: ${{ secrets.OPENAI_API_KEY }}
          prompt: |
            Review this PR for:
            1. 安全漏洞（OWASP Top 10）
            2. 性能问题（N+1 查询、内存泄漏）
            3. 代码风格（项目 ESLint / Prettier 配置）
            4. 测试覆盖（新增功能必须有测试）
            5. AGENTS.md 规则遵守
            
            输出格式：
            - 严重问题（必须修）：列表 + 行号
            - 建议改进（可选）：列表
            - 优点：列表
          model: gpt-5.5
        timeout-minutes: 10
```

### 模板 2：自动 Issue Triage

`.github/workflows/codex-triage.yml`：

```yaml
on:
  issues:
    types: [opened]

jobs:
  classify:
    runs-on: ubuntu-latest
    steps:
      - name: Codex Issue Triage
        uses: openai/codex-action@v1
        with:
          api-key: ${{ secrets.OPENAI_API_KEY }}
          prompt: |
            分析这个 GitHub Issue：
            
            1. 分类：bug / feature / docs / question
            2. 优先级：P0 / P1 / P2 / P3
            3. 推荐 owner
            4. 复现步骤（如果是 bug）
            5. 估计工作量（S / M / L / XL）
            
            输出 JSON
          model: gpt-5.5-mini
```

### 模板 3：自动 Changelog

`.github/workflows/changelog.yml`：

```yaml
on:
  release:
    types: [created]

jobs:
  changelog:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Codex Generate Changelog
        run: |
          npx codex chat "从上次 release 到这次的所有 PR，
          生成 CHANGELOG.md
          按 Conventional Commits 分类：feat / fix / perf / docs / chore
          中文输出，简洁（每条 < 30 字）" > CHANGELOG.md
          git config user.name "codex-bot"
          git config user.email "codex@example.com"
          git add CHANGELOG.md
          git commit -m "chore: auto-generate changelog"
          git push
```

### 模板 4：自动部署

`.github/workflows/deploy.yml`：

```yaml
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4
      
      - name: Codex Pre-deploy Check
        run: |
          npx codex chat "检查：
          1. 全量测试通过
          2. lint 通过
          3. typecheck 通过
          4. 数据库迁移就绪
          
          全部通过才继续，否则报错"
      
      - name: Deploy
        run: ./scripts/deploy.sh production
      
      - name: Codex Smoke Test
        run: |
          npx codex chat "部署后跑 5 个核心 API：
          - POST /api/auth/login
          - GET /api/users/me
          - GET /api/dashboard
          - POST /api/upload
          - DELETE /api/cache
          
          全通过才成功"
```

**实测收益**（6 个月数据）：

- 每周省 5-8 小时
- 严重 bug 漏出率 8% → 1.5%
- 部署失败率 12% → 2%
- **发布节奏从"周发布"加速到"日发布"**

## 工作流 5：远程异步编程（24/7 AI 工程师）

**适用场景**：长任务 / 夜间跑 / 移动端布置。

**核心架构**：

```
手机/电脑
  ↓ (WhatsApp / Telegram / OpenClaw / Web)
云服务器 (Codex)
  ↓ (跑任务)
GitHub / 通知
```

**5 步配置**：

### 步骤 1：云服务器准备

```bash
# 16 核 + 64GB 内存 + 200GB 存储
# 海外：Vultr / DigitalOcean（$96/月起）
# 国内：阿里云 / 腾讯云（$60/月起）

ssh user@server
curl -fsSL https://opencode.ai/install | bash
npm install -g @openai/codex
```

### 步骤 2：长任务定义

```bash
# /home/user/.codex/long-tasks/nightly-migration.toml
[task]
name = "nightly-migration"
description = "把 user 表的 email 字段从 varchar(255) 迁移到 citext"

[steps]
run_at = "02:00"  # 低峰期
backup_before = true
max_retries = 3
notify_on = ["success", "failure"]
```

### 步骤 3：Cron 触发

```bash
crontab -e

# 每天凌晨 2 点跑迁移任务
0 2 * * * cd /home/user/project && npx codex long-task /home/user/.codex/long-tasks/nightly-migration.toml
```

### 步骤 4：远程通知

```bash
# 装飞书 CLI / Telegram Bot / Slack Webhook
# 任务完成后自动推送到手机

npx codex long-task ... --notify "feishu://chat_id=xxx"
```

### 步骤 5：手机查看

```
[2026-06-26 02:35] Codex 完成 nightly-migration
- 耗时：35 分钟
- 改动：迁移 email 字段
- 验证：完整性检查通过
- 备份：/home/user/backups/2026-06-26.sql
- PR：https://github.com/me/my-app/pull/123

[打开 PR] [查看 diff] [批准 merge] [回滚]
```

**实测数据**（Notion 工程师）：

- 8 小时长任务：**常见**（Codex Web / OpenClaw）
- 月成本：$100-300（含云服务器 + API）
- 解放时间：**每天 2-3 小时**

## 5 套工作流的"组合拳"

**实际项目里很少只用 1 套**。**5 套组合用**：

```
周一早上
  ├─ 9:00 飞书提醒"今天要做的 5 件事"
  ├─ 10:00 工作流 1（截图转页面）
  ├─ 11:30 工作流 2（Bug 排查）
  └─ 12:00 午休

周一下午
  ├─ 14:00 工作流 3（大重构）
  ├─ 16:00 Codex 持续 review 我下午的 commit
  └─ 18:00 下班

周一晚上（远程）
  ├─ 20:00 用 OpenClaw 远程布置"夜间迁移任务"
  ├─ 22:00 睡觉
  └─ Codex 跑 8 小时长任务

周二早上
  ├─ 7:00 起床看 Codex 通知
  ├─ 8:00 review 夜间 PR
  ├─ 8:30 批准 + 部署
  └─ 工作流 4 自动跑（CI/CD + Git 自动化）
```

**这套节奏的产出**：

- 每天 5-8 小时手写代码
- 每天 8-12 小时 Codex 跑后台
- **总产出 = 一个人 × 3 倍**

## 1 个真实工作流：Codex 8 个月的心得

我自己用 Codex 8 个月总结的"日常节奏"：

**早间 30 分钟**：

```bash
# 1. 看 Codex 昨晚的 long-task 结果
codex task list --recent

# 2. Review 待合并的 PR
codex --profile review chat "请审查 open PRs"

# 3. 跑全量测试
codex --profile cheap chat "用 run-tests skill 跑全量测试"

# 4. 看昨天 commit
codex chat "用 commit-msg skill 总结昨天所有 commit"
```

**上午 3 小时**：

- 写新功能（用 Codex VS Code 扩展）
- 修 bug（用 Codex CLI + worktree）
- **Codex 持续辅助**

**午间 30 分钟**：

- 远程布置"下午长任务"——**不在本地跑**（笔记本散热顶不住）

**下午 3 小时**：

- 重构（用 Codex Desktop 多 worktree）
- review Codex 跑的 PR

**晚间 30 分钟**：

- 提交当天 commit
- 跑 nightly long-task（迁移 / 备份 / 监控）
- 设置明天任务

**周末 2 小时**：

- 整理 skill 库（哪些用得多、哪些可以删）
- 写新 skill（重复 3 次的任务）
- 升级 AGENTS.md

## 1 个我自己的真实心路历程

**第 1 个月**：把 Codex 当 Claude Code 的替代品。**结果**：撞墙（不会用 AGENTS.md / 不会用 Skills / 撞 spawn_agent 的坑）。

**第 2-3 个月**：学 AGENTS.md + Skills。**结果**：撞 spawn_agent 协同 + 上下文丢失的墙。

**第 4-5 个月**：上 CodexLoop + Codex Desktop。**结果**：撞 token 成本 + 长任务失忆的墙。

**第 6-7 个月**：稳定期。**结果**：5 套工作流固化，月成本 $80-150。

**第 8 个月**：开始用 Codex++ + DeepSeek 省钱 + OpenCode 多模型。**结果**：月成本降到 $50-80。

**关键转折**：

- 撞墙 1-2 次不可怕——**继续迭代 prompt + skill**
- 第 3 次撞墙就该**换策略**（不是换工具，是换方法）
- 6 个月后基本稳定——**这套组合能跑 1-2 年不重做**

## 我的最终判断

**独立开发者在 2026 年的"标准配置"**：

**工具层**：

- Codex CLI（主力）
- Codex Desktop（多任务）
- Codex Web（远程）
- Codex++ + DeepSeek（省钱）

**技能层**：

- AGENTS.md（项目级 + 个人级）
- 10-20 个 Skill
- 5-8 个 MCP

**工作流层**：

- 5 套固定流程（截图 / Bug / 重构 / CI/CD / 远程）
- 个人 ECC 系统
- CodexLoop 长任务管理

**预算**：

- 月成本 $50-150
- 时间回报 3-5 倍

**这套配置的核心原则**：

- 工具**不绑死**——按任务选
- Skill **常更新**——重复 3 次就沉淀
- 长任务 **有 Plan**——不直接让 AI 开干
- 远程 **不守电脑**——夜间任务跑 8 小时

**未来 6-12 个月**：

- Codex + Skill + MCP 三件套继续成熟
- **独立开发者 = 1 个小团队**会成为新常态
- **不上车 = 落后同行 1-2 年**

## 写在最后

这套 15 章系列，从 Codex 2026 大爆发开始，到独立开发者 8 个月心路历程收尾。

**15 章回顾**：

- 01-05：Codex 基础（范式 / 爆发 / AGENTS.md / CodexLoop / 多 Agent）
- 06-10：Codex 实战（Computer Use / CI/CD / 飞书 CLI / AIGrader / 未来）
- 11-15：Codex 深入（工具生态 / Skills / MCP / 横评 / 工作流模板）

**独立开发者的最终心法**：

- 工具是杠杆——**杠杆能放大你的能力，不能替代你的能力**
- Skill 是肌肉——**重复 3 次就沉淀成肌肉记忆**
- Workflow 是系统——**5 套工作流跑顺了就是你的"个人 ECC"**
- **去写吧，别等了**——**未来 6 个月不上车，就落后同行 1-2 年**

**Codex 实战 15 章系列**——**结束**。