# 09. AIGrader 复盘：1 个人半天做出全栈 AI 批改平台

github.com/xiaodangjia/AIGrader 是 2026 年最值得拆的独立开发者项目之一——**1 个人 1 半天做出 Spring Boot + React + pgvector 全栈 AI 批改平台**。这一章把它彻底拆开，给你一个"独立开发者用 AI 做到这种程度"的具体路径。

## 项目是什么

AIGrader 是一个面向 K12 教育的 AI 作业批改平台。教师布置作业 → 学生提交 → AI 秒级批改 → 学生订正 → 教师复核。

**这不是 demo**——是真能跑的生产级系统。教师、学生、管理员三套角色权限，3 种 AI 批改策略（选择 / 填空 / 主观题），数据存储在 pgvector 支持语义检索相似题目。

## 4 小时内产出的数据

| 维度 | 数值 |
|------|------|
| 后端 Java 文件 | 63 个 |
| 前端 TS/TSX 文件 | 21 个 |
| 数据库表 | 9 张（含 pgvector）|
| REST API | 30+ |
| AI 批改策略 | 3 种 |
| 角色权限 | 3 套 |
| AI 模型 | DeepSeek（主力）|
| 总代码行 | ~15000 行 |

**4 小时 = 15000 行代码**。平均每分钟 60+ 行。这放在 2023 年是不可想象的，2026 年是独立开发者的新基准线。

## 技术栈选型

AIGrader 的技术栈是**"流行 + 够用"**的典型：

**后端**：

- Spring Boot 3.4（不用 Spring Web）
- Java 21（最新 LTS）
- JPA / Hibernate（标准 ORM）
- PostgreSQL 16 + pgvector（向量存储）
- Redis（缓存 + 限流）

**前端**：

- React 18
- TypeScript（强制）
- Tailwind CSS（快速 UI）
- Vite（构建工具）
- Zustand（轻量状态管理）

**AI**：

- DeepSeek（主力，国产，便宜）
- OpenAI Embedding（pgvector 检索用）

**作者选型逻辑**：

- Spring Boot 而非 Node.js：**Java 适合企业级、长维护周期**
- React 而非 Vue：**生态更大、AI 训练数据更多**
- pgvector 而非专用向量库：**少一个组件，运维简单**
- DeepSeek 而非 GPT-5.5：**便宜 1/10，足够用**

**这套选型是"独立开发者"思维——能跑、够用、维护成本低**。

## 6 个并行 stream

我在第 5 章简单提过 AIGrader 的 6 stream 拆分。这里完整拆。

作者把 4 小时拆成 6 个**并行 spawn_agent** 任务流：

**Stream 1：数据库设计**

- 设计 9 张表的 schema
- pgvector 字段定义
- 索引设计
- 迁移脚本

**Stream 2：后端 API**

- Spring Boot 项目结构
- 30+ REST 端点
- Service / Repository 分层
- 异常处理

**Stream 3：前端 UI**

- 登录 / 注册
- 教师工作台
- 学生作业页
- 管理后台

**Stream 4：AI 批改策略**

- 选择题自动判
- 填空题相似度匹配（pgvector）
- 主观题 LLM 评分

**Stream 5：测试用例**

- 单元测试（JUnit 5）
- 集成测试（TestContainers）
- E2E 测试（Playwright）

**Stream 6：部署脚本**

- Docker Compose
- 环境变量管理
- CI/CD 配置
- 监控告警

**6 个 agent 同时跑 4 小时 = 单 agent 跑 24 小时的工作量**。

## 3 层约束系统

6 个 agent 并行写代码不乱，**靠的是 3 层约束**。

### 层 1：AGENTS.md 项目规则

```markdown
## 技术栈
- 后端：Spring Boot 3.4 + Java 21
- 前端：React 18 + TypeScript + Tailwind
- 数据库：PostgreSQL 16 + pgvector
- 测试：JUnit 5 + TestContainers + Playwright
- 构建：Maven 3.9+ / Vite 5+

## 编码规范
### DO
- 所有 API 路由必须有 OpenAPI 注解
- 所有 Service 注入用构造器注入（不用 @Autowired）
- 所有数据库查询用 JPA，禁止 native SQL
- 所有错误处理用 @ControllerAdvice 统一处理

### DON'T
- 禁止使用 Lombok（项目不用）
- 禁止 hardcode URL，统一从 application.yml 读
- 禁止 .env 文件入 git
- 禁止在 Controller 写业务逻辑
```

**这段 AGENTS.md 是 6 个 agent 不冲突的基础**。每个 agent 看到的是同一份"宪法"。

### 层 2：Skill 标准化

作者定义了一组 **reusable skill**——每个 agent 调用相同 skill：

