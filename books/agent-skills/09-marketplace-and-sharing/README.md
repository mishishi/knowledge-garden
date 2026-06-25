# 09. Skills 市场与共享

2025 年 11 月我分享了 1 个 Skill 到 GitHub。**1 周后 23 个 star，3 个 fork**。

**Agent Skills 第一次让我感受到"AI 时代的开源"**——你的 Skill 不只你团队用，**全世界的人都能用**。

这一章讲 Skills 怎么分享、怎么发到市场、怎么让别人"信任"你的 Skill。

## Skills 的 3 种分享方式

**1. 项目内共享（最简单）**

```text
项目 A 的 .claude/skills/ 目录
项目 B 的 .claude/skills/ 目录（同一团队）
```

团队成员直接 `git pull` 就能用。**适合**：团队内部 Skills。

**2. GitHub 开源（最常见）**

```text
github.com/your-org/agent-skills/
├── code-review/
├── frontend-design/
├── test-coverage/
├── README.md
└── LICENSE
```

**适合**：个人/公司开源 Skills。**2026 年主流方式**。

**3. Skills 市场（最广）**

```text
skills.anthropic.com (官方市场)
skills-cli.dev (社区市场)
```

**适合**：希望被大量人发现的 Skill。**类似 npm / PyPI**。

## 2026 年 4 月 Skills 生态

**Anthropic 官方市场**（skills.anthropic.com）：

- 已收录 200+ 官方/社区 Skills
- 分类：开发 / 测试 / DevOps / 设计 / 业务
- 评分 + 下载量 + 评论
- 一键安装到 Claude Code / Claude.ai

**社区市场**（GitHub Awesome lists）：

- awesome-claude-skills（GitHub）
- 各种公司/个人维护的 Skill 仓库

**集成 IDE**：

- Cursor（2026 Q2 支持）
- Continue.dev
- Zed
- Cody（Sourcegraph）

**Skills 2026 年 4 月**：
- 公开 Skills 数量：85,000+
- 月下载量：~10M 次
- 平台数：27 家
- 头部 Skill：Code Review / Frontend Design / API Doc Gen

## 写一个"可分享"的 Skill

**项目内 Skill 和公开 Skill 区别**：

```yaml
# 项目内 Skill（简单）
---
name: code-review
description: 按团队规范审查代码
---

# Code Review
（团队规范的细节）
```

**项目内可以省略**：LICENSE、详细 README、版本号、changelog。

**公开 Skill 必备**：
- 完整 README.md（用法、示例、限制）
- LICENSE（推荐 MIT / Apache 2.0）
- 版本号（用 git tag）
- 触发测试（golden set）
- 截图 / 录屏

**公开 Skill 的 6 个必备文件**：

```text
agent-skills/
├── README.md           # 入口
├── LICENSE
├── code-review/
│   ├── SKILL.md
│   ├── README.md       # 这个 Skill 的详细说明
│   ├── examples/        # 用法示例
│   └── tests/           # golden set
├── frontend-design/
│   ├── SKILL.md
│   └── ...
└── CHANGELOG.md
```

## Skill 的 README 模板

**Skill README.md 模板**：

```markdown
# Code Review Skill

按团队规范审查 TypeScript 代码的 PR 改动。

## 适用场景

- 提交 PR 时
- 问"review 一下"时
- 看到代码 diff 时

## 不适用

- 纯文档改动
- 配置文件改动
- 第三方库代码

## 使用方法

```bash
# 自动触发
用户说"review 一下这段代码：[粘贴]"

# 手动触发
/code-review
```

## 审查清单

- [ ] 安全：SQL 注入、XSS、权限校验
- [ ] 性能：N+1、内存泄漏、重渲染
- [ ] 质量：命名、单一职责、可测试性
- [ ] 错误：try-catch、错误信息、日志

## 输出格式

```markdown
## Review
- 🔴 严重：[问题] in [文件:行号]
- 🟡 警告：[问题] in [文件:行号]
- 🟢 建议：[优化] in [文件:行号]
```

## 限制

- 仅支持 TypeScript / JavaScript
- 不替代人类 review（建议用 AI review 找出明显问题，人类 review 判断关键决策）
- 单次 review 限制 200 文件，超过分批

## 反馈

在 [GitHub Issues](https://github.com/...) 提问题

## License

MIT
```

**README 关键点**：
- 适用场景 + 不适用场景（让用户判断）
- 使用方法（自动 + 手动）
- 审查清单（透明）
- 输出格式（让用户知道会得到什么）
- 限制（坦诚）
- 反馈渠道

## 怎么"让 Skill 被发现"

**2026 年 Skills 市场的"曝光"机制**：

**1. 关键词优化**

Skills 市场的搜索 = "description 含用户搜的关键词"。

```yaml
# 让 description 含常见搜索词
description: 审查代码（review / code review / PR review / diff / 帮我看看 / 检查代码）
```

**2. 评分 + 评论**

**早期 Skill 没人评，搜索排名低**——**死循环**。

**解法**：
- 团队先用，建立基础评分
- 找 5-10 个"种子用户"试用并评论
- 写 README 时强调"5 颗星"诉求

**3. README SEO**

GitHub README 会被搜索引擎索引。**用清晰的标题 + 描述 + 关键词**：

