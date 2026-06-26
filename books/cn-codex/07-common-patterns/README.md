# 07. 共同模式：15 款桌面 Agent 收敛的 5 个核心范式

15 款产品看似眼花缭乱，**实际在收敛 5 个共同模式**——worktree / 多 Agent 编排 / 异步执行 / Skills 生态 / 定时任务。这一章拆这 5 个范式，**让你看透桌面 Agent 战场的底层逻辑**。

## 范式 1：Worktree 隔离

**15 款里有 12 款支持 worktree 隔离**——这是桌面 Agent 的基础设施。

### 为什么 worktree 是必须的

单 Agent 跑复杂任务时**上下文会爆**——比如要改 50 个文件，单 Agent 改到第 30 个就忘了前 20 个。

**worktree 隔离** = **每个 agent 跑在独立 git worktree**：

- 互不干扰
- 失败回滚简单
- 多任务并行

### 各家实现对比

| 产品 | worktree 实现 | 隔离粒度 |
|------|---------------|---------|
| **Codex Desktop** | git worktree（多分支并行） | **3-5 个 worktree 同时跑** |
| **TRAE Work** | "三端协同"（手机 / 电脑 / Web）| 任务级别隔离 |
| **WorkBuddy** | "项目空间"（共享上下文）| 团队级别隔离 |
| **Kimi Work** | Agent Swarm 集群 | **300 子 Agent 独立** |
| **QoderWork** | "任务监控"（步骤可见）| 任务级别隔离 |
| **Qoder CN** | "专家团"（不同 Expert 独立上下文）| Agent 级别隔离 |

**Codex Desktop 的 worktree 最"工程化"**——**最像 Git 的工作流**。

**Kimi Work 的 Agent Swarm 最"分布式"**——**最像 Kubernetes 的 Pod 调度**。

### 实战用法

**Codex Desktop 用 worktree**：

```bash
# 启动时指定 3 个 worktree
codex desktop --worktree feature-a --worktree feature-b --worktree bugfix
```

**3 个 agent 同时跑**：

- worktree-1：实现 user authentication
- worktree-2：实现 payment integration
- worktree-3：修复 #123 bug

**完成后 merge**——**互不干扰**。

### 适合场景

- 多 feature 并行开发
- 大型 monorepo 重构
- 多人协作（**用 worktree 模拟"团队成员"**）

## 范式 2：多 Agent 编排

**15 款里有 12 款支持多 Agent 编排**——**单 Agent 不够用是行业共识**。

### 4 种编排模式

**模式 A：主-子 Agent（trae / qoder）**

**TRAE Work** 的 "主 Agent + 子 Agent" 架构：

- **主 Agent**：拆任务、组团队、盯进度
- **子 Agent**：各管一摊（前端 / 后端 / 测试）
- **典型**：做完整项目（前端 + 后端 + 测试 + 部署）

**模式 B：专家-助理-团队（WorkBuddy）**

**3 层能力模型**：

- **专家**：岗位经验封装（销售 / 法务 / 财务）
- **助理**：24/7 数字员工
- **团队**：共享上下文 + 沉淀资产

**典型**：企业级 B 端项目。

**模式 C：Agent Swarm 集群（Kimi Work）**

**300 个子 Agent + 拓扑依赖管理**：

- **planner** 拆任务
- **researcher-1, 2, 3, 4** 收集数据（**并行**）
- **coder-1, 2** 写代码
- **reviewer** 审查
- **writer** 写文档

**依赖关系自动管理**——**researcher-3 等 researcher-1, 2 先完成**。

**模式 D：专家团（Qoder CN）**

**专项调优的 SWE Agent + 模型路由**：

- **Leader Agent**：拆任务、组团队
- **专家成员**：前端 / 后端 / 数据库 / 架构 / 测试
- **每个 Expert 路由到不同模型**——规划用 Opus、写代码用 GLM5、测试用 Kimi K2.5

**"不是同一个 AI 换 prompt"**——是**真正独立上下文的 SWE Agent**。

### 4 种模式对比

| 模式 | 代表产品 | Agent 数量 | 调度方式 | 适合 |
|------|---------|----------|---------|------|
| 主-子 | TRAE Work | 2-5 | 主 Agent 直接调度 | 完整项目 |
| 三层 | WorkBuddy | 10-50 | 团队空间协调 | 企业 B 端 |
| Swarm | Kimi Work | 50-300 | **DAG 拓扑管理** | 长任务 + 复杂研究 |
| 专家团 | Qoder CN | 5-15 | Leader + 模型路由 | 专业 SWE 任务 |

### 多 Agent 编排的核心问题

