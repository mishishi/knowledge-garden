# 09. 实战：2 个 Side-Project 串起来

> 写中。先看 ch01-08。

前面 8 章都在拆概念。这一章做两个真东西：AI 内容工厂（researcher + writer + editor 全自动）+ PR 代码评审 Multi-Agent（diff 收集 + 静态分析 + AI review + 评论草稿）。每个项目从需求到代码到跑通都过一遍。

## 项目 1：AI 内容工厂

**场景**：你运营一个 newsletter，每周要发 3 篇深度文章。以前要花 5 小时：调研 2h + 写作 2h + 校对 1h。改成 Multi-Agent：

- **Researcher Agent**：给定主题，搜 10 篇相关文章，提炼 3 个核心观点 + 关键事实
- **Writer Agent**：基于事实写 1500 字初稿
- **Editor Agent**：审校（语法、逻辑、可读性），输出可发布版本
- **Publisher Agent**（可选）：发到 Ghost / Substack API

预计节省 70% 时间。重点是**怎么设计 Writer 的 prompt 让它不编事实**。

## 项目 2：PR 代码评审 Multi-Agent

**场景**：你公司每天 50+ PR，以前 review 跟不上。改成 Multi-Agent 自动 review：

- **DiffReader Agent**：从 GitHub PR URL 拉 diff，结构化提取
- **ArchitectureReviewer**：检查分层、依赖、模块边界
- **PerformanceReviewer**：检查 N+1 查询、内存分配、循环复杂度
- **SecurityReviewer**：检查 SQL 注入、XSS、密钥泄露
- **TestReviewer**：检查测试覆盖率、边界 case
- **LeadReviewer**：汇总 4 个 reviewer 的意见，按严重程度分级

人类 review 只看 LeadReviewer 给「需要人工确认」的 case。预计把 review 时间砍 50%。

## 大致会覆盖

- 项目结构 + CrewAI Flow 怎么组织
- 真实代码（不是 toy example）——直接能跑
- 跑通后怎么评估（output quality、token 成本、误报率）
- 怎么从「demo」升级到「能上线」

## 下篇

[10. 公司生产案例：3-5 个真实公司怎么用](../10-prod-cases/) — 公开声明过用 CrewAI 的公司，他们怎么用、用 CrewAI 哪个特性、解决了什么、踩过什么坑。
