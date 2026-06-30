# 01. Agent 是什么: 从 LLM 到 Agent, 范式迁移

去年 11 月我第一次在生产环境跑 agent 的时候, 还觉得自己挺懂. 当时用 GPT-4 接了一个 ReAct loop, 给了一个计算器和搜索 API, 让它回答 "特斯拉上个季度卖了多少辆 Model Y". 我心想这不就是 prompt 加上 tool 吗, 一晚上搞定.

结果上线第二天, 用户问了一个 "把上个问题里那个数乘以 0.85", 它把上下文里的 "Model Y" 当成了数字, 直接返回了 "0.85". 不是因为模型笨, 是因为我们根本没设计 agent 该怎么维护 working memory. 那一刻我才意识到: LLM 到 agent 这条路, 中间隔着的不只是一个 loop, 是整套思维方式的迁移.

后来我们组为了填这个坑, 把市面上能找到的 agent 框架翻了一遍, AutoGen, LangGraph, CrewAI, 还有 MetaGPT, 一边读论文一边读源码. 零零散散花了大概三个月, 才把 "到底什么是 agent" 这件事想清楚. 这一章我尽量把那三个月的认知压缩给你看, 跳过我踩过的那些坑.

## 那个问题其实不是 LLM 的问题

先说清楚一件事: agent 不是一个新模型, 也不是 GPT-5 才有的魔法. 它是把已有的 LLM 当大脑, 外面套了一层循环结构, 让模型自己决定下一步该干什么. 这层结构 2022 年就有了, ReAct 那篇论文, Yao et al., ICLR 2023 收录的那篇, 把整个范式定了下来.

ReAct 之前是什么? 是 Chain-of-Thought, Wei et al., 2022 年 1 月发的那篇. CoT 解决的是 "让模型想一步再回答", 但它假设整个推理图是模型在生成前就想好的. 实际生产里你会发现, 模型想的路径经常是错的, 需要中途看反馈, 调路径. CoT 干不了这事, 因为它是一次性 forward pass.

ReAct 干的是这件事: 把 "思考" 和 "行动" 交替起来, 每一步行动后拿真实反馈再决定下一步. 论文里那个经典例子, HotPotQA 多跳问答, ReAct 比纯 CoT 在 Exact Match 上从大概 0.29 干到 0.35, 比纯 Act (只有行动没有思考) 也好. 但说实话, 这个数字在 2024 年看已经不算惊艳了. ReAct 真正的贡献不是这个 benchmark, 是它把 agent loop 的骨架画出来了.

我后来跟 Anthropic 的人聊, 他们说 Claude 内部做 agent 工具的时候基本就是这个骨架, 只是把 Thought 拆成了 system prompt + tool result + scratchpad 三段. 我们当时用 Python 写了个最简版, 大概 80 行:

```python
def react_loop(llm, tools, query, max_steps=8):
    history = [{"role": "user", "content": query}]
    for _ in range(max_steps):
        thought, action = llm.parse_action(history)
        if action.name == "FINISH":
            return action.answer
        obs = tools[action.name](**action.args)
        history += [
            {"role": "assistant", "content": thought},
            {"role": "tool", "content": obs}
        ]
    return llm.force_answer(history)
```

跑起来会发现, 这个 80 行的版本在简单任务上够用, 但 production 完全不行. 因为它没有错误恢复, 没有状态压缩, 没有 cost control. 但作为理解 agent 是什么的最小可执行单元, 够了.

## Function calling: 从 ReAct 到 tool use 的转折

ReAct 论文里的 action 是模型自己生成一段文本, 然后正则表达式或者 LLM 自己 parse 出 "调用什么工具". 这种方式 2023 年上半年大家都在用, 包括我. 痛点是 parse 失败率大概 5-15%, 你写得再 robust 的正则也有边界 case, 模型输出格式漂移太正常了.

转折点是 2023 年 6 月, OpenAI 在 gpt-4-0613 和 gpt-3.5-turbo-0613 上线了 function calling. 模型直接输出结构化的 JSON arguments, 不再需要 parse 文本. 这件事听起来小, 实际意义很大: 它把 "工具调用" 从一个 hack 变成了模型的第一公民能力.

我印象很深的是, 6 月 21 号那天晚上, 我把一个线上 agent 从 text parsing 切到 function calling, parse 失败率从 11% 直接掉到 0.3% 以下. 不是模型变聪明了, 是接口契约变了. 整个社区在这个时间点分了一波叉: 还在用 ReAct text parsing 的是老派, 切到 function calling 的开始造新框架. LangChain 的 agent 模块大概在 7 月就重构了, 全面转向 tool calling.

Anthropic 在 2024 年上半年跟进了 tool use, 格式略有不同 (他们的 tool_use / tool_result block 结构). Google Gemini 同期也上了类似能力. 到 2024 年中, 三大厂基本统一了: tool calling 是 agent 的标准接口. 这件事的 trade-off 是, 你被 vendor 锁定了 schema, 但换来的稳定性远超自由 parse.