**问题 1：上下文隔离**

每个 Agent 看不到其他 Agent 的 context——**必须靠 prompt 显式描述**。

**解决**：靠"主 Agent 汇总 + 标准化输出"。

**问题 2：任务冲突**

两个 Agent 都要改同一文件——**后跑的覆盖前面的**。

**解决**：靠 worktree 隔离 + 文件锁。

**问题 3：失败传播**

一个 Agent 失败拖累整个集群——**指数级失败**。

**解决**：靠"自动重试 + 失败隔离 + 降级"。

## 范式 3：异步执行

**15 款里有 13 款支持"异步执行 / 后台任务"**——**这是桌面 Agent 区别于聊天 AI 的核心能力**。

### 异步的 3 种实现

**实现 A：云端异步（Codex Web / OpenClaw）**

**任务跑在云端**——电脑可以关闭。

- 早上起床看 Codex 自动生成的 PR
- 8 小时长任务 / 跨日任务
- **适合**：长任务 / 跨设备

**实现 B：本地后台（QoderWork / WorkBuddy）**

**任务跑在本地后台**——电脑必须保持唤醒。

- 屏幕关掉就停
- **适合**：短任务（< 1 小时）

**实现 C：移动端布置（TRAE Work / Marvis）**

**手机发任务，电脑执行**。

- 通勤时语音发任务
- 电脑端实时同步
- **适合**：碎片时间利用

### 异步的最佳实践

**原则 1：长任务用云端**

- 8 小时迁移 / 重构
- **别用本地跑**（电脑发热 + 资源占用）

**原则 2：定时任务看 CPU**

- 每天 9 点的 SEO 检查
- **用云端**（不依赖本地电脑唤醒）

**原则 3：实时监控用移动端**

- 随时查任务进度
- **手机 App 通知**

**原则 4：失败重试要明确**

- 自动重试 3 次
- 重试失败推送到 Slack / 飞书
- **别让任务静默失败**

### 异步的 5 个真实坑

**坑 1：本地跑长任务电脑发热**

300 Agent Swarm 跑 13 小时——M3 Max 风扇起飞。

**解决**：用云端异步。

**坑 2：定时任务断网失效**

QoderWork 定时任务**电脑断网就停**。

**解决**：用云端定时（QoderWork 暂不支持，**等更新**）。

**坑 3：异步任务并发冲突**

两个定时任务同时跑——**CPU 抢资源**。

**解决**：错峰调度 + 任务队列。

**坑 4：异步任务失败通知缺失**

任务失败 30 分钟才发现——**错过了最佳修复时间**。

**解决**：必接飞书 / 钉钉 / Slack 通知。

**坑 5：跨设备状态不同步**

电脑端显示"任务完成"——手机端还在"运行中"。

**解决**：必接 OneID 统一账号。

## 范式 4：Skills 生态

**15 款里有 11 款做 Skills 市场**——**Skill = agent 时代的 App Store**。

### Skills 的本质

**Skills = 打包好的指令集 + 资源 + 脚本**——让 Agent **做写代码之外的事**。

- 比如 image generation Skill：让 Codex 调 GPT Image 生成 UI 素材
- 比如 SEO audit Skill：让 Codex 跑 SEO 审计 + 报告

### Skills 的 3 个 scope

| Scope | 路径 | 适用 | 数量 |
|-------|------|------|------|
| **个人** | `~/.codex/skills/` | 跨项目私有 | 20-30 |
| **项目** | `.agents/skills/` | 团队共享 | 10-20 |
| **企业** | `/etc/codex/skills/` | 全公司默认 | 50+ |

### 主流 Skills 市场

| 平台 | Skills 数量 | 月下载 | 计费 |
|------|----------|--------|------|
| **WorkBuddy SkillHub** | 7 万+ | 3000 万+ | 免费 + 付费 |
| **Codex Skills** | 500+ | - | 免费 |
| **QoderWork 技能市场** | 200+ | - | 免费 |
| **TRAE Skills** | 100+ | - | 免费 |
| **Kimi Work 社区模板** | 2000+ | - | 免费 |

**WorkBuddy SkillHub 是国内最大**——**7 万 Skills**。

### 独立开发者必装 Skills（2026）

我整理的 10 个最常用：

1. **create-plan** — 强制 Codex 写代码前拆任务
2. **review-code** — 以独立 reviewer 身份审查 diff
3. **run-tests** — 自动检测测试框架 + 跑全量
4. **commit-msg** — Conventional Commits 格式
5. **refactor-safe** — 跨文件重构前先列影响
6. **debug-investigator** — 基于日志定位 bug
7. **doc-generator** — 自动生成 README / API doc
8. **type-migrate** — JS 项目补 TypeScript
9. **i18n-extract** — 提取硬编码文案
10. **db-migrate** — Prisma / Drizzle / Flyway 迁移

