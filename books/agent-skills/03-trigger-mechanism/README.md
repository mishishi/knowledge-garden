# 03. Skills 触发机制

我 2025 年 12 月犯过一个错。

我写了一个 Skill 想"自动写测试"。description 写的是"写单元测试"。我以为模型会在我每次说"补测试"时自动调用。

**实际上模型根本没调用**。我连续问 3 次"给这个函数加测试"，3 次它都没用 Skill 写。

我以为 Skill 写错了。**实际是 description 没匹配用户问题**。

这一章讲 Skills 的触发机制——**description / when_to_use / paths 怎么决定"模型什么时候调"**。

## 2 种触发方式

**1. 手动触发（`/` 命令）**

用户在 Claude Code 里输入 `/skill-name`，直接调用。

**适用**：
- 用户明确知道要用某个 Skill
- Skill 是"我就是要这个"
- 调试 Skill 时手动调用测效果

**2. 自动触发（语义匹配）**

模型读所有 Skills 的 `description` + `when_to_use`，语义匹配当前对话，**判断是否调用**。

**适用**：
- 用户没明确说要 Skill，但任务"看起来"匹配
- Skill 是"模型应该想到"的能力
- 日常对话里大量使用

**两种触发的关系**：手动触发**总是**调用。自动触发**只在**模型判断匹配时调用。

**默认行为**：user-invocable=true（允许手动）+ 自动语义匹配（默认开）。**省略 when_to_use 即可实现"仅手动触发"**——模型不会自动判断。

## 触发决策的 3 步过程

模型决定"调不调这个 Skill"的过程：

**Step 1：候选筛选（paths 过滤）**

如果 Skill 有 `paths` 字段，模型先看"对话涉及的所有文件"是否匹配 glob。**不匹配的 Skill 直接出局**。

```yaml
# 例子
paths: ["**/*.ts", "**/*.tsx"]
```

只有对话涉及 .ts/.tsx 文件时，这个 Skill 才被考虑。

**Step 2：语义匹配（description + when_to_use）**

候选 Skill 进入语义匹配阶段。模型读 description（+ when_to_use），与当前对话对比。

```yaml
description: 按团队规范审查代码变更（PR review）。检查安全漏洞（SQL 注入、权限校验）、性能问题（N+1）、代码质量、错误处理。
```

模型判断"用户当前在讨论 PR review"→ 匹配 → 进入 Step 3。

**Step 3：调用决策**

模型结合"匹配度"和"必要性"决定调不调。

- 匹配度高 + 必要 → 调
- 匹配度中 + 必要 → 调
- 匹配度高 + 不必要 → 不调
- 匹配度低 + 必要 → 不调

**"必要性"由模型自己判断**。比如用户问"什么是 TypeScript"——虽然 description 涉及代码，但**当前任务不需要 code review Skill**。

## 怎么写好 description（让模型准确触发）

我自己的 5 条经验：

**1. 用具体术语，不用抽象概念**。

```yaml
# 差
description: 处理代码相关任务

# 好
description: 按团队规范审查 TypeScript/React 代码的 PR。检查安全（XSS、SQL 注入）、性能（重渲染、内存泄漏）、代码质量。
```

**差**的描述"代码相关"匹配一切代码场景，**会过度触发**。**好**的描述"PR 审查 + TypeScript/React"匹配精确。

**2. 包含用户可能用的关键词**。

```yaml
description: 审查 PR（review code / code review / 帮我看看这段代码）
```

把"PR / review / code review / 帮我看看"都列出来——这些是用户可能说的具体词。

**3. 包含"何时不用"**（如果有边界）。

```yaml
description: |
  审查 PR 改动（src/ 下的代码）。检查安全、性能、质量。
  不适用于：纯文档、配置文件、测试文件。
```

**"不适用"明确告诉模型边界**，减少误触发。

**4. 描述里给出"使用场景"，不只给"功能描述"**。

```yaml
# 差（只说功能）
description: 把函数包装成 async/await 风格

# 好（说功能 + 场景）
description: 把回调地狱的代码改写成 async/await 风格。适用于：用户说"重构这段回调"、问"能不能用 promise 改"、看到 callback hell 时代码时。
```

**好**的描述把"用户可能说的话"也写进去，模型匹配命中率更高。

**5. 描述里**不要**写"如何实现"，只写"做什么 + 何时用"**。