有意思的是, 2024 年下半年开始出现的 MCP (Model Context Protocol), Anthropic 11 月份推的那个, 想把这个标准再往上抽一层. 从 "单次 function call" 变成 "标准化的 tool server 协议". 我对 MCP 的判断是: 方向对, 但早期. 我们组试过自己跑 MCP server, 生态还不成熟, 很多 tool 还在用直接 function call 接入. MCP 真正起飞估计要 2025 年下半年甚至更晚.

## 范式迁移到底移了什么

我在跟新人讲 agent 的时候, 喜欢画一张图: LLM 时代你写的是 prompt, 调的是 temperature 和 max_tokens, 关心的是 single-turn quality. Agent 时代你写的是 loop, 调的是 max_steps 和 retry policy, 关心的是 task completion rate over multi-turn.

说白了, 范式从 "我给模型一个输入, 等一个输出" 变成 "我给模型一个目标, 看着它跑完". 这个迁移听起来抽象, 落到工程上是几个具体的变化.

第一, prompt 不再是单一资产. 在 agent 系统里, 你有 system prompt, 有每一步的 user message, 有 tool description, 有 observation format. 这几样东西互相耦合, 改一个常常会动另一个. 我去年有个教训, 为了优化一个工具的描述改了几个字, 结果整个 agent 的成功率从 0.78 掉到 0.65. 后来排查了两天才发现, 是某个 tool description 里的示例触发了模型对其他 tool 的偏见.

第二, eval 范式变了. LLM 时代你 eval 的是单轮回答质量, 用 BLEU, 用人类偏好, 用 GPT-4 打分. Agent 时代你要 eval 的是 trajectory, 是 "模型走完一个任务到底用了多少步, 哪一步错了, 错了之后能不能恢复". 这个东西项目里 AI Evals 系列会专门讲, 我只说一句: 没想清楚怎么 eval trajectory 之前, 别上 agent. 我们当时吃过亏, 灰度上线一周才补 eval, 中间有几条样本肉眼能看出来是错的, 但 metric 上没反映.

第三, 成本结构变了. 单轮 LLM 调用你大概能预算 cost, prompt 多少 token, 输出多少 token, 一乘就出来. Agent 一次任务可能跑 3-15 步, 每步都有 prompt 和 output, 还可能重试, 还可能循环 (你信不信, 早期版本我们 agent 在某条样本上跑了 47 步还没停, 是因为它反复调用 search 查同一个关键词). 成本不是线性增长, 是指数级失控的风险. 必须有 hard cap, 必须有 step-level timeout.

第四, 也是最关键的: 调试范式变了. LLM 时代 debug 看 prompt 和 response 就够了. Agent 时代你要 trace 一整条 trajectory, 每一步的 thought, action, observation, 都要落库. 不然线上出问题你根本没法复现. 我们现在每个 production agent 都接 LangSmith 或者自建的 trace 系统, 不接不开. 这一条是血的教训.

## 真实项目的几个分水岭

讲几个 2024-2026 我亲眼见过的分水岭, 帮大家感受一下进化速度.

第一个分水岭是 2024 年 5-6 月, GPT-4o 出来那阵. 我们当时把一个客服 agent 从 GPT-4 切到 GPT-4o, latency 从平均 4.2 秒降到 1.8 秒, 成本大概降了 40%. 同一时间 Anthropic 的 Claude 3.5 Sonnet 上来, 在代码相关的 agent 任务上比 GPT-4o 强一截. 那个月我们做了 A/B test, 最后选 Claude 3.5 Sonnet 跑主力 agent, GPT-4o 跑 fallback. 这种 multi-model routing 在 2024 年中开始普及.

第二个分水岭是 2024 年 9-10 月, OpenAI o1-preview 发布. 推理模型第一次以 API 形式给到大家. 这东西对 agent 的影响很微妙: 在需要深度规划的 task (比如数学, 比如复杂代码) 上 o1 比 GPT-4o 强很多, 但 latency 高, 成本高, 而且它不接 function calling 早期版本. 我们当时没用 o1 跑主 agent, 而是用它做 "planner" 先把任务拆解, 然后 GPT-4o 做 "executor". 这种 planner-executor 分离的架构在 2024 年底开始流行, 后来 LangGraph 的 multi-agent 模式基本就是这个思路.

第三个分水岭是 2025 年初, Anthropic 的 Claude 3.7 Sonnet 和后续的 Claude 4 系列. Sonnet 3.7 引入了 extended thinking, 模型自己有一个内省的思考过程. 这件事对 agent 来说意义比想象的大, 因为很多之前需要外层 loop 引导的 reflection, 模型自己就能做了. 我们当时有个 agent 在 long-horizon planning 上一直不行, 切到 extended thinking 后直接能跑通. 但 extended thinking 的 trace 要单独存, 不然你看不到它内部在想什么, debug 又是问题.