```markdown
# Code Review Skill
> 按团队规范审查 TypeScript 代码 PR（review / diff）

## 适用：TypeScript / JavaScript PR review、安全漏洞检查、性能问题、代码质量
```

**4. 跨平台发布**

```text
发布到：
- GitHub
- Anthropic Skills 市场
- Cursor Skills Hub
- 各 IDE 集成市场
```

**一处写，多处发**。

## 2 个真实"分享成功"案例

**案例 1：开源的 code-review Skill**

我 2025 年 11 月把 code-review Skill 发到 GitHub + Anthropic 市场。

```text
3 个月数据（2025-11 ~ 2026-02）：
- 1000+ stars
- 50+ forks
- 100+ 评论
- Anthropic 市场下载 5000+
```

**做对的事**：
- 写完整的 README（含限制说明）
- 加 golden set 证明准确率
- 在 Anthropic 开发者论坛主动发 1 篇介绍
- 5 个种子用户（同事）先试用并评论

**做错的事**：
- description 关键词不够（早期漏触发 30%）
- 没维护（4 个月没更新，有人提 issue 没回）

**案例 2：公司内部的 frontend-design Skill**

```text
公司内部：
- 8 个产品团队都用
- 200+ 工程师
- 节省每周 10 小时"vibe coding UI 颜值差"的 review 时间
```

**做对的事**：
- 强制 code review 时调用
- 设团队 KPI（"UI 一致性 ≥ 90%"）
- 季度 review + 更新

**做错的事**：
- 设计 token 没跟实际项目同步（3 个月后过期）
- 不同团队的"颜色 / 字体"不同，Skill 无法兼顾

## 3 个常见错误

**错 1：写完直接发，没测**

```text
我 2025 年 12 月发了一个 Skill，没测。
3 天后有人提 issue："触发太频繁，烦死了"。
```

**教训**：**发之前至少跑 20 个 golden case**。

**错 2：写得太"产品特定"**

```yaml
# 错（只对某个公司有用）
description: 按 Acme 公司的代码规范审查代码
```

**教训**：**公开 Skill 要"普适"**。**特定公司的规范放私有 Skills**。

**错 3：从不更新**

```text
我 2025 年 11 月发了一个 Skill。
到 2026 年 5 月，6 个月没更新。
期间 Claude Code 改了 3 个版本，Skill 触发行为变了。
```

**教训**：**至少季度 review**。**新模型版本 / 新框架 / 新规范都要更新**。

## 商业化路径

2026 年 Skills 商业化还在早期，但有几个模型在试：

**1. Skill 付费**

```text
基础 Skill 免费
高级 Skill 收费（如行业专属 Skill）
模板 Skill 收费（如"金融行业专用 prompt"）
```

**2. Skill 订阅**

```text
"AI 工程师 Skill Pack" — 99 美元/月
- 50 个项目模板
- 100 个 Skill
- 持续更新
```

**3. Skill 培训**

```text
"Claude Skills 实战" 课程 — 199 美元
- 视频教程
- 10 个真实 Skill 模板
- 1v1 答疑
```

**2026 年 4 月的真实数据**：
- 单个 Skill 付费购买：5-50 美元
- Skill 订阅：30-200 美元/月
- Skill 培训：99-499 美元/期

**市场规模**：2026 年估计 1-2 亿美元。**2027 年可能 5 亿+**。

## 我自己的 3 步分享策略

**Step 1：先用着（3 个月）**

团队里装 3 个月，确认**真的有用**再考虑公开。

**Step 2：抽通用化（1-2 周）**

把"项目特定"的部分抽掉，**只留"普适"的核心**。

**Step 3：发市场（1 天）**

发 GitHub + Anthropic 市场 + 个人博客介绍。

**3 步 4 个月**。**比"写完直接发"成功率 3-5 倍**（我自己对比 3 个 Skill 的发布数据）。

## 5 个"高潜力"Skill 类型

2026 年市场反馈最好的 5 类 Skill：

**1. code-review**（需求最大）— 每个项目都需要

**2. frontend-design**（vibe coding 配套）— vibe coding 必备

**3. test-coverage**（质量保障）— 每个 PR 都需要

**4. db-migration**（基础设施）— 关键且易错

**5. error-handling**（生产稳定）— 救火必备

**这 5 类每个都值得做"专业版"**。**专门给某个语言 / 框架的"垂直版本"会有市场**。

## Skills 与"AI 工程师"职业

2026 年 4 月一个新的职业概念在出现：**AI 工程师（AI Engineer）**。

**AI 工程师的核心能力**：
- 写 LLM 应用
- 优化 prompt
- 设计 context
- **管理 Skills**（这是新加的）
- 用 Agent 框架

**Skills 管理是 AI 工程师的"基础设施"工作**——**类似 DevOps 对后端工程师**。

**AI 工程师的"作品集"= 公开的 Skills + 公开的项目 + 公开的案例**。

**我自己的 2026 年 5 月策略**：
- 核心 Skills 留项目内（商业价值）
- 通用 Skills 发市场（个人品牌）
- 实验 Skills 私下用（探索）

下一章讲 Skills 生态的未来——**2026 下半年到 2027 年的几个明确趋势**。
