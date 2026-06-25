# 04. CLAUDE.md vs Skills：最关键的边界

2025 年 11 月我做了一个反例。

我把"代码规范"放在了 CLAUDE.md 里（项目级固定加载），把"怎么写代码"放在了 Skills 里。**结果：每次对话开头 5K token 都被 CLAUDE.md 吃掉了，不管用户在不在写代码**。

然后我把"代码规范"也搬到 Skills 里（按需加载）。**CLAUDE.md 缩到 2K，每次对话只加载 2K**。

但又来了新问题——**用户每次问"我们代码规范是啥"时，Skills 不一定自动触发**。"代码规范"是项目级背景，不是任务级工作流。

**这就是 CLAUDE.md 和 Skills 的核心边界问题**。

这一章讲：什么放 CLAUDE.md，什么放 Skills，什么都不该放。

## 核心原则

**CLAUDE.md = 始终加载 = 高频不变的"骨架规则"**
**Skills = 按需加载 = 低频调用的"详细内容"**

**CLAUDE.md 放什么**：
- 高频使用的规范（每个对话都用）
- 不变的项目背景（技术栈版本、命名规范）
- 简单的"做什么 / 不做什么"

**Skills 放什么**：
- 低频调用的工作流（写代码 review、生成 API 文档）
- 大段代码示例（>20 行的模板）
- 复杂的执行步骤（>5 步的 SOP）

**反例**：
- 80% 的对话不写代码 → 不要把"代码规范"放 CLAUDE.md
- 100% 的对话都"用中文" → 放 CLAUDE.md 没问题

## CLAUDE.md 适合什么

CLAUDE.md 加载在每次对话开头，**默认始终存在**。所以**内容要"高频 + 不变"**。

**3 个适合放在 CLAUDE.md 的内容**：

**1. 技术栈版本**（永远不变）

```markdown
# 技术栈
- Node.js 20+
- TypeScript 5.x
- React 18
- PostgreSQL 15
- pnpm（不是 npm / yarn）
```

**2. 命名规范速查表**（项目约定）

```markdown
# 命名
- 变量/函数：camelCase
- 类/类型：PascalCase
- 文件：kebab-case
- 常量：UPPER_SNAKE_CASE
- 数据库表：snake_case 复数（users / orders）
```

**3. 核心架构规则**（不能错的事）

```markdown
# 架构
- 数据流：UI → API → Service → DB
- 错误处理：try-catch 包装 + 统一 log
- 状态管理：Zustand，不用 Redux
- API 风格：RESTful，不用 GraphQL
```

**注意**：CLAUDE.md 控制在 1-2K token。**再多就开始浪费**。

## Skills 适合什么

Skills 按需加载，**默认不占 context**。**适合"低频 + 详细"的内容**。

**4 个适合放在 Skills 的内容**：

**1. 详细的工作流（>5 步）**

```markdown
## Code Review 流程
1. git diff 看所有变更
2. 按 4 个维度逐文件检查
3. 输出去重
4. 按严重程度排序
5. 用 markdown 输出
6. 不要重复已知问题
```

**2. 详细代码模板（>20 行）**

```python
# 标准 Express handler
async function handler(req, res) {
  try {
    const result = await service.process(req.body);
    res.json({ code: 200, data: result });
  } catch (e) {
    logger.error({ error: e, requestId: req.id });
    res.status(500).json({ code: 500, message: 'server error' });
  }
}
```

**3. 领域知识 / API 规范**

```markdown
## 内部 API 命名
- POST /api/v1/users — 创建用户
- GET /api/v1/users/:id — 查单个用户
- PATCH /api/v1/users/:id — 局部更新
- PUT /api/v1/users/:id — 全量替换
- DELETE /api/v1/users/:id — 删除
```

**4. 复用的最佳实践**

```markdown
## 错误处理
- 永远用 try-catch 包装 async 函数
- 错误必须 log 包含 stack trace
- 用户面错误用 i18n key，不要硬编码
- 重试用 exponential backoff（1s / 2s / 4s）
```

## 不该放的两类内容

**1. 不该放 Skills 的内容**：所有对话都用得上的"骨架规则"。

```yaml
# 错
skill: "use chinese"  # 这是 CLAUDE.md 的事
skill: "code style: camelCase"  # 这是 CLAUDE.md 的事
```

**2. 不该放 CLAUDE.md 的内容**：低频调用的"详细内容"。

```markdown
# 错
## Code Review 详细流程
（5 步 + 模板 + 20 个例子）
```

**这两种错都会浪费 context**。

## 我自己的判断决策

写一个新规则时，问 2 个问题：

**Q1：这个规则在 80% 的对话里会用到吗？**
- 是 → CLAUDE.md
- 否 → Skills

