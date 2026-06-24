# 02. Agent Loop：把 `while not done` 展开成 8 种变体

> 第 1 章那个 8 行 `while not done` 是最小骨架。真实生产里它会变成什么样？这一章拆 8 种主流变体——每种适用场景、关键差异、我自己翻过的车。

## 为什么一个 loop 会有 8 种变体

去年我维护一个 agent 时遇到过这个问题：simple loop 跑 50 个任务，32% 完成率。然后我加了 reflection（每 3 轮 self-critique），完成率拉到 56%。再换 plan-and-execute，到 68%。最后混 sub-agent delegation + reflection，到 81%。

但每种变体不是免费的——它们各自有特定的失败模式。simple loop 卡死时没人知道它在想什么，plan-and-execute 的 plan 错了整个任务跑偏，sub-agent delegation 的成本翻 5-10 倍。

不存在"最好"的 loop——只有"最匹配当前任务"的 loop。下面 8 种按"agent autonomy 由低到高"排，越往后越自主、越复杂、越贵。

## Simple Loop（最基础）

```python
while not done:
    response = llm.call(messages + tools)
    if response.has_tool_use:
        result = execute(response.tool_use)
        messages.append(result)
    else:
        done = True
```

适用场景：单步任务、明确完成条件。比如"读文件 → 改一行 → 保存"。我做的小工具脚本大多这种。

翻车：第 N 轮 LLM 忘了最初目标、tool 失败 retry 不当、loop 卡死烧 token。

## ReAct（Reason + Act）

每轮强制让 LLM 输出 `Thought: ... Action: ... Observation: ...` 三段式，比 simple loop 多一个"显式 reasoning"环节。

```python
while not done:
    response = llm.call(f"{messages}\n\nThink step by step. Format: Thought: ... Action: ...")
    thought = extract(response, "Thought:")
    action = extract(response, "Action:")
    observation = execute(action)
    messages.append(f"Observation: {observation}")
```

ReAct 的好处是**可解释性**——每一轮你能看到 LLM 在想什么，比 simple loop 那种黑盒好调试。

适用场景：需要 audit trail 的场景（金融 / 医疗 / 法务）、tool 数量少（≤ 5 个）、单步决策链路短。

翻车：Thought 太长烧 token、LLM 编一个看起来合理但实际不存在的 Action、Observation 解析错误。我自己用 ReAct 时最容易栽在"LLM 把 Action 字段写成自然语言而不是 tool call"——必须加 robust parser。

## Plan-and-Execute（先规划再执行）

两阶段：先调一次 LLM 让它生成完整 plan（任务步骤列表），再逐步执行每一步。

```python
plan = llm.call("Plan step by step: " + user_task)  # 一次大调用
for step in plan.steps:
    result = execute(step)
    if not step_ok(result):
        plan = llm.call(f"Re-plan given failure: {result}")  # 失败重规划
```

Anthropic 的"Building Effective Agents"博客把这种叫 workflow——区别于 autonomous agent。

适用场景：任务结构清晰、可以一次性规划（比如"读 5 个文件 → 提取 API → 改 1 个文件 → 跑测试"）、需要给用户看 plan 再批准。

翻车：plan 错了整个任务跑偏——而且 LLM 一旦写好 plan 就很固执，不容易中途改。Re-plan 触发条件太严会让任务卡住，太松会无限重规划。我自己设的阈值是"step 失败 2 次 or 连续 3 步 plan 和实际偏离超过 50%"。

成本：plan 阶段 1 次大调用（输入长），执行阶段 N 次小调用。总体比 simple loop 便宜，因为避免了 simple loop 每轮重新思考的开销。

## Reflection（自我审视）

每 N 轮让 LLM 回头看自己过去 N 步的决策，self-critique 后修正下一步。

```python
while not done:
    response = llm.call(messages + tools)
    execute(response.tool_use)
    messages.append(response, tool_result)
    if step_count % 3 == 0:
        critique = llm.call(f"Critique last 3 steps. What's wrong? How to fix?")
        messages.append(f"[Self-reflection]: {critique}")
```

Stanford 2023 的 Reflexion 论文证明 reflection 能让 agent 完成率提升 20-30 个百分点——我自己的小规模实验从 32% 到 56%，差不多。

适用场景：multi-step 任务、tool 失败率高、LLM 容易跑偏的任务。

翻车：reflection 本身烧 token——每 3 轮额外 1 次 LLM 调用，cost 翻 1.5-2 倍。reflection 也可能让 LLM 过度自我怀疑，老是改方向不收敛。频率要调，我试过每 3 轮、每 5 轮、每 10 轮，3 轮性价比最好。

## Tree-of-Thought（多路径评估）

每一步生成 K 个候选 action，分别执行 K 个分支，最后选最优。

```python
while not done:
    candidates = [llm.call(messages, temperature=0.8) for _ in range(K)]
    branches = [execute(c.tool_use) for c in candidates]
    scores = [llm.call(f"Score this branch: {b}") for b in branches]
    best = max(zip(scores, candidates))
    messages.append(best[1], execute(best[1].tool_use))
```

适用场景：决策空间大、有明确评分标准（数学 / 代码 / 逻辑题）、可以并行执行。

翻车：成本是 simple loop 的 K 倍——K=3 就是 3x 烧钱。并行执行如果涉及副作用（写文件 / 调外部 API）会乱套。LLM 的 scoring 不一定可靠——评分 prompt 写不好就让 LLM 自己骗自己。我用 ToT 时把 scoring 拆给不同模型（主模型生成候选、Haiku 评分），效果稳定很多。

