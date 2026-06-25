# 01. 为什么需要 Context Engineering

2024 年中，我帮一个法律 SaaS 团队看他们的合同审查产品。团队里两个 prompt 工程师花了一周时间调 prompt，调完交付的 prompt 大概 800 字，里面塞满了 few-shot 示例、角色指令、格式要求、风格约束。开发把 prompt 接到产品里，测试时效果很好——5 个测试合同全部识别正确。

第 6 个合同长度翻倍，prompt 直接被截断。识别正确率掉到 60%。

团队第一反应是"prompt 调得不够细"。又调了一周，加更多示例、加更具体的指令、用了更贵的模型。合同长度继续增长到第 10 个测试样例，正确率反而掉到 45%。

第三周他们换了一个资深工程师来重构。这位工程师没动 prompt，而是改了一件事——**把 prompt 拆成两段**，第一段是"系统级"的固定指令（永远在 context 开头），第二段是"任务级"的动态内容（每次根据合同变）。然后在合同前处理阶段做了 2 件事：抽取关键条款（按章节切），按相关性排序选最相关的 5 个章节进 context。

正确率回到 90%。prompt 几乎没改。

这件事的教训是：**prompt 工程的天花板是"context 管理的天花板"**。当模型能力足够强（GPT-4 / Claude Opus 这一代），决定产品上限的往往不是"prompt 写得多好"，而是"context 里装了什么"。

## Context Engineering 的定义

Context Engineering 是在 LLM 推理时，**系统性地管理进入模型 context window 的全部信息**——不只是 user prompt，包括 system prompt、工具定义、对话历史、外部检索结果、记忆召回、文件附件、few-shot 示例、工具调用结果。

它跟 prompt 工程的差别用一句话讲清楚：

- Prompt engineering：**在 context window 内的固定位置写最好的指令**
- Context engineering：**决定整个 context window 内应该装什么、不装什么、按什么顺序装**

2025 年 7 月 arXiv 上发表的综述论文《A Survey of Context Engineering for Large Language Models》把这件事定义为独立学科。论文里说："Prompt engineering is a subset of context engineering."（prompt 工程是 context 工程的子集。）

## 为什么 2026 年突然重要

3 个具体原因。

**第一，模型变强了，但用户期望更高了。** GPT-3.5 时代产品能用就赢，prompt 写得差一点无所谓。Claude 3.5 / GPT-4o / Gemini 1.5 这一代，模型本身质量足够好，用户对"产品能不能用"的标准提了 3 倍。剩下能拉开差距的就是 context 设计。同样的模型，context 设计好的产品比 context 设计差的好 30-50% 准确率。

**第二，长 context 不等于好 context。** Claude 现在有 200K context window，Gemini 有 1M，GPT-4o 有 128K。"装得多"看似解决了问题，但实际是**装多了反而差**。论文里反复提到的 "Lost in the Middle" 现象：模型对 context 开头和结尾的信息记得最准，中间的部分准确率显著下降。一个 100K 的 context 实际有效利用率大概只有 60-70%。

**第三，agentic 应用爆发，context 管理成为第一瓶颈。** 2025 年起大部分 LLM 应用不再是单轮对话——是多步 agentic 系统（多次工具调用、多轮检索、长时记忆）。每一步的 context 设计都影响下一步。Context 失控 = agent 在 5 步之后开始 hallucination、重复操作、用错工具。**Context engineering 是 agentic 应用的操作系统层。**

## 4 大原则

2026 年社区对 Context Engineering 形成了 4 大原则的共识（来自 yeasy 的开源项目和 LangChain / Anthropic 的实践）：

- **Write**：把信息写出去（外部存储、记忆、文件）
- **Select**：从外部把信息选回来（检索、记忆召回、上下文组装）
- **Compress**：把 context 压到刚好够用（摘要、压缩、淘汰）
- **Isolate**：把 context 隔离在合适的边界（子 agent、沙箱、结构化）

4 个原则不是顺序的，是循环的。每一次 agent 决策：写什么到外部 → 选什么回来 → 怎么压缩 → 怎么隔离。**第 7 章到第 9 章会逐个展开。**

## 这一章先回答的 3 个问题

剩下的 9 章会按这个顺序：

1. **Context window 和 token 基础**（第 2 章）：100K context 实际能用多少？模型到底在读什么？
2. **Write 策略**（第 3 章）：什么该存外面？怎么组织记忆？
3. **Select 策略**（第 4 章）：RAG 不只是向量检索 + TopK，到底怎么选才准？
4. **Compress 策略**（第 5 章）：context 满了怎么办？摘要还是淘汰？
5. **Isolate 策略**（第 6 章）：多 agent 怎么分 context？子任务怎么隔离？
6. **工具与 MCP**（第 7 章）：工具定义怎么写才不污染 context？
7. **多 Agent context 管理**（第 8 章）：handoff 时 context 怎么传？
8. **自主 Agentic RAG**（第 9 章）：agent 自己决定查什么、查几次、查多深？
9. **生产反模式**（第 10 章）：5 个最常见的 context 灾难 + 怎么避

写完 10 章你会得到一件事——**当面对一个 LLM 应用问题，不再问"prompt 怎么改"，而是问"context 应该装什么"**。这两个问题的差别，就是 prompt 工程师和 LLM 系统工程师的差别。
