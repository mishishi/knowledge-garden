# Multi-Agent：当一个 Agent 不够用的时候

我第一次认真考虑 multi-agent 架构，是 2024 年 3 月。那时候我们在做一个代码 review 的工具，单 Agent 方案就是把所有 diff 丢给一个 model，让它输出 review comments。听起来挺合理对吧？跑了一周发现，这个 Agent 要同时干四件互相打架的事：理解代码语义、检查安全漏洞、判断风格合规、给出可读性建议。结果就是它在四个维度上都做得平庸——漏洞漏报、风格误报、语义理解浅、可读性建议基本是套话。

后来我们把它拆成了四个 sub-agent，每个专注一个维度，让一个 supervisor 汇总。当时 AutoGen 0.2 刚出来，CrewAI 还没发布，我们用 LangChain 自己撸了一套蹩脚的 supervisor。效果从 0.58 拉到 0.73 左右，不算惊艳，但够说服团队继续往下做。

这一章讲的就是这种场景下你怎么思考 multi-agent，怎么选框架，怎么避免我当年踩过的那些坑。

## 为什么拆成多个 Agent

先说清楚一个常见的误解：multi-agent 不是为了让模型"更聪明"。你把 prompt 写得再好，single agent 在复杂任务上的天花板就是比 multi-agent 低，原因不是模型能力问题，是注意力分配问题。我跑过几百条样本做过对比，让一个 Agent 同时处理 code review + security audit，security 这块漏报率是单独跑 security agent 的 2.3 倍。不是模型不会，是 prompt 太长、上下文太杂，它分心了。

更重要的原因是责任分离。我做 code review 工具那会儿，最头疼的是 debug——用户报"这个 review 不准"，我得猜到底是哪个环节出的问题：理解错了？规则没匹配？还是输出格式坏了？拆成多 agent 之后，至少能定位到"是 security sub-agent 漏了"还是"是 supervisor 汇总错了"。可观测性这个价值，在 production 里被严重低估。

还有协作上的好处。有些任务天然就是流水线结构——规划→检索→写作→校对，你让一个 Agent 全干，它得自己维护中间状态，context 会越滚越大。拆开之后每个 sub-agent 只关心自己那段的输入输出，context 干净得多。我后来做 RAG-heavy 的研究类 agent，主线就是 Planner → Researcher → Writer → Critic，四个 agent 串起来，context window 利用率比单 agent 高出不少。

但不是所有任务都该拆。如果你的任务能在 3-5 步内完成、信息流是单向的、单 agent 完全 hold 得住，那拆 multi-agent 就是 over-engineering。我见过有人把"总结一篇文档"这种活拆成 5 个 agent，结果总延迟从 2 秒涨到 12 秒，准确率还降了——因为 agent 之间传话损耗太大了。

## 三种主流架构模式

聊 multi-agent 绕不开三种拓扑：supervisor（中心化）、peer-to-peer（去中心化）、hierarchical（分层）。我分别讲讲我们在什么场景用过、效果怎么样。

Supervisor 模式是 LLM 应用里最常见的，本质就是一个 manager agent 加几个 worker agent。Manager 负责任务分发、结果聚合，worker 各管一摊。我 2024 年做的那个 code review 工具就是这个结构：Supervisor 拿到 diff，调度四个 worker（semantic/security/style/readability），最后汇总输出。这种模式的优点是控制流清晰，日志好查，失败了好 retry；缺点是 supervisor 自己成了单点瓶颈——如果它调度错了，后面全错。我当时还专门写了个 fallback：supervisor 调度超过三轮还没收敛，直接 fallback 到 single agent 跑一遍。

P2P 模式就是 agent 之间平等，谁都可以跟谁聊。AutoGen 的 GroupChat 默认就是这种。听起来很美对吧？实际上我用了半年，结论是 P2P 适合"头脑风暴类"任务——比如让几个 agent 互相讨论一个设计方案、做 adversarial review——但不适合生产流水线。原因很简单：控制流不可预测，token 消耗爆炸，调试起来想死。我有个项目跑 P2P，单次任务平均消耗 45k tokens，同样的任务用 supervisor 只要 12k。

Hierarchical 是上面两种的混合——上面有个 high-level supervisor 拆任务，中间有 mid-level supervisor 协调几个 worker。Microsoft 的 Magentic-One、AutoGen 的 nested chat 都属于这种。这种架构适合特别复杂的任务，比如 SWE-bench 那类需要多步骤、多工具、跨领域的问题。我 2025 年初做过一个实验，用 hierarchical 跑 software engineering benchmark，比单 agent 提升了 14 个百分点，但 prompt 和 orchestration 逻辑写了快 2000 行。所以这条路是好，就是贵。

说白了，90% 的场景用 supervisor 就够了。先从这个开始，遇到瓶颈再考虑升级。

## 框架选型：我怎么从 AutoGen 跳到 LangGraph

