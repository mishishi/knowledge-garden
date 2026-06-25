# 08. 中文需求理解 / 国内工具链

2026 年 vibe coding 在国内有个绕不开的问题：**主流 vibe coding 工具（Claude Code / Cursor / Windsurf / Copilot）的中文需求理解都不行**。

我做过对比测试。同一段中文需求：

> "基于 Flask 写个用户列表查询接口，分页每页 10 条，支持按用户名模糊搜索，返回字段包括 userId、userName、registerTime。错误用全局 error handler 处理。数据库连接池大小设 20。"

**Claude Opus 4.7（Claude Code 后端）**：漏了"模糊搜索"的具体实现（生成 `==` 而不是 `LIKE`），漏了"连接池大小 20"的配置。

**TRAE（Doubao-1.5-pro）**：全部命中，中文需求理解据 CSDN 评测准确率比 Claude Code 高 12-18 个百分点。

这不是 Claude 模型不行——Claude Opus 4.7 在英文需求理解上是顶配。问题是**它的中文训练数据质量不如 Doubao / Qwen / DeepSeek 这一票国产模型**。

## 国内 vibe coding 工具现状

**TRAE**（字节跳动）— 2026 年国内 vibe coding 工具一哥。基础版免费，Pro 版解锁高级模型（Claude 3.5 Sonnet / GPT-4 / Doubao-1.5-pro / DeepSeek-V3.1 自由切换）+ Builder 模式 + 企业私有化。Work 模式兼顾终端 + IDE，中文需求准确率行业第一。

**通义灵码**（阿里）— 个人免费额度有限，企业版按团队收费。中文需求理解次优。基础补全强，复杂 vibe coding 流程偏弱。

**文心快码**（百度）— 文心一言系列，中文需求还行，但生态弱，工具集成少。

**CodeGeeX**（智谱）— 开源模型，可本地部署。中文 OK，但 IDE 集成体验差。

**DeepSeek-V3.1**（深度求索）— 模型本身强，可作为后端接 Claude Code / Cursor / Cline。中文理解强 + 代码能力强 + 价格低（API 1元/百万 token）。

## 海外 vs 国内工具选型

**做海外项目 / 英文文档 / 开源协作**：Claude Code / Cursor 是首选。模型最强（Claude Opus 4.7），英文需求理解一档。

**做国内项目 / 中文需求 / 国内合规**：TRAE 一站式解决，中文 + 私有化 + 免费三件套。Cline 接 DeepSeek-V3.1 是性价比之选。

**做企业内部项目 / 数据敏感 / 不能上云**：TRAE 企业版（私有化部署）或 Cline 接本地 Ollama 跑的 Qwen2.5-Coder-32B。

**预算 0 的独立开发者**：TRAE 基础版或 Cline + DeepSeek API。

## 中英混合 prompt 的写法

国内 vibe coding 实战中我发现一个反直觉的技巧：**写 prompt 时用中文描述业务，用英文描述技术**。

差写法（全中文）：

> "写一个 middleware 函数，校验 Authorization header 里的 JWT token，无效返回 401。"

AI 会把 `Authorization` 写成 `授权`、`middleware` 写成 `中间件`，但项目里其他文件都是英文命名，结果命名风格割裂。

好写法（中英混合）：

> "写一个 middleware 函数，校验 Authorization header 里的 JWT token，无效返回 401。注意：项目所有命名是英文（middleware / validateToken / 返回格式用 { code, message, data }），不要混用中文命名。"

这种写法 AI 一次到位。

## 中文需求的隐藏陷阱

**陷阱 1：歧义词**。"分页"中文既可以指 offset 分页也可以指 cursor 分页，AI 默认走 offset（最容易实现）。**口述时必须写死**：分页用 `limit + offset` 还是 `limit + cursor`。

**陷阱 2：业务术语**。电商的"SKU"、"SPU"、"客单价"，金融的"日切"、"头寸"、"敞口"——AI 不懂业务术语时会瞎猜。**口述时第一次出现的业务术语必须解释**。

**陷阱 3：法规**。"符合等保 2.0"、"日志保留 6 个月"、"敏感字段加密"——这些是国内合规要求，海外模型训练数据里基本没有。**口述时必须写明合规约束**。

## 中文 vibe coding 模板

我每个国内项目开头贴这份：

```
项目背景：[中文描述业务，英文命名规范]
技术栈：[NestJS / Spring Boot / Django]
本任务：[中文描述要做什么]
约束（中文业务 + 英文技术）：
- 业务术语：[本项目专有术语解释]
- 命名规范：[English only]
- 合规要求：[等保 / 个保法 / 行业规范]
- 性能约束：[禁止 N+1，分页规则]
- 安全约束：[禁止密钥硬编码，写接口必加鉴权]
验收标准：[怎么算做完了]
```

写好这份模板，复制粘贴到每个新需求开头。

下一章聊 vibe coding 的边界——什么时候该停、什么时候必须回到逐行阅读。