### Skills 商业化

**Substack 之于创作者 = Skill 市场之于 agent 开发者**。

3 种赚钱方式：

- **直接卖 Skill**（$5-50/Skill）
- **抽成市场**（30% 给平台）
- **订阅制 Skill Hub**（$9-29/月）

**2026 年下半年会有"Skill 大 V"出现**——**像 Substack 早期一样，**月入 $10K 的 Skill 创作者会冒出来**。

### Skills 的 3 个真实坑

**坑 1：Skill 太多记不住**

装了 50+ Skill——**实际常用就 10 个**。

**解决**：只装高频 Skill，其他按需装。

**坑 2：Skill 质量参差不齐**

Skills 市场**没有审核机制**——**垃圾 Skill 大量存在**。

**解决**：用大厂官方 Skill + 社区评分高的。

**坑 3：Skill 不跨平台**

**同一个 Skill 在 Codex 能用，在 Kimi Work 不能用**——**Skill 格式不统一**。

**解决**：Anthropic 在推开放 Skill 标准（**SKILL.md 跨平台**），**关注生态发展**。

## 范式 5：定时任务

**15 款里有 13 款做"定时任务 / Automations"**——**Agent 从"调用一次"到"持续运行"**。

### 定时任务的 5 个场景

**场景 1：每日 SEO 检查**

```bash
0 9 * * * codex task "检查 kunpeng-ai.com 的 SEO 状态"
```

**场景 2：每周代码审查**

```bash
0 17 * * 5 codex review "审查本周所有 commit"
```

**场景 3：每月数据备份**

```bash
0 2 1 * * codex backup "备份生产数据库到 OSS"
```

**场景 4：每日数据报告**

```bash
0 18 * * * codex report "生成每日数据日报"
```

**场景 5：实时监控 + 告警**

```bash
*/5 * * * * codex monitor "检查 API 错误率，> 1% 告警"
```

### 定时任务的 4 个关键设计

**设计 1：错峰调度**

不要所有任务 9 点跑——**CPU 会爆**。

```bash
# 错峰
0 9 * * * task1
30 9 * * * task2
0 10 * * * task3
```

**设计 2：失败重试 + 通知**

```bash
# 失败重试 3 次，失败通知飞书
codex task "..." --retry 3 --notify feishu://chat_id=xxx
```

**设计 3：审计日志**

**每个定时任务必须有审计日志**——什么时候跑、跑了什么、结果如何。

```bash
codex task "..." --audit-log ~/.codex/logs/cron.log
```

**设计 4：依赖检查**

**任务 B 依赖任务 A 完成**——**不能直接 cron**。

```bash
# 用工具链管理（如 TaskScheduler / Airflow）
task-a → task-b → task-c
```

### 定时任务的 3 个真实坑

**坑 1：本地定时任务电脑必须唤醒**

QoderWork 定时任务**关屏就停**——**不是 24/7**。

**解决**：用云端定时（**云厂商提供**）。

**坑 2：并发任务资源争抢**

10 个定时任务同时跑——**CPU 抢资源**。

**解决**：错峰 + 任务队列。

**坑 3：定时任务静默失败**

任务失败**没人知道**——错过了最佳修复时间。

**解决**：**必接告警通知**（飞书 / 钉钉 / 短信）。

## 5 个范式的组合

**5 个范式不是独立**——**它们形成一个完整体系**：

```
多 Agent 编排（怎么拆任务）
   +
worktree 隔离（怎么隔离环境）
   ↓
并行执行（怎么同时跑）
   +
异步执行（怎么后台跑）
   ↓
定时任务（什么时候自动跑）
   +
Skills 生态（怎么扩展能力）
   ↓
完整 Agent 系统
```

**5 个范式全用上 = 独立开发者 = 1 个小团队**。

## 我的实战组合

**日常开发**：

- 多 Agent 编排（TRAE 主-子）+ worktree 隔离（Codex Desktop）
- 异步执行（云端 Codex Web，**长任务用**）
- Skills（10 个高频 Skill + 个人 ECC 系统）
- 定时任务（**几乎不用本地**，**用云端**）

**结论**：

- **5 个范式是"独立开发者的工具箱"**
- **每个范式 1-2 个工具 = 1 个人 = 1 个小团队**

下一章讲**国内 API 接入方案**——DeepSeek / Qwen / GLM / Kimi / 豆包，**5 大国产模型对比 + 反代技巧 + 独立开发者省钱秘技**。