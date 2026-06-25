# 06. Isolate 策略：结构化与隔离

我见过最贵的 context 设计错误是 2024 年初。

一个 SaaS 客户做"智能分析师"产品，**单个 agent 试图做所有事**——查数据、写报告、绘图、发邮件、跟进客户。System prompt 8000 token，包含 47 条指令。Tools 列表 120 个。Knowledge base 30 个。

测试时表现很好——用户问什么它都能答。**上线 1 周后灾难**：
- 用户问"上周销售数据怎么样？"，agent 把 30 个 knowledge base 全部检索了一遍（因为 system prompt 说"用所有可用的资源"）
- 单次请求 4-8 秒，token 成本 $0.8
- 5% 的请求在 200K context 里塞满了，模型开始 hallucination
- **一周花了 1.2 万美元的 token 费，转化率只有 2%**

我帮他们重做的方案：**把 1 个超级 agent 拆成 5 个子 agent**，每个 agent 自己的 context，自己的 knowledge base，自己的 tools。**总准确率从 65% 涨到 92%，单次成本从 $0.8 降到 $0.05**。

**Isolate 策略的本质是：不要让一个 agent 试图做所有事。把不同任务隔离在不同的 context 里。**

## 3 种 Isolate 方法

**1. 多 Agent 隔离（Multi-Agent Isolation）**

主 agent 把任务分给子 agent，每个子 agent 有自己的 context。**子 agent 的 context 跟主 agent 的 context 隔离**。子 agent 完成后只返回"结果摘要"给主 agent。

```text
[用户] 
   ↓
[主 agent: 协调者，context 5K]
   ↓ (分任务)
   ↓-----------↓----------------↓-----------------↓
[数据子 agent] [报告子 agent] [邮件子 agent] [绘图子 agent]
context 15K   context 20K    context 8K      context 10K
   ↓ (返回摘要)
   ↓-----------↓----------------↓-----------------↓
[主 agent 汇总]
   ↓
[用户]
```

每个子 agent **不知道其他子 agent 的 context**。**主 agent 只看子 agent 的"结果摘要"，不看子 agent 怎么想出来的**。

**2. 结构化隔离（Structured Isolation）**

同一个 agent，**把 context 按结构分组**，每组之间不互相污染。比如：
- "系统指令"区：5K，固定不变
- "工具定义"区：3K，固定不变
- "任务输入"区：5K，每次变
- "工具结果"区：3K，最近 1-2 次
- "对话历史"区：4K，最近 5-10 轮
- "知识召回"区：5K，dynamic 召回

每组之间用 XML/Markdown 的明确分隔符（`<system>` `</system>` `<tools>` `</tools>`）。**模型被训练过识别这些分隔符，能清楚知道"这一段是 system、那一段是 user 提供的"**。

我自己的产品里**结构化隔离 + 子 agent 隔离**都做。前者减少单 agent 内的混乱，后者减少跨任务的干扰。

**3. 沙箱隔离（Sandbox Isolation）**

对于"危险操作"或"长时任务"，把 agent 隔离在一个沙箱里运行。沙箱有自己的 context、外部 API 权限、时间限制。**沙箱内可以自由探索，沙箱外只能看到"沙箱输出什么"。**

```text
[主 agent] 
   ↓ (启动沙箱：调查 X 用户最近 6 个月的所有订单)
   ↓
[沙箱 agent: ReadOnlyDatabaseQuery, 600 秒限时, 20K context]
   ↓ (返回："X 用户过去 6 个月有 12 笔订单，退款率 35%，主要原因是 Y")
   ↓
[主 agent 用这个结果继续决策]
```

**沙箱的好处是限制了"上下文失控"的影响**。即使沙箱内 agent 跑了 100 步用了 200K context，**主 agent 看到的还是 1-2K 的结果摘要**。

## 什么时候该 Isolate

判断标准：**这个任务是否需要独立的 context 视角？**

具体几个我自己的"Isolate 触发器"：

**1. 任务需要完全不同的 system prompt。** "写代码"和"审合同"是两个不同的角色。**别让一个 agent 在不同 mode 之间切换——为每个 mode 单独的 agent**。

**2. 任务需要不同的知识库。** "客服查询"和"销售预测"用不同的 knowledge base。**混在一起会让模型在召回时不知道用哪个**。