**Q2：这个规则需要 100+ 字的详细说明吗？**
- 是 → Skills
- 否 → CLAUDE.md

**两个都"是"或都"否"** — 按上面的规则走。

**一个"是"一个"否"** — 看哪个更关键：
- 高频但简短的 → CLAUDE.md
- 详细但低频的 → Skills

## 一个项目 CLAUDE.md 的 500 字模板

我自己用的项目 CLAUDE.md 模板（**控制在 500-1500 字**）：

```markdown
# 项目：[name]

## 技术栈
- [语言版本]
- [框架版本]
- [数据库版本]
- [包管理器]

## 命名
- 变量/函数：camelCase
- 类/类型：PascalCase
- 文件：kebab-case
- 常量：UPPER_SNAKE_CASE

## 架构
- 数据流方向：[UI → API → DB]
- 错误处理：[try-catch + 统一 log]
- 状态管理：[Zustand / Redux / etc.]

## 必做
- [每个 PR 必须做的检查]
- [每个 commit 必须包含的信息]

## 必不做
- [禁止使用的库 / 模式]
- [代码反模式]

## 沟通
- 用中文回答
- 技术术语保留英文
- 不要过度道歉
```

**这套模板约 800 字，加载后只占 1-1.5K token**。

## Skill vs CLAUDE.md 的 4 种反模式

**反模式 1：把 Skills 内容放 CLAUDE.md**

```markdown
# 错
## Code Review 详细规则
（3000 字的代码 review 规范）
```

**问题**：每次对话都加载 3K 浪费。**改成 Skill**。

**反模式 2：把 CLAUDE.md 内容放 Skills**

```yaml
# 错
skill name: "use-chinese"
description: 强制 Claude 用中文回答
```

**问题**：用户问"为什么用中文"时不会自动调用。**改成 CLAUDE.md**。

**反模式 3：CLAUDE.md 引用 Skills**

```markdown
# 错
详细代码规范参考 Skill: code-review
```

**问题**：CLAUDE.md 不应该"指向"Skills——它本身是骨架。**如果"代码规范"重要到要在每个对话开头提到，**就放 CLAUDE.md**。如果只是偶尔用，**放 Skills**。

**反模式 4：Skill 引用 CLAUDE.md**

```yaml
# 错
body: |
  按 CLAUDE.md 里的代码规范审查
```

**问题**：Skill 加载时不知道用户当前 CLAUDE.md 是什么。**Skill 应该自包含**——**重要的规则写进 Skill body 里**。

## CLAUDE.md 的 4 个子文件

Claude Code 2026 支持 CLAUDE.md 的模块化（多个子文件）：

```text
.claude/
├── CLAUDE.md           # 主文件，1-2K
├── CLAUDE-CODING.md    # 代码相关，1K
├── CLAUDE-TESTING.md   # 测试相关，500字
└── CLAUDE-DEPLOY.md    # 部署相关，500字
```

主 CLAUDE.md 用 `@import` 引用：

```markdown
# 主 CLAUDE.md
@import CLAUDE-CODING.md
@import CLAUDE-TESTING.md

## 简短的全局规则
（200 字）
```

**好处**：主 CLAUDE.md 保持小（1-2K），只在相关对话加载子文件。

**2026 年的默认值**：单文件 CLAUDE.md，**先不拆**。**等超过 2K 时再拆**。

## Skills + CLAUDE.md 的 5 个最佳实践

**1. CLAUDE.md 控制在 1-2K token**。**超过就开始考虑拆 Skills**。

**2. Skills 总数 ≤ 15 个**。**多了就拆项目或拆成子目录 Skills**。

**3. 任何 > 20 行的代码示例放 Skills**。CLAUDE.md 不该有"大段代码"。

**4. Skills 按 paths 限定到具体文件类型**。**别让 Skills 在不相关场景误触发**。

**5. CLAUDE.md 和 Skills 内容不重复**。**同一信息只在一边出现**。**避免"两边都得改"的同步成本**。

## 调试 CLAUDE.md 太大的 3 个方法

**方法 1：删除"骨架"以外的内容**

CLAUDE.md 只放"骨架规则"——技术栈、命名、架构。**详细工作流、模板、API 规范放 Skills**。

**方法 2：拆成子文件**

```text
.claude/
├── CLAUDE.md           # 主
├── CLAUDE-CODING.md    # 拆出
```

**方法 3：移到 Skills**

```yaml
# 错（CLAUDE.md）
## Code Review 详细规则
# ...

# 对（Skill）
skill name: "code-review"
description: 按团队规范审查代码
```

**CLAUDE.md 应该是"打开就能用"的状态**——**任何超过 2K 的内容都该被怀疑**。

下一章讲 8 大实用 Skills 拆解——**我项目里真正在用的 8 个 Skill**。
