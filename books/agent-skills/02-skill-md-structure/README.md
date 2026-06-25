# 02. SKILL.md 文件结构

2025 年 11 月我第一次写 Skill，模仿网上找的 3 个例子拼出来一个 SKILL.md。**Claude 在该调用的时候不调用，不该调用的时候瞎调用**。

后来我才明白，**SKILL.md 的字段不是越多越好，每行字都有触发权重的代价**。

这一章把 SKILL.md 的结构讲透——每个字段的作用、怎么写、踩过的坑。

## 最小可用的 SKILL.md

一个 Skill 就是一个文件夹。最简形式：

```text
.claude/skills/code-review/
└── SKILL.md
```

`SKILL.md` 的内容是 **YAML frontmatter + Markdown body**：

```yaml
---
name: code-review
description: 按团队规范审查代码变更。涉及 src/ 下的 TS/JS 文件时自动触发。
---

# Code Review Skill

## 审查清单

1. 安全：SQL 注入、权限校验、敏感信息泄露
2. 性能：N+1 查询、内存泄漏、不必要的循环
3. 代码质量：命名规范、单一职责、可测试性
4. 错误处理：异常捕获完整性、错误信息可读性

## 输出格式

```markdown
## Code Review
- 🔴 严重：[问题描述 + 文件:行号]
- 🟡 警告：[问题描述 + 文件:行号]
- 🟢 建议：[优化建议 + 文件:行号]
```
```

**4 件事**：
- `name`：技能名（也是 `/` 命令名）
- `description`：模型读这段判断是否触发（**关键中的关键**）
- body 第一节：工作流（步骤 / 清单 / SOP）
- body 其他：参考、模板、示例

## 字段详解

**name**（必填）。规则：必须 kebab-case（小写 + 连字符），不超过 64 字符，跟目录名一致（`code-review` ↔ `code-review/`），不能重名。

常见错误：`codeReview` ❌ → 改 `code-review`、`code_review` ❌ → 改 `code-review`、`Code Review` ❌ → 改 `code-review`。

**description**（必填）。**这是整个 Skill 最重要的字段**——Claude 读这个判断"什么时候调用这个 Skill"。

3 条铁律：

1. 1-2 句话讲清"做什么 + 什么时候用"。**差**的描述"代码审查工具"太模糊，模型在不该用的时候也会用。**好**的描述"按团队规范审查代码变更的安全、性能、错误处理问题。涉及 src/ 下的 TS/JS 文件改动时自动触发"明确触发场景，模型只在匹配时才用。

2. 用关键词触发——description 里包含用户可能用到的具体术语。**关键词 review PR / diff / git diff / SQL 注入 / N+1 都是用户可能说的具体术语**，模型匹配这些术语决定是否调用。

3. 控制在 1536 字符以内。description + when_to_use 合计上限 1536 字符，超过会被截断。

**when_to_use**（可选但推荐）。比 description 更详细的触发条件。**description + when_to_use 一起决定触发**——当 description 模糊时，when_to_use 补全触发场景。

```yaml
description: 按团队规范审查代码变更。
when_to_use: |
  当用户提交 PR、要求 review 代码、问"这段代码有没有问题"、问"为什么改"时自动触发。
  适用于：团队成员、PR review、code review 工具集成。
  不适用于：纯写作、纯文档编辑、外部项目代码。
```

**paths**（可选）。glob 路径过滤，限定 Skill 只在涉及特定文件时考虑触发。**用法**：当对话中涉及的文件匹配这个 glob 时，Skill 才被考虑触发（包括用户提及、读取、编辑的文件）。这能解决"什么文件该用什么 Skill"的问题——比如 `code-review` 配 `paths: ["src/**", "tests/**"]` 只在改 src 或 tests 时触发，`frontend-design` 配 `paths: ["**/*.tsx", "**/*.css"]` 只在改前端文件时触发。**关键点**：paths 限定的是"对话上下文涉及的所有文件"，不是"当前编辑文件"。

**user-invocable**（可选，默认 true）。是否允许用户手动 `/` 调用。如果一个 Skill 是"内部辅助"（模型自动用，不需要用户触发），设 false。比如"自动格式化输出"——用户不需要 `/format` 来触发。