```yaml
# 错（写了实现细节）
description: 用 try-catch 包装函数 + 用 p-retry 重试 + 加日志

# 对（只写外部可见的）
description: 给函数加错误处理 + 重试 + 日志。适用于：用户说"加错误处理"、"加 try-catch"、"网络重试"。
```

实现细节放 body，description 只描述"外部行为"。

## paths 的 3 个实战用法

**用法 1：限定到具体目录**

```yaml
paths: ["src/api/**"]
```

只触发于 src/api/ 下的文件改动。

**用法 2：限定到文件类型**

```yaml
paths: ["**/*.py", "**/*.ipynb"]
```

只触发于 Python 文件。

**用法 3：组合多个 glob**

```yaml
paths:
  - "src/**"
  - "tests/**"
  - "scripts/**"
  - "!**/node_modules/**"  # 注意：目前 Claude Code 不支持 ! 排除
```

**注意**：2026 年 Claude Code 的 paths 不支持 `!` 排除语法。要排除文件，靠 paths 的"白名单"性质 + 触发判断。

## 触发失败的 4 个常见原因

**1. description 太抽象**（"代码相关"）→ 模型不知道什么时候用 → 不触发

**2. description 太具体**（"审查 src/api/user.ts 里的 TypeScript 异步函数"）→ 模型只在精确匹配时用 → 漏触发

**3. 关键词不匹配**（用户说"看看这个"但 description 里没"看看"）→ 语义不匹配 → 不触发

**4. paths 限制太死**（paths: ["src/api/v2/**"] 但用户在 v1 目录）→ 不在 paths 内 → 不触发

**调试方法**：
1. 触发时看 Claude Code 输出的"using skill X"日志
2. 不触发时在对话里说"用 code-review skill 看一下"（手动触发）验证 Skill 内容
3. 修改 description 后重启 Claude Code（缓存）

## 多 Skill 同时匹配的决策

一个对话里可能多个 Skill 都"匹配"。**模型怎么选**？

**优先级规则**（Claude Code 2026 默认）：
1. **paths 匹配最具体的 Skill 优先**（比如 paths: ["src/api/**"] 比 paths: ["src/**"] 更具体）
2. **description 长度适中的 Skill 优先**（过长过短都不好）
3. **最近调用的 Skill 优先**（避免来回切换）
4. **手动 `/` 调用的最高优先级**

**实战**：
- `code-review` paths: ["src/**"]
- `frontend-design` paths: ["**/*.tsx"]
- 在 `src/components/Button.tsx` 改动时：两个 Skill 都候选，**frontend-design 优先**（路径更具体）

**陷阱**：**避免多个 Skill 的 paths + description 大量重叠**。**否则模型在不同 Skill 之间反复切换**。

## 我自己装 Skill 的最佳实践

我项目里 Skills 配置的 5 个原则：

**1. 一类任务一个 Skill**。**code-review** 专门审查，**code-format** 专门格式化，**test-gen** 专门生成测试。**不要一个大 Skill 包所有事**。

**2. paths 限定要准**。**frontend-design** 只配 `.tsx/.css/.scss`；**code-review** 配 `src/**`（不限文件类型）；**test-gen** 配 `src/**/*.{ts,tsx}`。

**3. description 含"否定词"**。"不适用于：纯文档"比单写"用于代码"更准。

**4. 一个项目的 Skills ≤ 15 个**。多了就开始互相干扰。**真需要更多——拆项目**。

**5. 每次加新 Skill 都测 5 个场景**。触发、过度触发、漏触发、输出质量、回归测试。**测完才发布**。

## 调试触发问题

Skill 不触发时的 3 步调试：

**Step 1：看 description 是不是清晰**

打开 SKILL.md，把 description 念出来——"如果我是 Claude，看到这个 description，我会在 X 任务时调用吗？"

如果答案是"不知道"——description 写得太模糊，重写。

**Step 2：看 paths 是不是过严**

用 `**/*` 临时放宽 paths，看 Skill 是否触发。如果是，**paths 写错了**。

**Step 3：手动 `/skill-name` 验证 Skill 内容**

如果手动能调，**说明 Skill 内容正确，是触发条件写错**。

下一步是修 description + when_to_use + paths。

下一章讲 CLAUDE.md vs Skills 的分工——**哪些放哪里的边界问题**。