第四个分水岭是 2025 年中的 multi-agent 浪潮. AutoGen 0.4, LangGraph 1.0, CrewAI 0.80+, 这几个框架在 2025 年中前后来了一次大重构, 核心都往 production-grade 走. 我特别想说 LangGraph, 它把 agent 抽象成 graph 而不是 chain, 这个抽象在 2024 年还不明显, 2025 年看简直是对的方向. multi-agent 这件事项目里 multi-agent in practice 系列会详细讲, 这里只说一句: 别为了 multi-agent 而 multi-agent, 80% 的场景 single-agent + 好工具就够了.

## 工具调用起源: 不只是 function call

工具调用这件事的起源比大多数人以为的要早. ReAct 是 2022 年底, 但真正的雏形可以追到 2021 年的 WebGPT, OpenAI 自己做的一个让 GPT-3 浏览网页的项目. 那时候还没有结构化 tool call, 模型输出的是带特殊标记的 "search" 指令, 后端正则匹配执行.

2022 年还有个重要工作, Toolformer, Meta 的那篇. 它是第一个用 self-supervision 训练模型学会调用 API 的论文, 思路是让模型自己标注哪些位置插入 API 调用会提升 perplexity. 效果有但落地难, 因为训练成本太高. 但 Toolformer 把 "tool use 是模型的能力而不只是 prompt 技巧" 这个观念立住了.

真正工程化是 2023 年 ReAct + function calling 的组合, 到 2023 年底基本定型. 2024 年开始大家关注的不再是 "能不能调用工具", 而是 "怎么高效管理工具生态". 一个真实问题: 一个生产 agent 可能要接 20-50 个 tool, 怎么让模型选对? OpenAI 的方案是 fine-tune 一个 retriever 选 tool, Anthropic 的方案是让模型自己看 description 选, LangChain 早期有 vector store 选 tool 但效果不稳定.

我们当时做了个内部 benchmark, 30 个 tool 的场景下, 让模型自己看 description 选, 准确率大概 82%. 加 retriever 能到 88%, 但 latency 多 200ms. 最后我们选了不加重 retriever, 但把 tool description 写得极其具体, 每条不超过 80 字, 带明确的 input/output 示例. 这个工程 trick 在 2024 年中总结过, 后来发现 Anthropic 内部做法也类似.

## 几个常被搞混的概念

最后澄清几个概念, 不然后面章节会有歧义.

Agent vs Workflow. 这两个经常被混用. 我自己的定义: workflow 是你预设好步骤, 模型在每步填空; agent 是模型自己决定步骤. LangGraph 的创始人 Harrison Chase 有一篇博客讲这个区别, 我觉得他定义得比我清楚. 实操上, 如果你的任务步骤你能用流程图画出来, 用 workflow, 别用 agent. agent 的价值在于 "我不知道它会走哪条路径但它能走到终点". 这件事项目里后面会专门拆.

Agent vs Copilot. Copilot 是 IDE 里那个, 它是辅助人, 决策权在人. Agent 是自主跑, 决策权在模型. 这两个在产品形态上完全不同, 但底层技术栈很多是共享的. 别被产品名骗了, 看决策权在哪.

Agent vs RAG. RAG 是给模型外挂知识, agent 是给模型外挂动作. 一个 agent 系统里几乎一定有 RAG 组件, 但 RAG 不需要 agent. Context-engineering 系列会讲 RAG 的各种花样, 这里只强调: 别把 "模型能查文档" 当成 agent, 那只是 RAG.

Single-agent vs Multi-agent. 这个不多说, 项目里有专门系列. 一句话原则: 能用 single-agent 解决就别上 multi-agent, multi-agent 引入的协调成本和调试复杂度是 single-agent 的 3-5 倍.

## 给工程师的两条 actionable 建议

第一, 在你决定做 agent 之前, 先把 eval 框架搭起来. 我看过太多团队 agent 写完才发现不知道效果怎么样. 哪怕是 50 条手工标注的样本, 也比没有强. 早期 eval 不用 fancy, 能跑通 trajectory 记录 + 人工打分就行. AI Evals 系列会展开, 但起点是: 没 eval, 不上 agent.

第二, 第一版 agent 用最简的 ReAct + function calling 实现, 别一上来就 LangGraph 或 AutoGen. 我知道框架能让你快, 但框架也藏了很多行为, 出问题你不知道是 prompt 的问题还是框架的问题. 我们组新人入职第一周都是手写 ReAct loop, 第二周才让碰框架. 这个训练出来的工程师对 agent 的理解深度, 比直接用框架的高一截.

如果你是第一次接触 agent, 先去看 ReAct 那篇论文, 再去看 OpenAI function calling 的官方文档 (不长, 一小时能读完), 然后照着本文那个 80 行 Python 写一遍. 跑通了, 你对 agent 的理解就超过了 80% 的教程读者. 跑不通, 带着问题来翻下一章, 我们聊 LLM 本身.

---

下一章我们拆 LLM 基础: [LLM 基础: Agent 的大脑怎么造](./02-llm-foundation.md), 从 transformer 到 instruction tuning 到 RLHF, 把 agent 大脑那一层铺开.