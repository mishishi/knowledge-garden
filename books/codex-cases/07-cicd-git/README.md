# 07. CI/CD + Git 自动化：Codex 的工程化闭环

Codex 不只是个能写代码的 agent。**真正能改变独立开发者工作流的是它跟 CI/CD + Git 的深度集成**。这一章讲清楚 Codex 在工程化层面的 5 个核心场景、怎么配置、避坑指南。

## 1. 自动 PR Review

Codex 接 GitHub Actions 后，**每个 PR 触发自动 review**。这是我用得最多的场景。

**配置**：在仓库根目录的 `.github/workflows/codex-review.yml` 加：

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
```

**实战数据**：

- 每周 50-80 个 PR 触发
- 平均 4-7 分钟 review 完成
- **抓到 12% 严重问题**（人 review 漏掉的）
- **减少 30% review 迭代轮数**

**配置注意事项**：

- 必设 `fetch-depth: 0`（Codex 需要看完整 git history）
- API key 走 secrets，不要 hardcode
- 用 GPT-5.5 而非 GPT-5.5-mini（review 质量差别巨大）
- 给 review prompt 具体标准，**不要让 Codex 自由发挥**

## 2. Issue 自动分类 + 分配

新 Issue 进来，Codex 自动判断"是 bug / feature / 文档"、评估优先级、@ 合适的 owner。

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
            3. 推荐 owner：
               - 前端 → @frontend-team
               - 后端 API → @backend-team
               - 数据库 → @data-team
               - 文档 → @docs-team
            4. 复现步骤（如果是 bug）
            5. 估计工作量（S / M / L / XL）
            
            输出 JSON 格式
          model: gpt-5.5-mini
```

**实战数据**：

- 每周处理 30-50 个 Issue
- 分类准确率 89%
- **节省 5-8 小时/周人工 triage 时间**

**避坑**：Codex 分错的 issue，**必须有兜底机制**——比如分错了人，那个人手动 reassign。一周后 review 分类准确率，**持续改进 prompt**。

## 3. 自动生成 Changelog

每次发布，Codex 自动从 commit history + PR titles 生成 CHANGELOG.md。

```bash
# 本地或 CI 跑
codex chat "从 main 分支到 v1.2.0 tag 的所有 PR，生成 CHANGELOG.md
按 Conventional Commits 分类：feat / fix / perf / docs / chore
中文输出，简洁（每条 < 30 字）"
```

**生成的 CHANGELOG 示例**：

```markdown
## v1.2.0 (2026-06-15)

### 新功能
- 用户注册支持微信登录
- Dashboard 加暗色模式
- API 限流加 Redis 支持

### 修复
- 修复登录页面 N+1 查询（性能提升 5x）
- 修复 PDF 导出中文乱码
- 修复移动端菜单错位

### 性能
- 商品列表查询从 800ms 降到 180ms
```

**注意**：Codex 不会自己写 CHANGELOG.md 到仓库——你得让 CI 把它的输出写文件。

```yaml
- name: Codex Generate Changelog
  run: |
    codex chat "..." > CHANGELOG.md
    git add CHANGELOG.md
    git commit -m "chore: auto-generate changelog"
    git push
```

## 4. 自动 Bump 版本号

Conventional Commits 配合 Codex 自动 bump 版本：

- `feat:` → minor
- `fix:` → patch
- `BREAKING CHANGE:` → major

```yaml
on:
  push:
    branches: [main]

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - name: Codex Bump Version
        run: |
          # 分析 commit history，决定版本号
          npx codex chat "从上次 release 到现在所有 commit，决定下一个版本号。输出格式：vX.Y.Z" > VERSION
          # 自动更新 package.json
          npx codex chat "把 VERSION 内容更新到 package.json 的 version 字段"
          # commit + tag
          git tag $(cat VERSION)
          git push --tags
```

**实战**：

- 完全去掉手动版本号管理
- 周发布 1-2 次，**0 误 bump**
- **节省 30 分钟/周琐碎工作**

## 5. 自动部署 + 回滚

Codex 接 CI/CD 自动部署。**人只审核"是否部署"那一下**。

```yaml
on:
  workflow_dispatch:
    inputs:
      environment:
        description: '环境'
        required: true
        default: 'staging'
        type: choice
        options: [staging, production]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment }}
    steps:
      - name: Codex Pre-deploy Check
        run: |
          # Codex 跑完所有健康检查
          npx codex chat "检查 staging 环境：
          1. 数据库迁移是否完成
          2. 健康检查 /health 是否通过
          3. 最近 5 分钟错误率 < 0.1%
          4. CDN 缓存是否刷新
          
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

**重点**：部署前 + 部署后都让 Codex 验证。**如果 Codex 检测到任何问题，自动停止部署或触发回滚**。

## 6. Codex Cloud Tasks（云端任务）

2026 年 Codex 推出 **Cloud Tasks**——云端跑 agent 任务，不需要本地电脑。

场景：

- 让 Codex 跑 2 小时的迁移任务 → 关电脑去睡觉
- 早上起来看 Codex 自动生成的 PR

**配置**：

```yaml
on:
  schedule:
    - cron: '0 2 * * *'  # 每天凌晨 2 点