**3. 任务有"危险副作用"。** "查数据"是 read-only，"发邮件"是 send-only，"退款"是 modify-order。**危险副作用必须隔离，限制 agent 的工具集和权限**。

**4. 任务时长差异大。** "回答一句话"和"调研 10 篇报告"时间差 100 倍。**别让长任务拖慢短任务**。

**5. 任务结果会被多次重用。** "提取订单信息"会被客服、退款、风控、推荐 4 个场景重用。**这种"基础设施型"任务应该是一个独立 agent，输出稳定的结构化结果**。

## 隔离的"代价"

Isolate 不是免费的。3 个代价：

**1. 协调成本。** 主 agent 调度子 agent 需要"任务描述 + 上下文传递"。这个描述本身要花 token 写，**且描述不清楚 = 子 agent 跑偏**。

**2. 上下文断裂。** 子 agent 不知道主 agent 的"前面发生了什么"。**有些任务需要"长 context"才能理解**——强行切开会丢失关键信息。

**3. 调试复杂。** 单 agent 调试简单，看 prompt + response 就行。**多 agent 调试要追踪每个 agent 的状态，工具是 LangSmith / LangFuse / Helicone**。

**经验法则**：先做"单 agent + 好的结构化隔离"，跑通后再考虑"多 agent 隔离"。**过早多 agent 化是 2026 年最常见的工程错误之一。**

## Sub-agent 的"上下文传递协议"

子 agent 需要从主 agent 拿到一些 context 才能工作。但 **不能传全部**——会破坏隔离。**只传"完成这个子任务所需的最少信息"**。

我自己用的协议：
- `goal`: 子任务的目标（1-2 句）
- `constraints`: 约束条件（必填字段、合规要求、风格）
- `inputs`: 输入数据（订单号、用户 ID、文件路径）
- `output_schema`: 期望输出格式（JSON schema / 模板）
- `context_summary`: 必要的背景信息（2-3 句话，**不传完整对话**）

子 agent 只看这 5 段。**不传**：
- 完整对话历史（除非明确需要）
- 整个 system prompt（子 agent 有自己的）
- 其他子 agent 的结果（除非需要协作）

这套协议让多 agent 系统的总 token 成本**降低 50-70%**。

## 实战：客服系统的 Isolate 设计

回到前面那个客服 SaaS 案例。原来的 1 个超级 agent 拆成 5 个子 agent：

**Triage Agent**（分流）：
- context：用户消息 + 历史工单摘要（5K）
- tools：分类、优先级标记
- 输出：问题类型 + 紧急程度

**Knowledge Agent**（知识查询）：
- context：triage 结果 + 知识库检索（8K）
- tools：向量检索、文档查询
- 输出：相关文档 + 引用

**Action Agent**（执行操作）：
- context：knowledge 结果 + 用户订单信息（6K）
- tools：订单 API、退款 API、工单系统
- 输出：执行结果 + 状态

**Response Agent**（生成回复）：
- context：以上 3 个子 agent 的结果摘要（4K）
- tools：邮件模板、短信模板
- 输出：最终回复内容

**Escalate Agent**（升级处理）：
- context：当前问题 + 类似历史升级案例（5K）
- tools：人工工单创建
- 输出：升级工单 ID

**主协调 agent**：只负责调度，context < 3K。

**对比 1 个超级 agent**：
- 单次 token 成本：$0.8 → $0.05（94% 降）
- 首次解决率：65% → 92%（+27pp）
- 用户等待时间：8 秒 → 3 秒
- 复杂问题的处理：60% → 95%

**关键 insight**：每个子 agent 的 context 都很小（< 8K），但都"刚好够用"。**比 1 个 200K 的超级 agent 更准、更快、更便宜。**

## 2 个常被忽视的 Isolate 模式

**1. 用户的"沙盒视图"。** 让用户能看到"agent 当前在想什么、查了什么、用了什么工具"——但不让用户直接改 agent 的 context。**这是产品 UX 层面的 Isolate**。

**2. 时间隔离。** 长任务跑 30 分钟时，每 5 分钟"压缩一次 context"（用 Compress 策略），避免 context 无限增长。**这是时间维度的 Isolate**。

下一章讲工具调用——工具定义怎么写才不污染 context，MCP 怎么统一工具生态。
