# 06. 辩论模式（Debate）实战

辩论模式是 4 种协作范式里**最烧 token、最慢、但答案质量最高**的范式。2026 年它在两个场景爆发：高风险决策（投资 / 医疗 / 法律）、需要可解释的答案（每个 agent 的推理可见）。

## 核心思想

让多个 agent **独立**处理同一问题，对比结果，由 Judge agent 决定最终答案。直觉是：3 个独立的脑子比 1 个脑子更不容易犯错。

学术依据来自 MIT 2023 年的研究 "Improving Factuality and Reasoning through Multiagent Debate"——多 agent 辩论能让 LLM 在数学、事实性、推理任务上的准确率比单 agent 提升 **15-30%**。

## 真实案例：法律合同审查

**场景**：客户上传一份 SaaS 服务协议，要求"找出对客户不利的条款并给出修改建议"。

**Debate 结构**：

```
[合同文本]
   ↓
[Agent A：保守派] 找出所有"对客户不利"的条款 + 修改建议
   ↓
[Agent B：激进派] 找出所有"对客户有利"的条款 + 修改建议
   ↓
[Agent C：中立派] 综合两边观点，给出平衡分析
   ↓
[Judge Agent] 综合三份分析，给最终审查意见
   ↓
[最终输出]
```

**单跑一次耗时**：60-90 秒。**成本**：约 $2-3（4 个 agent 调用，每个 200K token context）。

## 三个关键设计决策

**决策 1：几轮辩论**

最少 1 轮（每个 agent 独立给答案），最多 3-5 轮（agent 之间互相看对方答案、修改自己答案）。

**实战经验**：

- 1 轮：成本最低，质量提升有限
- 2 轮：第一轮独立给答案，第二轮互相反驳，质量显著提升
- 3 轮：边际效益递减，成本翻倍
- 4+ 轮：基本无收益，纯烧钱

**推荐 2 轮**。我们 A/B 测试对比 1 轮 vs 2 轮 vs 3 轮：

- 1 轮：幻觉率 12%
- 2 轮：幻觉率 5%
- 3 轮：幻觉率 4%

2 轮到 3 轮的提升不值得翻倍成本。

**决策 2：agent 之间看不看对方答案**

**两种模式**：

**盲辩论（Blind Debate）**：每个 agent 独立给答案，看不到其他 agent 的输出。

- 优点：避免"羊群效应"（agent 看到别人的答案后趋同）
- 缺点：可能出现 3 个 agent 给完全不同的答案，Judge 难选

**看辩论（Open Debate）**：每个 agent 看到其他 agent 的输出，可以反驳。

- 优点：互相校验、互相完善
- 缺点：羊群效应、绕弯路

**实战推荐**：**第一轮盲辩论，第二轮看辩论**。先用盲辩论收集不同视角，再用看辩论互相校验。

**决策 3：Judge agent 怎么选答案**

**三种策略**：

- **投票**：3 个 agent 各自给出选项 + 置信度，Judge 选最高票。
- **综合**：Judge 把 3 个答案融合成一个（类似多份报告合并）。
- **重判**：Judge 完全忽略 3 个 agent 的答案，自己重新做一遍。

**实战推荐**：**综合 + 重判结合**。Judge 先综合 3 份答案，再针对关键点重判。这比纯投票质量高 18%，比纯重判成本低 60%。

## Debate 范式的代码骨架

```python
async def debate(question, num_agents=3, rounds=2):
    agents = [
        Agent(role="conservative", system_prompt=CONSERVATIVE_PROMPT),
        Agent(role="aggressive", system_prompt=AGGRESSIVE_PROMPT),
        Agent(role="neutral", system_prompt=NEUTRAL_PROMPT),
    ]
    
    # Round 1: 盲辩论
    answers = await asyncio.gather(*[a.answer(question) for a in agents])
    
    # Round 2: 看辩论
    if rounds >= 2:
        for i, a in enumerate(agents):
            other_answers = [answers[j] for j in range(len(agents)) if j != i]
            answers[i] = await a.refine(question, other_answers)
    
    # Judge
    judge = JudgeAgent()
    final = await judge.synthesize(question, answers)
    
    return final
```

## Judge agent 的 prompt 设计

Judge agent 是 debate 范式的灵魂。Prompt 模板：

```
你是 3 个独立分析 agent 答案的最终裁判。
你的职责是综合 3 份分析，给出最准确、最全面的最终答案。

输入：
- 用户原始问题：[question]
- Agent A 的分析：[answer_a]
- Agent B 的分析：[answer_b]
- Agent C 的分析：[answer_c]

判断要点：
1. 如果 3 份分析一致 → 直接采纳
2. 如果有冲突 → 找出冲突根源，给出你的判断 + 理由
3. 如果有共同遗漏 → 补充遗漏的关键点
4. 必须给出置信度评分（0-100）和主要风险点

输出格式：
- 最终答案
- 综合理由
- 置信度
- 主要风险
```

## 真实成本数据

我跟踪了一年 debate 范式的成本：

| 任务类型 | 单 agent | Debate 3 agents | 成本倍数 |
|---------|---------|----------------|---------|
| 简单事实问答 | $0.02 | $0.06 | 3x |
| 投资分析 | $0.50 | $2.00 | 4x |
| 法律审查 | $1.00 | $4.50 | 4.5x |
| 医疗诊断 | $2.00 | $9.00 | 4.5x |

辩论模式平均成本是单 agent 的 **4 倍**。只有在答案价值高、错误成本大的场景才划算。

## 适用 / 不适用

**适合**：投资 / 医疗 / 法律 / 战略决策、需要可解释性（多个 agent 推理可见）、需要对抗单 agent 偏见。

**不适合**：高频低延迟任务（成本 4 倍受不了）、简单问题（杀鸡用牛刀）、实时聊天（用户等不了 60 秒）。

下一章讲 Hierarchical 范式——最通用、最像真实组织架构的模式。