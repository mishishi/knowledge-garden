# 04. A2A 4 种协作范式

A2A 协议定义了 agent 间通信的语法和语义，但**怎么组织多个 agent 完成复杂任务**是个模式问题。2026 年业界主流有 4 种协作范式：管道、辩论、分层、市场。每种适合不同场景。

## 范式 1：管道（Pipeline）

**最简单、最常用**。agent 顺序执行，前一个的输出是后一个的输入。

```
[用户输入] → [Agent A] → [Agent B] → [Agent C] → [最终输出]
```

**例子**：研究综述生成。

```
[用户问题]
   ↓
[Search Agent] 搜 10 篇相关论文
   ↓ 论文标题 + 摘要列表
[Summarize Agent] 每篇生成 200 字摘要
   ↓ 论文摘要列表
[Synthesize Agent] 综合成综述
   ↓
[最终综述]
```

**优点**：实现简单、易调试、错误容易定位。每个 agent 单一职责。

**缺点**：串行执行慢，3 个 agent 总延迟 = 3 倍单 agent 延迟。不适合需要迭代 / 反馈的任务。

**适合场景**：线性流水线任务（数据 ETL、文档处理流水线、研究综述、内容生产流水线）。

## 范式 2：辩论（Debate）

**多个 agent 并行处理同一问题**，对比结果、投票或辩论后给最终答案。

```
[用户问题]
   ↓
[Agent A] [Agent B] [Agent C]  并行独立给出答案
   ↓       ↓       ↓
[Judge Agent]  对比 3 个答案，选最优 / 综合 / 重做
   ↓
[最终答案]
```

**例子**：投资决策。

```
[投资标的：NVDA]
   ↓
[看多 Agent] 给看多理由（基于财报、行业趋势）
[看空 Agent] 给看空理由（基于估值、风险）
[中性 Agent] 给中性分析（综合两边）
   ↓
[Judge Agent] 综合三份分析，给最终建议
   ↓
[最终投资建议]
```

**优点**：减少单 agent 的偏见。3 个 agent 互相校验，幻觉率显著降低。研究表明辩论模式的幻觉率比单 agent 低 30-50%。

**缺点**：成本高（3 倍 token）、耗时长、需要 Judge agent 本身能力强。

**适合场景**：高风险决策（投资、医疗、法律）、需要多视角分析的问题、答案需要可解释（每个 agent 的推理可见）。

## 范式 3：分层（Hierarchical）

**主 agent 拆任务、子 agent 执行、子 agent 报告**。最像真实组织架构。

```
[用户任务]
   ↓
[PM Agent] 拆解成 N 个子任务
   ↓       ↓       ↓
[Worker A] [Worker B] [Worker C]
   ↓       ↓       ↓
[PM Agent] 汇总子任务结果
   ↓
[最终输出]
```

**例子**：AI 软件开发团队。

```
[PM Agent] 接到"做一个用户登录功能"
   ↓ 拆成：需求分析、架构设计、代码实现、code review、测试
   ↓       ↓       ↓       ↓       ↓
[Analyst] [Architect] [Coder] [Reviewer] [Tester]
   ↓       ↓       ↓       ↓       ↓
[PM Agent] 汇总所有子任务的产出
   ↓
[最终交付]
```

**优点**：可扩展（Worker 可以并行）、任务清晰（PM 负责拆和汇总，Worker 负责执行）、容错（某个 Worker 失败，PM 可以重派或换 Worker）。

**缺点**：PM agent 是单点瓶颈。如果 PM agent 拆任务拆得不好，整个流程崩。需要 PM agent 本身能力强。

**适合场景**：复杂任务、需要专业分工、可以并行执行的任务、长期运行的 agent 系统（PM agent 持续在线接收新需求）。

## 范式 4：市场（Market）

**所有 agent 平权**，通过竞标 / 协商分配任务。最接近"自由市场"。

```
[任务发布]
   ↓
[任务市场] → 所有 agent 看到任务
   ↓       ↓       ↓       ↓
[Agent A 出价 X 元，3 分钟完成]
[Agent B 出价 Y 元，5 分钟完成]
[Agent C 出价 Z 元，2 分钟完成]
   ↓
[任务分配给最优出价方]
   ↓
[执行]
   ↓
[结算]
```

**例子**：动态 agent 团队。

```
[任务：翻译一段法律文本从中文到英文]
   ↓
[市场] 通知所有"翻译 agent"
   ↓
[LegalTranslation-A] 出价 $0.10，置信度 0.92
[LegalTranslation-B] 出价 $0.15，置信度 0.95
[GeneralTranslation-C] 出价 $0.05，置信度 0.70
   ↓
[委托人] 选 LegalTranslation-B（性价比最优）
   ↓
[B 执行翻译] 返回结果
```

**优点**：动态调度、资源最优、agent 生态良性竞争。

**缺点**：实现复杂、需要市场协议、需要出价 / 结算机制、不适合所有任务类型。

**适合场景**：agent 市场 / agent 商店、动态负载均衡、成本敏感的任务、agent 能力差异大的场景。

## 怎么选

| 任务类型 | 推荐范式 |
|---------|---------|
| 线性流水线 | Pipeline |
| 高风险决策 | Debate |
| 复杂多步任务 | Hierarchical |
| 动态 / 成本敏感 | Market |
| 不知道选啥 | Hierarchical（最通用）|

**实战经验**：80% 的生产 agent 系统用 Hierarchical（PM + Workers）。15% 用 Pipeline。4% 用 Debate。1% 用 Market。Market 是前沿但还不成熟。

## 混合范式

实际生产里很少用单一范式。常见的是 **Hierarchical 套 Debate**：

```
[PM Agent]
   ↓
[Analyst] [Architect] [Coder] [Reviewer] [Tester]
              ↓
         [Debate：3 个架构方案对比]
              ↓
         [选最优]
```

下一章展开讲 Pipeline 范式的实战细节——最简单的范式，最容易踩坑。