**skill 1：`add-rest-endpoint`**

```yaml
input:
  - resource: User / Order / Assignment ...
  - operations: list / get / create / update / delete
output:
  - Controller 方法（含 OpenAPI 注解）
  - Service 方法（含业务逻辑）
  - Repository 接口
  - DTO（Request / Response）
  - Test 文件
constraints:
  - 路由前缀 /api/v1/{resource}
  - 错误码统一 E0010xxx 格式
  - 限流注解 @RateLimit
```

**skill 2：`add-react-component`**

```yaml
input:
  - name: 组件名
  - props: TypeScript interface
output:
  - .tsx 文件（PascalCase）
  - .module.css（如果需要）
  - index.ts（re-export）
  - Storybook story
constraints:
  - 必须有 propTypes / TypeScript interface
  - 必须有 defaultProps
  - 必须有 data-testid
```

**skill 3：`add-db-table`**

```yaml
input:
  - 表名
  - 字段列表
output:
  - JPA Entity
  - Migration 脚本（Flyway）
  - Repository
constraints:
  - 主键用 Long auto-increment
  - created_at / updated_at 自动维护
  - 软删除字段 deleted_at
```

**3 个 skill 让 6 个 agent 输出风格一致**。

### 层 3：约束文件锁

每个 agent **只允许修改特定目录**：

| Agent | 允许修改的目录 |
|-------|--------------|
| Stream 1 (DB) | `db/`, `migrations/` |
| Stream 2 (API) | `src/main/java/com/aigrader/api/` |
| Stream 3 (UI) | `src/main/webapp/src/` |
| Stream 4 (AI) | `src/main/java/com/aigrader/ai/` |
| Stream 5 (Test) | `src/test/java/`, `src/test/e2e/` |
| Stream 6 (Deploy) | `deploy/`, `.github/workflows/` |

**这层约束是 6 个 agent 不互相覆盖的关键**。每个 agent 在自己的"沙箱目录"工作。

## 提示词工程

作者给每个 agent 的 prompt 模板是关键。我把模板展开：

```markdown
# 任务
[具体任务描述]

# 输入
- 项目根目录：/home/user/aigrader
- 你的工作目录：[相对路径]
- 你可以修改的文件：[glob pattern]
- 你的依赖：[其他 stream 正在做的]

# 输出
- 你必须产出的文件：[具体文件列表]
- 你必须保证的验收标准：[可验证的条件]

# 约束
- 严格遵守 AGENTS.md
- 使用 skill：[具体 skill 名称]
- 调用顺序：[如果依赖其他 stream，先等什么完成]

# 完成时报告
- 产出文件路径
- 关键决策说明
- 需要人工 review 的点
- 后续 stream 需要知道的信息
```

**这套模板的 4 个关键点**：

1. **明确目录边界**——agent 不会乱动别人的文件
2. **明确依赖顺序**——比如 Stream 4 (AI) 必须等 Stream 1 (DB) 完成
3. **明确验收标准**——agent 知道什么时候算"做完了"
4. **明确后续接口**——agent 输出要能被下游 stream 使用

## SSH 远程运维

作者把 6 个 agent 跑在**云服务器**上，不是本地笔记本。**通过 SSH 远程触发**。

```bash
ssh user@server "cd /home/user/aigrader && \
  npx codex spawn-agent 'implement user service'"
```

为什么不上跑在本地？

- 本地笔记本性能不够跑 6 个并发 agent
- 云服务器 24/7 在线，长任务不中断
- 远程触发避免本地误关闭
- **可以同时在多台机器跑不同项目**

**6 个 agent 并发跑 = 6 倍 token / 6 倍算力需求**。**笔记本顶不住**。

## 4 小时真实时间表

我把作者公开的时间表整理一下：

| 时间 | 任务 |
|------|------|
| 0:00-0:30 | 项目初始化：AGENTS.md + 3 个 skill + git init + 6 个 worktree |
| 0:30-4:00 | 6 个 agent 并行开发 |
| 4:00-4:30 | 合并 6 个 worktree 到 main，解决冲突 |
| 4:30-5:00 | 跑全量测试，修复 bug |
| 5:00-5:30 | 部署到 staging，跑 smoke test |
| 5:30-6:00 | 写 README + 文档，发布 GitHub |

**总耗时 4 小时开发 + 2 小时收尾 = 半天**。这是真"半天"。

## 4 个关键工程秘密

### 秘密 1：先写 AGENTS.md 再写代码

作者**第一个 30 分钟全在写 AGENTS.md + skill**，没碰业务代码。

**这反直觉**——很多人觉得应该"先跑起来再说"。但**AGENTS.md 是 6 个 agent 的协作基础**。**没有它，6 个 agent 写出来的代码风格不一致、需要大改**。

