# 10. 我的 vibe coding 工作流模板

一年下来，踩了 50+ 次坑之后，我沉淀出一套**可复用**的 vibe coding 工作流。这一章把流程、模板、清单全放出来，你拿去直接用。

## 一、项目初始化（一次）

每个 vibe coding 项目开头，建一个 `VIBE.md` 放项目根目录：

```markdown
# 项目 vibe coding 配置

## 技术栈
- 后端：NestJS + TypeScript + PostgreSQL + Prisma
- 前端：React + TypeScript + Vite + Tailwind
- 部署：Docker + AWS ECS

## 命名规范
- DB 字段：snake_case
- API 返回：camelCase
- 所有 DB 返回必须经过 utils/format.ts 转换
- 错误返回统一：{ code: number, message: string, data: null }
- 日志统一：pino logger，格式 { time, level, traceId, msg }

## 性能约束
- 禁止 N+1（必须 join / include）
- 分页必须 cursor（offset 只用于后台管理列表）
- 列表接口必须 select 指定字段

## 安全约束
- 禁止任何密钥硬编码（全部 env）
- 所有写接口必须 @RequireAuth
- 所有 SQL 必须参数化

## 业务术语
- SKU = 库存单元（Stock Keeping Unit）
- SPU = 标准产品单元（Standard Product Unit）
- 客单价 = GMV / 订单数

## 合规要求
- 等保 2.0 三级
- 用户敏感字段（手机号、身份证）必须 AES-256 加密存储
- 操作日志保留 ≥ 180 天

## 测试要求
- 单元测试覆盖率 ≥ 70%
- 集成测试覆盖所有 controller 接口
- E2E 测试覆盖核心业务流程（注册、登录、下单、支付）
```

把这份 `VIBE.md` 在每次 vibe coding 时**贴到 AI 对话开头**。一次配置永久复用。

## 二、单任务 vibe coding 流程

每个新任务按这个流程走：

**Step 1：写需求口述模板**

```
项目背景：基于现有 NestJS 项目（见 VIBE.md）
本任务：[具体做什么]
约束：[本任务特有的约束，不重复 VIBE.md 里已有的]
验收标准：[怎么算做完了]
```

**Step 2：让 AI 生成初版**

贴需求模板，让 AI 出代码。**不要急着看代码，先看 commit message 和文件结构**。如果文件结构跟描述对不上，立即停。

**Step 3：人工扫一遍**

用 IDE 的 file diff 视图（VS Code / Cursor / TRAE 都有）扫 AI 生成的关键改动。**重点扫**：循环里有几个 await、SQL 有没有参数化、有没有硬编码字符串、命名跟 VIBE.md 是否一致。

**Step 4：跑测试 + 慢查询日志 + 安全 checklist**

```bash
npm test
# PostgreSQL 慢查询
psql -c "SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10"
# 安全 checklist
./scripts/security-check.sh
```

**Step 5：commit**

commit message 模板：

```
[type] scope: 一句话描述

[详细说明 AI 生成的关键决策]
[列出所有 VIBE.md 偏离的地方]
[列出还需要后续 review 的点]
```

**Step 6：第二天重新看一遍**

第二天起来重新看昨天的 commit，**用 fresh eyes**。能发现 30% 头一天漏掉的问题。

## 三、跨文件重构流程（特殊）

**额外 4 步**：

1. **先 grep 列清单**：让 AI 扫所有需要改的位置（文件:行号），不要改任何代码。
2. **画依赖图**：让 AI 画模块依赖图，先改底层再改上层。
3. **分批改**：单次 vibe ≤ 5 个文件，分批 commit。
4. **worktree 隔离**：用 `git worktree add` 开新分支，改完测完再 merge。

## 四、性能 / 安全 / 规范三类清单（每次 commit 前必跑）

**性能 checklist**：

```
[ ] grep "findMany\|findUnique" 检查所有数据库调用，确认无循环内调用
[ ] 分页接口用 cursor（offset 仅后台列表）
[ ] 列表接口 select 指定字段
[ ] 无 select *
```

**安全 checklist**：

```
[ ] grep -r "=\s*['\"]" src/  无硬编码字符串（除测试 fixture）
[ ] 所有写接口有 @RequireAuth
[ ] 所有 SQL 参数化
[ ] 错误返回不泄露 stack
[ ] 审计日志覆盖敏感操作
```

**规范 checklist**：

```
[ ] 命名跟 VIBE.md 一致
[ ] 错误返回统一格式
[ ] 日志统一格式
[ ] 所有 DB 层返回经过统一转换
```

## 五、什么时候停

3 个硬信号：

- **AI 幻觉**（引用不存在的库/函数）→ 停
- **3 轮没修好同一 bug** → 停
- **AI 拒绝继续** → 停

## 六、工具栈选择

| 场景 | 工具 |
|------|------|
| 海外项目 | Claude Code（纯终端 + 模型最强）|
| 国内项目 | TRAE（中文 + 私有化 + 免费）|
| 数据敏感 | TRAE 企业版 / Cline + 本地 Ollama |
| 预算 0 | TRAE 基础版 / Cline + DeepSeek API |
| 不想读代码 | TRAE IDE 模式（有项目级代码索引）|

## 七、个人心法

vibe coding 不是"我让 AI 写我就不用管"。**vibe coding 是"我让 AI 写初版，我负责把它从 70 分磨到 100 分"**。磨的过程你必须读代码、做决策、补测试、补文档。

省下来的时间 ≠ 不用花时间。省下来的是"写第一版的机械时间"，但"review + 测试 + 改"的判断时间反而变多了——因为 AI 写的代码你得重新理解一遍才能改。

这套流程跑了一年，**我个人 vibe coding 项目从平均 5.4 轮迭代降到 1.8 轮，从 62% 半年后维护不了降到 16%**。省下来的时间全在 review 阶段前移到了需求口述阶段。

如果你只能记住一件事：**vibe coding 的功夫在 vibe 之外，在口述需求 + 清单校验 + commit 后第二天再看一遍**。

整个系列 10 章到这里。下一步看你想先开哪条新线——A2A 多 Agent 互操作 / 长期记忆 / 具身智能 / AI 内容创作经济，挑一个继续。