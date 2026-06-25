# 03. CLAUDE.md 深入：项目记忆的写法

我团队 2025 年 12 月启用 Claude Code 的时候，遇到一个问题：**3 个工程师用 Claude Code 写的代码风格不一样**。

工程师 A 习惯 `const` 优先，工程师 B 习惯 `let`，工程师 C 喜欢用 `var`（老项目）。**每个工程师的 Claude Code 输出都跟自己的偏好一致**——**3 个人的 PR 看起来像 3 个项目**。

后来我们写了 CLAUDE.md。**3 个工程师的 Claude Code 输出立即一致了**。**3 个不同人的 PR 看起来像 1 个项目**。

这一章讲 CLAUDE.md 的**深入写法**——**不只是"项目说明"，是"团队的工程宪法"**。

## CLAUDE.md 的本质

CLAUDE.md 是**项目级"团队记忆"**——**每次新对话自动加载到 system prompt 头部**。

**类比**：
- **CLAUDE.md = 团队的入职培训手册**（新人入职第一天读的东西）
- **Skills = 团队的工具 SOP**（做特定任务时按 Skill 走）
- **MCP = 团队的工具集**（连接外部系统）

**CLAUDE.md 加载机制**：
- 项目级 `.claude/CLAUDE.md` 优先
- 全局 `~/.claude/CLAUDE.md` 兜底
- 子文件 `@import CLAUDE-CODING.md` 拆分加载

## CLAUDE.md 的 4 大原则

**1. 高频不变才放进来**

CLAUDE.md 加载在每次对话开头，**默认始终存在**。**内容要"每个对话都用得到 + 不怎么变"**。

**2. 短比长好**

CLAUDE.md 控制在 1-2K token。**超过就开始挤占 context**。**细节放 Skills**。

**3. 具体不抽象**

不要写"用好的代码风格"——**写"用 camelCase 命名变量，PascalCase 命名类"**。

不要写"做好测试"——**写"测试覆盖率 80% 起，关键路径必须有测试"**。

**4. 例子比规则好**

不要只列规则——**给 1-2 个正反例子**：

```markdown
## 错误处理

**正例：**
```typescript
try {
  await service.process(req.body);
} catch (e) {
  logger.error({ error: e, requestId: req.id });
  return { code: 500, message: 'server error' };
}
```

**反例：**
```typescript
// 错：裸 catch
try { await service.process(req.body); } catch (e) {}
```
```

**例子比规则更易遵循**。

## CLAUDE.md 的 8 个标准章节

我自己 2026 年用的项目 CLAUDE.md 模板（**8 个章节，按需删减**）：

```markdown
# 项目：[项目名]

## 简述
- 项目做什么
- 目标用户
- 核心价值

## 技术栈
- 语言 / 框架 / 数据库 / 工具

## 命名
- 变量 / 函数 / 类 / 文件 / 常量

## 架构
- 数据流方向
- 状态管理
- 错误处理

## 必做
- 每个 PR 必须做的检查
- 每个 commit 必须包含的信息

## 必不做
- 禁止使用的库 / 模式
- 常见的反模式

## 沟通
- 用什么语言回答
- 技术术语怎么处理
- 不要做什么

## 测试 / 部署 / 监控
- 测试标准
- 部署流程
- 监控指标
```

**8 个章节约 1500-2000 字**。**精简到刚好够**。

## 真实 CLAUDE.md 例子

我自己 side project 的 CLAUDE.md（**700 字以内**）：