**AGENTS.md + skill 占总时间的 12%**，但**节省了 60% 的合并冲突和 review 时间**。**ROI 极高**。

### 秘密 2：约束文件锁避免 80% 冲突

6 个 agent 同时写代码，**传统方式 = 合并地狱**。作者用 worktree + 文件锁，**冲突降到 5% 以下**。

**3 个 worktree 工具**：

- git worktree（Git 内置）
- jj / sapling（Meta 的版本控制）
- GitButler（图形化 worktree）

作者用 `git worktree`——6 个分支并行，最后 merge。

### 秘密 3：测试驱动控制质量

每个 agent 写完代码**必须**包含测试。**没有测试的代码不合并**。

作者 6 个 stream 的测试覆盖：

- Stream 1 (DB)：100%（每个表都测）
- Stream 2 (API)：90%（关键端点必测）
- Stream 3 (UI)：70%（核心组件必测）
- Stream 4 (AI)：95%（批改策略边界 case）
- Stream 5 (Test)：100%（自身是测试）
- Stream 6 (Deploy)：80%（部署脚本测）

**总覆盖率 88%**——4 小时内 88% 覆盖率，靠的是**"测试是 agent 输出的硬约束"**。

### 秘密 4：SSH 远程 + 云服务器

我前面提了，但这是关键。**没有云服务器，AIGrader 这种 4 小时全栈项目根本跑不出来**。

**云服务器要求**：

- 16 核 + 64GB 内存（跑 6 个并发 agent）
- 200GB 存储（git 仓库 + 依赖）
- 1Gbps 带宽（agent 频繁读 git）
- **$50-100/月**（独立开发者用得起）

**国内选择**：

- 阿里云 ECS（$60/月起）
- 腾讯云 CVM
- 华为云 ECS
- Vultr / DigitalOcean（$96/月起，海外）

## 独立开发者能不能复制

我把 AIGrader 的方法论**拆成可复制的步骤**：

**Step 1：写 AGENTS.md（30 分钟）**

按上一章的模板，写 5 个部分：

- 技术栈
- 目录结构
- 常用命令
- 编码规范（DO / DON'T）
- 项目背景

**Step 2：定义 3-5 个 skill（30 分钟）**

针对你的项目类型：

- Web 项目：add-rest-endpoint / add-react-component / add-db-table
- 移动 App：add-screen / add-widget / add-api-client
- AI 项目：add-prompt / add-tool / add-eval

**Step 3：拆 stream（15 分钟）**

根据项目复杂度拆 3-6 个 stream。每个 stream **互不依赖**或**只单向依赖**。

**Step 4：spawn 6 个 agent**

在云服务器跑。每个 agent 在独立 worktree。

**Step 5：合并 + 测试（30-60 分钟）**

合并 worktree，跑全量测试，修复冲突。

**Step 6：部署 + 文档（30 分钟）**

部署到 staging，写 README，发布。

**总时间 = 半天**。**前提是你已经习惯了 spawn_agent + CodexLoop 的协作模式**。

## AIGrader 之后的启示

AIGrader 验证了一个核心假设：**1 个人 + 一套 agent 工具 = 1 个小型开发团队**。

**对比传统团队**：

- 1 个全栈工程师 + 1 个 AI 工程师 + 1 个测试工程师 = **3 人 / 月薪 6 万**
- 1 个独立开发者 + 6 个 Codex agent = **1 人 / 月成本 $100（云 + API）**

**生产力差距**：6 个 agent 4 小时 vs 3 人 2 周（10 天 × 8 小时 = 80 小时）。**单位时间产能 agent 高 5 倍**。

**但人类工程师的价值**：

- 产品方向判断（agent 没有）
- 用户体验细节（agent 容易过度工程化）
- 长期架构演进（agent 看不到 3 个月后）
- 业务领域知识（agent 不懂教育行业的潜规则）

**独立开发者的新定位**：

- 不是"全栈工程师"
- 是"**AI 工程团队的产品经理 + 架构师**"
- 负责方向 + 质量 + 决策
- 把执行交给 agent

## 我的判断

**短期（3-6 个月）**：AIGrader 类项目成为独立开发者的"基准演示"——你能不能 1 天出 MVP，决定了你能不能跑赢同行。

**中期（6-12 个月）**：spawn_agent + CodexLoop 组合成熟，**独立开发者能力 = 5-10 人小团队**。

**长期（12+ 个月）**：**1 个独立开发者 = 1 家公司**。AI 员工不是比喻，是真的。融资不是必要条件。

下一章讲未来 6 个月趋势 + 个人 pick。