## Sub-Agent Delegation（主从代理）

主 agent 把子任务派给 sub-agent，sub-agent 独立跑完回报结果。

```python
def main_agent(task):
    subtasks = llm.call(f"Decompose into subtasks: {task}")
    results = []
    for sub in subtasks:
        sub_result = sub_agent(sub, own_tools=relevant_subset)
        results.append(sub_result)
    return llm.call(f"Synthesize: {results}")
```

Devin / Claude Code / Cursor agent mode 都用这种模式——主 agent 负责编排 + 决策，sub-agent 负责单一子任务（比如"读这个文件"、"跑这个测试"、"搜索这个 query"）。

适用场景：复杂任务需要不同 tool 子集、sub-task 之间相对独立、需要隔离失败。

翻车：成本爆炸——主 agent 1 次 + N 个 sub-agent 各 M 次 = (N×M+1) 次 LLM 调用。我跑的一个 10-subtask 任务烧了 $12。sub-agent 失败时主 agent 不知道内部发生了什么，调试非常痛苦。**sub-agent 必须返回 trajectory summary**（不是只返回 final answer），主 agent 才能合理重试或换路径。

## Human-in-Loop（关键决策点暂停问人）

在危险 / 不可逆 / 高成本决策点暂停，要求人类确认再继续。

```python
def execute_tool(name, args):
    if name in DANGEROUS_TOOLS:
        if not confirm(f"Allow {name}({args})? [y/N]"):
            return "Error: user denied"
    return actually_execute(name, args)
```

Anthropic 的 Claude Code 把这种模式做成"permission system"——第一次执行 `rm` 会问，以后类似命令自动放行或拒绝。Devin 也类似，关键操作强制审批。

适用场景：agent 能改文件 / 跑命令 / 发邮件 / 花钱、对外有副作用。

翻车：太频繁打断用户——我早期版本每个 tool 都问，5 轮对话问了 12 次，用户烦躁到卸载。太松又有真实风险。**我现在的策略：危险操作（删 / 写 / 跑命令）每次问；只读操作（grep / cat / search）不问；连续相同操作 5 分钟内不重复问。**

## Cost-Capped Loop（成本天花板）

主 loop 加 cost ceiling + step limit + token budget 三道闸。

```python
def run_agent(task, max_steps=25, max_cost=1.0, max_tokens=100_000):
    cost, tokens, step = 0.0, 0, 0
    while step < max_steps and cost < max_cost and tokens < max_tokens:
        resp = llm.call(messages)
        cost += calc_cost(resp)
        tokens += resp.usage.total_tokens
        # ...
    if cost >= max_cost:
        return f"Cost ceiling hit (${cost:.2f})"
    if step >= max_steps:
        return f"Max steps reached"
```

适用场景：**任何生产环境**——不设成本上限的 agent 等于财务自杀。

翻车：成本计算要准——Opus 输入 $15/M output $75/M，如果按 input/output 算错了一位小数，账单能差 10 倍。我用了 anthropic 官方的 pricing 表 + 每天 cron 对账一次实际账单。`max_cost` 设多少看任务——单次查询设 $0.10、multi-step 设 $1.0、长任务设 $5.0。

## 8 种变体怎么选

不是炫技选最好的，是匹配任务的 autonomy + 风险 + 成本。

我自己用的决策树：
- 单步明确任务 → Simple Loop
- 需要 audit trail + tool 少 → ReAct
- 任务结构清晰 + 步骤 ≤ 10 → Plan-and-Execute
- LLM 容易跑偏 → + Reflection
- 决策空间大 + 有评分标准 → Tree-of-Thought（成本敏感时慎用）
- 任务可拆解 + 子任务独立 → Sub-Agent Delegation
- 有副作用操作 → + Human-in-Loop
- 生产环境 → 必须 + Cost-Capped Loop（无论上面哪个）

实际项目我几乎都用 Plan-and-Execute + Reflection + Cost-Capped 三件套，偶尔加 Sub-Agent Delegation 处理重活。ReAct 只在 audit 必须的场景用，ToT 几乎不用（成本太高）。

## 这章踩过的几个关键坑

**Reflection 频率不能死板按 step count**——不同任务"反思频率"应该不同。数学任务每 1 步反思（错了就改），编程任务每 3-5 步反思（执行有惯性），研究任务每 10 步反思（信息密度高）。我后来改成"基于失败信号触发反思"——比如 tool 失败、连续 2 步同结果、cost 飙升——而不是按 step 数机械触发。

**Sub-agent 必须返回 trajectory，不只 final answer**——主 agent 看 trajectory 才能判断"sub-agent 是因为工具失败还是 prompt 模糊而失败"，不然只能盲目重试。早期我的 sub-agent 只 return final answer，主 agent 收到 `failed: timeout` 也不知道是网络超时还是 LLM 卡死。

**Human-in-Loop 的"deny"必须给 LLM 看**——用户拒绝一次操作，如果只 return `null`，LLM 不知道为啥，可能下次又尝试。我改成 return `Error: user denied. Ask user for clarification or try a different approach.`——LLM 收到后通常会问用户"那我应该怎么办"而不是死磕。

**Cost ceiling 要 soft，不是 hard**——直接 `if cost > 1.0: abort` 太粗暴。改成 `if cost > 1.0: ask user "Continue spending? Estimated $X more"`——给用户决定权而不是系统自己中断。

下一章 [03. Tool 设计](../03-tool-design/) 拆 harness 第二块基石——tool 的 schema、错误处理、retry、并行调用的具体写法。