```markdown
# 项目：knowledge-garden

个人知识库，部署在 GitHub Pages。

## 技术栈
- Python 3.11 + Pillow（构建脚本）
- HTML/CSS/JS（前端）
- 思源宋体 + 思源黑体（中文）

## 命名
- 文件：kebab-case（multi-agent.md 不是 multi_agent.md）
- CSS class：kebab-case
- 变量：camelCase
- 章节 slug：kebab-case 加数字前缀（01-why.md）

## 架构
- 构建：`python build_reader.py` → `index.html`
- 部署：GitHub Actions → GitHub Pages
- 不写 JS 框架（用原生 JS）

## 必做
- 每个新章节加 AI 味扫描（硬编号 / 表格 / h3 / ⚠️ emoji）
- 每个新章节控制在 1500-3000 字
- 章节开头用故事，不用"## 摘要"

## 必不做
- 不引入 React / Vue
- 不引入 TypeScript（项目小，不需要）
- 不用 emoji UI（用 SVG）

## 沟通
- 中文回答
- 代码示例用 TypeScript 风格但写 JS
- 不用"亲"、"您好"等过度礼貌

## 部署
- 推到 main → 自动构建 + 部署
- 5 分钟内生效
- 检查 `mishishi.github.io/knowledge-garden/`
```

**700 字**。**每次对话自动加载**。**新会话前 5 分钟"重新教学"省掉了**。

## 5 个 CLAUDE.md 实际用法

**1. 强制代码风格一致**

```markdown
## 命名
- 变量/函数：camelCase
- 类/类型：PascalCase
- 文件：kebab-case
- 常量：UPPER_SNAKE_CASE
```

**每次 Claude Code 输出代码，自动按这个规范**。**团队 review 不用纠结命名**。

**2. 强制架构一致**

```markdown
## 架构
- 数据流：UI → API → Service → DB
- 错误处理：try-catch + 统一 logger
- 状态管理：Zustand
- API 风格：RESTful
```

**每次 Claude Code 生成新代码，**自动按这个架构**。**避免"东一榔头西一棒槌"**。

**3. 强制必做检查**

```markdown
## 必做（PR 前）
- [ ] 跑测试
- [ ] 跑 lint
- [ ] 更新 CHANGELOG
- [ ] 自己 review 1 遍
```

**每次让 Claude Code 准备 PR，自动列这个 checklist**。**不再漏检查**。

**4. 强制禁止反模式**

```markdown
## 必不做
- 不用 `var`（用 `const` / `let`）
- 不用 `==`（用 `===`）
- 不用 `any`（用具体类型）
- 不用 `console.log`（用 logger）
```

**Claude Code 自动避开这些反模式**。**review 不用反复说**。

**5. 团队上下文的"快捷方式"**

```markdown
## 业务背景
- 用户是 [X 类型]
- 核心场景是 [Y]
- 收入模型是 [Z]
```

**Claude Code 自动知道业务背景——**不会问"这个项目做什么"**。

## 4 个反模式

**1. CLAUDE.md 写得太长**

```markdown
# 错（5K 字 CLAUDE.md）
（包含：所有规范、所有流程、所有 FAQ、所有历史）
```

**问题**：每次对话加载 5K 浪费。**好的 CLAUDE.md 1-2K**。

**2. CLAUDE.md 写得太抽象**

```markdown
# 错
## 代码风格
- 用好的命名
- 写清晰的代码
```

**问题**：Claude 不知道"好"是什么。**好的 CLAUDE.md 写具体的**：

```markdown
# 对
## 命名
- 变量/函数：camelCase
- 类/类型：PascalCase
- 文件：kebab-case
- 常量：UPPER_SNAKE_CASE
```

**3. CLAUDE.md 包含"项目特定"内容**

```markdown
# 错
## 业务
- 订单系统设计（仅本项目）

## 规范
- 我们的 CRM 数据格式
```

**问题**：换项目用不上了。**CLAUDE.md 应该是"通用 + 项目"两层**。

```markdown
# 全局 ~/.claude/CLAUDE.md
## 通用规范
- 用 TypeScript strict
- 不用 any
- 测试覆盖率 80%+

# 项目 .claude/CLAUDE.md
## 项目特定
- 业务：订单系统
- 规范：CRM 数据格式
```

**4. CLAUDE.md 引用 Skills 太多**