**allowed-tools**（可选）。限制 Skill 内可用的工具列表，默认继承父级所有工具。**用法**：限制 Skill 的"权限"，比如 `code-review` Skill 只读不写：allowed-tools 列 `Read, Grep, Glob, Bash(git diff:*)` 等。**注意**：allowed-tools 是"白名单"不是"黑名单"，没列的工具 Skill 不能用。

**model**（可选）。指定 Skill 内使用的模型，默认用主对话模型。**用法**：用便宜的模型做"轻量工作"（格式化、检查），贵的模型做"重推理"（设计、规划）。比如格式检查用 haiku，复杂重构用 opus。

**agent**（可选）。指定子代理类型，**2026 年 Claude Code 还在演进这块**，通常不推荐使用。

## body 怎么写

body 是 SKILL.md 的正文——**具体的工作流**。

**3 个常见结构**：

**结构 1：清单（SOP）**

```markdown
## 步骤

1. 读取所有变更文件
2. 按"安全 / 性能 / 质量 / 错误"4 个维度逐个检查
3. 输出去重 + 按严重程度排序
4. 用 markdown 格式输出
```

**适合**：固定流程的任务（code review、test、deploy）。

**结构 2：模板（带变量的占位符）**

```markdown
## 模板

```python
# {filename}
{imports}

class {ClassName}:
    def __init__(self, {init_params}):
        {init_body}
    
    def {method_name}(self, {method_params}):
        {method_body}
```

**适合**：生成代码、文档、邮件、报告。

**结构 3：参考文档（FAQ / Spec / API 文档）**

```markdown
## 常见问题

**Q: [问题]**
A: [答案]

**Q: [问题]**
A: [答案]
```

**适合**：领域知识、规范说明、API 文档。

**3 个结构可以组合用**。我的习惯：
- 主体是**清单**（最稳定的部分）
- 包含 1-2 个**模板**（输出格式固定）
- 必要时附**参考**（外部 spec、API 文档）

## 描述 vs 触发条件 vs 工作流

很多人写 Skill 时搞混这 3 个：

**Description** = "做什么 + 何时触发"（1-2 句）
**When to use** = "详细的触发场景"（1 段）
**Body** = "具体怎么执行"（步骤 + 模板 + 参考）

**对应"if-then"逻辑**：
- Description = "做什么"（then 部分）
- When to use = "何时做"（if 部分）
- Body = "怎么做"（详细步骤）

写的时候**先把 description 写好**——它决定了 Skill 的"边界"。**然后再写 body**——具体怎么执行。**when_to_use 是 description 的补充**。

## 我自己写 Skill 的 5 步流程

1. **先写 description**（50 字内）——直到能把"做什么 + 何时用"讲清楚为止
2. **列出工作流**（5-10 步）——这是 body 的骨架
3. **加 1-2 个模板**（如果输出格式固定）——保证结果一致
4. **加 paths 限定**（如果 Skill 适用特定文件类型）——减少误触发
5. **测试 3 次**：第 1 次看是否触发；第 2 次看是否过度触发；第 3 次看输出质量

**测试通过才发布**。我自己 2026 年的标准：每个 Skill 至少测 5 个不同场景再正式用。

## 2 个真实写错的例子

**例子 1：description 太宽**

```yaml
# 错
description: 帮助处理代码
```

模型会在所有代码相关任务都触发这个 Skill，包括"格式化"、"优化"、"重构"——**全都不是这个 Skill 该干的**。

**修正**：
```yaml
description: 按团队规范审查代码变更（PR review）。只触发于代码审查场景。
```

**例子 2：body 写了太多无关内容**

```yaml
# body 错
这个 Skill 用于代码审查。我们团队 2020 年成立，当时只有 3 个工程师...
```

**问题**：模型会读这些无关内容，浪费 token，可能让"重要规则"被淹没。

**修正**：
- 删掉所有历史背景
- body 只写"怎么执行"——步骤、清单、模板
- 团队背景放在 CLAUDE.md（项目级固定），不是 Skill（按需加载）

下一章讲 Skills 的触发机制——description + when_to_use + paths 怎么组合决定"什么时候调用"。