讲工具之前先讲个背景。2024 年中我基本只用 AutoGen，因为它当时最成熟——群聊、human-in-the-loop、code execution 内建，社区也活跃。但 2024 年底我开始往 LangGraph 迁移，原因很具体：AutoGen 的 group chat 在 production 里太难控制了。

先说 AutoGen。它的核心抽象是 GroupChat，一个 manager 决定下一个发言的 agent。你可以用 `speaker_selection_method` 控制是轮询、随机还是 LLM-driven。这个抽象写 demo 特别爽——三行代码一个 multi-agent demo——但上 production 你会发现：怎么 trace？token 怎么算？某个 agent 出错了怎么 retry？这些问题 AutoGen 0.2 的回答都比较模糊。我当时为了加 observability 自己 wrap 了一层，相当痛苦。

CrewAI 是 2024 年 11 月火起来的，定位比 AutoGen 更"产品化"——角色、任务、流程都给你定义好了，写起来很像在填表格。我用过一版做内容生成流水线，体感是：开发速度快，但灵活度低。它把 agent 间通信抽象成 task delegation，你想做点 P2P 那种动态交互就比较费劲。如果你团队不熟 prompt engineering，CrewAI 上手确实快；但如果你是工程师想精细控制，建议直接 LangGraph。

LangGraph 严格说不是 multi-agent 框架，是"用图来编排 LLM 应用"的框架，但它的 state machine 抽象天然适合做 multi-agent。我 2025 年初把那个 code review 工具从 AutoGen 迁到 LangGraph，重写了大概 800 行 orchestration 代码。最大的好处是 graph 这种结构让控制流可视化、状态可检查、checkpoint 内建——比如 supervisor 调完 worker，我想从中间某个状态重新跑，直接 `graph.invoke(state, config={"configurable": {"thread_id": "..."}})` 就完了。AutoGen 要做这件事得自己写 state management。

给一个 LangGraph 的代码片段感受下，这是我那个 supervisor 模式的核心部分：

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator

class ReviewState(TypedDict):
    diff: str
    semantic_comments: list[str]
    security_comments: list[str]
    style_comments: list[str]
    readability_comments: list[str]
    final_report: str

def run_semantic(state): ...
def run_security(state): ...
def run_style(state): ...
def run_readability(state): ...
def aggregate(state):
    # supervisor 汇总
    state["final_report"] = synthesize(state)
    return state

workflow = StateGraph(ReviewState)
workflow.add_node("semantic", run_semantic)
workflow.add_node("security", run_security)
workflow.add_node("style", run_style)
workflow.add_node("readability", run_readability)
workflow.add_node("aggregate", aggregate)

workflow.set_entry_point("semantic")
workflow.add_edge("semantic", "security")
workflow.add_edge("security", "style")
workflow.add_edge("style", "readability")
workflow.add_edge("readability", "aggregate")
workflow.add_edge("aggregate", END)