```markdown
# 错
## 规范
参考 Skill: code-review
参考 Skill: frontend-design
```

**问题**：CLAUDE.md 是"骨架"，Skills 是"工具"。**别让 CLAUDE.md 变 Skills 索引**。

## 子文件拆分

**CLAUDE.md 超过 2K 时，拆子文件**：

```text
.claude/
├── CLAUDE.md           # 主（1-2K）
├── CLAUDE-CODING.md    # 代码规范（1K）
├── CLAUDE-TESTING.md   # 测试规范（500 字）
└── CLAUDE-DEPLOY.md    # 部署规范（500 字）
```

**主 CLAUDE.md 用 `@import` 引用**：

```markdown
# 主 CLAUDE.md
@import CLAUDE-CODING.md
@import CLAUDE-TESTING.md

## 简短的全局规则
（200 字）
```

**拆的条件**：**主 CLAUDE.md 超过 2K**。**没超过就别拆**。

## 5 个"维护 CLAUDE.md"的最佳实践

**1. 季度 review**

每 3 个月看一次 CLAUDE.md——**新规则加进去，过时的删掉**。

**2. PR 修改 CLAUDE.md**

团队成员改 CLAUDE.md 走 PR review。**不要直接改主分支**。

**3. 写"为什么"不只写"什么"**

```markdown
# 差
## 规范
- 用 camelCase

# 好
## 命名
- 用 camelCase（参考 [Google TypeScript Style Guide](https://...)）
```

**给"为什么"——**让团队理解背景**。

**4. 引用而不复制**

```markdown
## 错误处理
参考 `docs/error-handling.md` 的完整规范
```

**完整规范放独立文档**——**CLAUDE.md 只放摘要**。

**5. 测试 CLAUDE.md 是否有效**

写完 CLAUDE.md 后，**新开会话，问 Claude Code 一个问题**——**看它是否按 CLAUDE.md 的规范回答**。

```text
用户：写个简单的 React 组件
Claude Code 输出：按你的命名规范（camelCase 变量、PascalCase 类、kebab-case 文件）
```

**不按规范就改 CLAUDE.md**。

## 真实数字：我自己的 CLAUDE.md 改进

**2025 年 12 月初版（2.5K）**：
- 触发准确率：70%（Claude 经常忽略一些规范）
- 团队抱怨：规范不一致

**改 3 次后（800 字）**：
- 触发准确率：92%
- 团队不再抱怨

**教训**：**CLAUDE.md 不是越长越好**——**具体 + 短 = 有效**。

## 1 个我犯过的大错

**2025 年 11 月我把项目所有规范写到 CLAUDE.md**——**5K 字**。

**问题**：
1. 每次对话加载 5K 浪费
2. 规范太多，Claude 反而抓不住重点
3. 加载 5K 后，重要的规范被淹没了

**改 3 步**：
1. 主 CLAUDE.md 减到 800 字
2. 详细规范拆 Skills
3. 业务背景放项目 README，不进 CLAUDE.md

**改完后规范执行率从 70% 涨到 95%**。

**反直觉**：**CLAUDE.md 短比长有效**。**"少即是多"在这里也成立**。

## CLAUDE.md + Skills 的工作流

**新工程师入职第 1 天**：

```text
1. 读 CLAUDE.md（800 字，5 分钟）
2. 知道团队"骨架规则"
3. Claude Code 自动应用这些规则

新工程师第 1 周：

1. 用 Claude Code 写代码
2. 触发 Skills（code-review / test-coverage / ...）
3. Skills 加载详细规范

新工程师第 1 个月：

1. 理解项目全貌
2. 知道哪些规范在 CLAUDE.md，哪些在 Skills
3. 可以自己写新 Skill
```

**CLAUDE.md = 入门 + 全局**。**Skills = 工具 + 细节**。**两者配合 = 完整的"团队工程宪法"**。

下一章讲 Skills + Hooks——**Claude Code 工作流自动化的核心**。