jobs:
  cloud-migration:
    runs-on: ubuntu-latest
    steps:
      - name: Codex Cloud Task
        run: |
          npx codex cloud "把 user 表的 email 字段从 varchar(255) 迁移到 citext 格式
          1. 先 dry-run 验证
          2. 备份原表
          3. 在低峰期（02:00 - 04:00）执行
          4. 验证完整性
          5. 完成后清理备份
          "
```

**实战数据**：

- 长任务（>30 分钟）稳定性提升 80%
- 节省本地资源（CPU / 内存 / 电）
- **但成本高**（GPT-5.5 长任务 $5-$20/任务）

## 7. Codex + 第三方模型（省钱秘技）

Codex CLI **支持第三方模型接入**。我之前详细写过，但这里再讲一下 CI/CD 场景。

用 DeepSeek / Qwen / GLM 替代 GPT-5.5，**成本降到 1/10**。

**配置**：`~/.codex/config.toml`

```toml
[model_providers.deepseek]
name = "DeepSeek"
base_url = "https://api.deepseek.com/v1"
env_key = "DEEPSEEK_API_KEY"

[profiles]
review = { model = "deepseek/deepseek-chat", temperature = 0.1 }
triage = { model = "deepseek/deepseek-chat", temperature = 0.3 }
heavy-review = { model = "openai/gpt-5.5", temperature = 0.1 }
```

**用法**：

```bash
# PR review 用 DeepSeek（成本 1/10）
npx codex --profile review chat "review this PR"

# 重要安全 review 用 GPT-5.5（质量高）
npx codex --profile heavy-review chat "review for security issues"
```

**实测省钱**：

- 简单 review 任务用 DeepSeek：$0.14/M tokens
- 复杂 review 任务用 GPT-5.5：$2.5/M tokens
- **混合用：月成本从 $300 降到 $50**

## 8. 跟 CodexLoop 配合（推荐组合）

CI/CD 自动化 + CodexLoop = **真正可靠的工程化 Codex**。

CodexLoop 负责长任务的 Checklist / Review / Deferred Ideas / Audit Logs，CI/CD 负责跑测试 / 部署 / 通知。**两者互补**。

**典型流程**：

```
PR 创建
  ↓
GitHub Actions 跑 CI 测试
  ↓
Codex Cloud Task 跑 PR review
  ↓
review 通过 + 测试通过 → 合并
  ↓
合并触发自动部署
  ↓
部署后 Codex 跑 smoke test
  ↓
smoke test 通过 → 通知 Slack
  ↓
CodexLoop 更新 deferred ideas + audit log
```

**这个流程把"开发 → review → 部署"全自动化**。人只做"产品决策"和"高价值 review"。

## 5 个常见坑

**坑 1：Codex 跑飞了浪费 token**

Codex 在 PR review 时可能陷入"无限循环"——反复跑同一个检查。**必须设 timeout 和 max_iterations**。

```yaml
- name: Codex Review
  timeout-minutes: 10
  run: npx codex chat --max-iterations 5 "review this PR"
```

**坑 2：API key 泄露**

Codex 输出里偶尔会包含 secret 字符串（从代码里读到的）。**必须配置 GitHub secret scanner 拦截**。

**坑 3：Codex 误判优先级**

Issue triage Codex 容易把 P1 误判成 P3。**重要 issue 必须人工 review**。**Codex 是辅助不是替代**。

**坑 4：云端任务成本失控**

Codex Cloud 长任务按 token 收费，**2 小时任务可能 $20**。**必须设 cost alert**（Codex CLI 自带 --max-cost flag）。

**坑 5：CI/CD 依赖耦合**

Codex 写出来的 workflow 文件可能强依赖特定工具版本。**要锁版本（@v1 不锁具体小版本）**。

## 跟传统 CI/CD 工具的对比

| 维度 | Jenkins | GitHub Actions + Codex | GitLab CI + Codex |
|------|---------|----------------------|------------------|
| 学习曲线 | 高 | 低 | 中 |
| 成本 | 自建服务器 | GitHub 免费额度 + Codex 订阅 | 自建 + Codex 订阅 |
| AI 能力 | 无 | 原生 | 需配置 |
| 适合场景 | 传统企业 | 独立开发者 / 小团队 | 已有 GitLab 的企业 |

**对独立开发者，GitHub Actions + Codex 是最优解**——零基础设施、AI 原生、低成本。

## 独立开发者的 CI/CD + Codex 实际收益

我自己 6 个月的数据：

- 每周省 5-8 小时（自动 review + 自动 triage + 自动 changelog）
- 严重 bug 漏出率从 8% 降到 1.5%
- 部署失败率从 12% 降到 2%
- **总体节奏从"周发布"加速到"日发布"**

**这套组合是独立开发者用 AI 工具最 ROI 高的工程化投资**。

## 我的判断

**短期（3-6 个月）**：自动 PR review + Issue triage 成为独立开发者标配。

**中期（6-12 个月）**：Codex Cloud Tasks 让"长任务自动化"成熟，独立开发者可以做"24/7 运行的 AI 工程师"。

**长期**：AI agent 自主做发布决策。**人只做"产品方向"判断**，"什么时候发、发什么"全是 agent 决定。

下一章讲飞书 CLI——一个真实办公场景的 agent 接入案例。