app = workflow.compile()
```

这个看起来简单，但能跑、能 trace、能 checkpoint——这三个能力在 production 里值千金。

如果你的团队在 2024 年中前期上手 multi-agent，AutoGen 是合理起点；但如果你是 2025 年开始新项目，LangGraph 是更稳的选择。CrewAI 适合非工程师主导、内容生成类项目。Anthropic 的 Claude SDK 也有 multi-agent 的支持，但偏 research orientation，production ready 还差点意思。

## 通信协议：Agent 之间怎么"说话"

Multi-agent 一个被低估的工程问题是 communication protocol。就是 agent 之间传什么、怎么传。

最 naive 的做法是把整个 message history 传给下一个 agent。听起来合理，但 token 消耗会爆炸，而且噪声会累积。我做过测试，3 轮对话后历史已经 8k tokens，但真正有用的信息不到 1k。所以 structured message 是必须的——每个 agent 输出明确的 schema，下一个 agent 只接收它关心的字段。

我一般用 Pydantic 定义 input/output schema。比如 security worker 的 output 是 `{"findings": [{"severity": str, "location": str, "description": str}]}`，supervisor 只看 findings 这个字段。这样 token 消耗可控、信息流可追溯、debug 时能精准看到"是 security 漏了还是 supervisor 漏聚合了"。

更高阶的做法是引入 shared state + message passing，而不是 chain of full context。LangGraph 的 state graph 天然支持这个——所有 node 共享一个 state object，每个 node 读自己关心的字段、写自己要更新的字段。这种模式比 chain of messages 更接近 actor model，更可扩展。

还有一个我踩过的坑：tool calls 的传递。Agent A 用了一个 tool，结果怎么传给 Agent B？直接把 tool 的 raw output 传过去往往不行，因为格式不可控、可能包含敏感信息。我的做法是 tool result 必须经过 transform layer——结构化、脱敏、截断——再放进 state。我那个 code review 工具里专门写了个 `normalize_tool_output` 函数处理这个。

跨 agent 的 memory 共享也是个问题。如果多个 agent 需要访问同一份知识（比如 codebase），你不能让每个 agent 都自己 RAG 一遍——既慢又浪费。我的做法是 supervisor 先做一次 retrieval，结果放进 shared state，sub-agent 直接读。这个模式在 2025 年的 agentic RAG 系统里基本是标配了。

## 常见的坑和怎么避

讲几个我真实踩过的坑，希望能帮你省点时间。

第一个是 agent 之间循环调用。A 调 B，B 调 A，永远停不下来。AutoGen 的 group chat 我至少见过三次这种事故。LangGraph 好一点因为是 DAG，但你用 conditional edge 也可能写出环。一定要设 max iteration，超过就强制终止并报警。这个我吃过亏——一个任务跑了 4000 多轮才因为 rate limit 挂掉，账单看了想哭。

第二个是 supervisor 变成瓶颈。Supervisor 如果每次都要 LLM call 来决定下一步，延迟和成本都吃不消。我后来改成：能用 rule 决定的（"先做 X 再做 Y"）就用 static edge，只在真正需要动态决策的地方才 LLM call。这样 supervisor 的 LLM 调用次数能从 O(n) 降到 O(1) 或 O(log n)。

第三个是缺乏 evaluation。Multi-agent 系统比 single agent 难 eval 一个数量级，因为变量多了一整个 orchestration 层。我后来专门写了一个 evaluator：给同样的 input，分别跑 single agent 和 multi-agent，对比输出；对 multi-agent 内部，还要分别 eval 每个 sub-agent 的输出质量。这块的具体方法论我在下一章 [评测](./09-evaluation.md) 里会详细讲。

第四个是 state 管理混乱。Agent 一多，state 字段就爆炸——十几个 sub-agent 各写各的字段，最后谁改了什么谁都说不清。我的原则是：state 要 schema-enforced，每次 update 要可追溯，敏感字段要标记谁能读谁能写。LangGraph 的 reducer 机制可以帮上忙，但最终还是得靠 discipline。

第五个是 prompt 的版本管理。每个 sub-agent 有自己的 system prompt，supervisor 有自己的 orchestration prompt，加起来十几二十个 prompt 散在代码各处。改一个 prompt 不知道影响哪些路径。我后来把所有 prompt 抽到单独的 YAML 文件，按版本号管理，每次改动走 PR review。土但是管用。

## 跟其他章节的衔接

Multi-agent 不是孤岛，它跟 series 里其他几章强相关。

跟 [AI Evals 系列] 的衔接：multi-agent 系统的评测比 single agent 难得多，因为你要同时评估 final output 和 intermediate outputs。我在 Evals 系列里专门讲了 hierarchical evaluation 和 agent-level metrics，这套方法论直接可以用到 multi-agent 上。每个 sub-agent 都应该有自己独立的 eval set，supervisor 的调度策略也应该是 eval 的对象。

跟 [Context Engineering 系列] 的衔接：multi-agent 系统本质上是 context 管理的艺术。每个 sub-agent 看到的 context 应该最小化但充分，supervisor 的 context 应该是聚合视图而不是 raw 历史。这跟我们 context engineering 里讲的 "context budget" 和 "context pruning" 是一脉相承的。我那个 code review 工具后来优化的一大方向就是 context engineering——把无关的 agent history 裁掉、把 tool result 结构化、让每个 agent 只看到它该看到的。

跟 [Memory 系列] 的衔接：多 agent 之间的 memory 共享是 2025 年开始热起来的话题。如果几个 agent 协作完成一个长期任务（比如 multi-session research），它们需要共享 episodic memory 和 working memory，但又不能互相污染。这块我们组做过一些实验，初步结论是：shared memory 比 per-agent memory 在 long-horizon 任务上效果好 15-20%，但需要严格的 write authority 控制。

## 给工程师的两条建议

第一，从 supervisor 模式开始，不要直接上 P2P 或者 hierarchical。用 LangGraph 写一个最简单的 supervisor + 2-3 个 worker 的图，跑通你手头的任务，再考虑扩展。我见过太多团队一开始就设计特别复杂的 multi-agent 架构，结果 80% 的复杂度是在为不存在的需求买单。

第二，multi-agent 是手段不是目的。先用 single agent + 好 prompt 跑一个 baseline，如果遇到明显的 attention split 问题或者需要责任分离，再拆。不要为了"看起来高级"上 multi-agent——多一次 agent call 就是多一次延迟、多一次失败可能、多一次 token 消耗。除非这些成本换来的是显著的能力提升，否则不值得。

我们 2024 年到 2026 年这两年，看着 multi-agent 从一个研究概念变成 production 标配，又从 AutoGen 一家独大变成 LangGraph/CrewAI/各家百花齐放。工具会变，但底层问题没变：怎么让多个 LLM-powered agent 高效协作完成任务。理解了这一点，工具切换对你来说只是换个语法而已。

下一章我们聊 [评测：Agent 怎么打分](./09-evaluation.md)——这是 multi-agent 之后最让你头疼的问题，也是 production 化绕不过去的一关。