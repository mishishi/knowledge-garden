# 06. Planning: Agent 怎么想

我第一次意识到"planning"是 agent 工程里最被高估的词,是 2024 年 3 月。那时候我们组在做内部一个 code agent,想让它自动帮人改 PR。看着论文里 ReAct 循环写得那么漂亮——Thought、Action、Observation 一圈一圈转——我就照着抄了一份。

结果第一个真实任务就崩了。任务是:"在 repo 里找到所有用了 deprecated API 的地方,换成新 API,跑测试,提交 PR。"

ReAct 让它一步一步来:先 grep、读文件、再 grep、再读。它确实能找到问题,但中间会反复纠结"我是不是漏了一个文件?""要不要先看看 git log?"——这些人类根本不会想的元问题。等它终于列出 14 个文件要改,token 已经烧掉 18 万了,改到第 6 个文件它开始 hallucinate API 名字。

后来我们改成 Plan-and-Execute,先让 LLM 把整个 14 步计划吐出来,再一步步执行。看起来很笨,但 token 降了一半,而且因为计划是显式的,中间任何一步失败我们都能在 UI 上高亮告诉用户"卡在这了,要人接一下"。

这是我想在前面讲清楚的:这一章不是讲哪个 planning 算法在论文 benchmark 上数字高。**是讲你在 production 里到底该用哪种,以及什么时候该放弃 planning 这个想法。**

## 2024 到 2026:我们对"思考"这件事的理解变化

先把时间线拉一下,这样后面讲 ReAct、Plan-and-Execute、Reflexion 这些东西的时候,你能知道它是什么时候、为什么冒出来的。

2022 年底 ChatGPT 出来,大家开始用 prompt 玩 agent。2023 年 6 月 ReAct 论文(Yao et al.)出来,基本确立了"think-then-act"的范式。那时候大家以为,只要让模型在每一步前先"想一下",它就能自己规划。**这是一个非常天真的假设。** 现实里模型"想"出来的东西,经常是把当前问题分解成 N 个子问题,然后第一个子问题就开始 hallucinate。

到 2024 年初,我们做生产系统的工程师开始发现,ReAct 在简单任务上还行(3-5 步能搞定的),一旦任务链条超过 10 步,模型就开始"短路"——它会跳过某些步骤,或者把多个步骤混在一起,或者干脆假装自己做了。Plan-and-Execute 就是这个背景下被广泛采用的:先让模型一次性把计划吐出来,后面就只做执行。

再往后,2024 年中,Reflexion 和 Self-Refine 这类"反思"机制被炒得很热。逻辑也很直观:让 agent 做完一步之后回头看看自己做得对不对,不对就重做。但实际跑下来,反思本身是个 LLM call,每次反思又烧 token,而且反思经常是"我觉得我做得不错"——模型对自己的错误天然不敏感。

2024 年底到 2025 年,情况开始变。o1/o3 这种 reasoning model 出来,planning 的范式其实在变。我自己的体感是:在 reasoning model 面前,显式地让模型"先列计划"反而是冗余的——它内部已经做了 planning,你让它再显式做一次,既浪费 token,又可能让它的最终输出和它的内部推理不一致。

但 reasoning model 不是万能的。它对"长链条、强依赖"的任务还是容易断。2025 年 Anthropic 提的"skills"概念、DeepMind 的 AlphaProof 那种系统,本质还是回到了"先把 plan 落成可验证的中间表示"这条路。

到了 2026 年初,我们做 agent 的工程师基本达成了几个共识,我先把它列出来,后面再展开:

- **简单的循环已经够用,显式 plan 是个 cost/benefit 决策**
- **ReAct 在工具调用稳定、步骤短的时候依然是最干净的方案**
- **Plan-and-Execute 适合"用户能容忍等待"且"任务可被静态分解"的场景**
- **反思机制是奢侈品,不是必需品**
- **Reasoning model 改变了 planning 的"形状"——从"显式 plan"变成"隐式 plan + 可验证 step"**

我下面会挨个说。

## ReAct 和它的"轻"用法

ReAct 那个模板我估计大家都见过:

```
Thought: 用户让我找 deprecated API。我应该先 grep。
Action: bash
Action Input: grep -r "old_api_name" src/
Observation: src/a.py:3: old_api_name(...)
Thought: 找到第一个文件,继续找。
Action: bash
Action Input: grep -r "old_api_name" src/ -l
...
```

理论上,模型在每一步前先想"我现在该干嘛",然后执行,再观察结果,再想。这种结构的好处是**它把模型的"思维"和"动作"解耦了**,所以观测到错的时候,模型能重新规划。

但 ReAct 真正在生产里能用,不是因为论文里的理论漂亮。**是因为 OpenAI function calling、Anthropic tool use 这些基础设施,把它变成了一个稳定的"协议"。** 模型不用自己拼字符串调用工具,工具调用是结构化的,参数有 schema 校验,错误能被 catch 住。

我后来做轻量 agent(比如"读一个 PDF 提三个问题"、"给一个 URL 写个摘要"这种 1-3 步就能搞定的),默认就是 ReAct 风格。代码大概长这样(简化版):

```python
def react_loop(task, tools, max_steps=8):
    history = [f"Task: {task}"]
    for step in range(max_steps):
        response = llm_call(
            system=REACT_PROMPT,
            tools=tools,
            messages=history
        )
        if response.has_tool_call:
            result = execute_tool(response.tool_call)
            history.append(f"Observation: {result}")
        else:
            return response.final_answer
    return "Failed: max steps exceeded"
```

这个模式 2024 年我们用得最多。**它的精髓是"够轻"**——没有"先规划"的预热阶段,没有"反思"的额外 call。就是 think-act-observe,跑完拉倒。

但 2025 年开始,我在很多场景下把 ReAct 的显式 "Thought:" 字段去掉了。原因很简单:reasoning model 自带 think,显式让它再 think 一次,反而干扰它的内部推理链。如果你用 o1/o3/o4-mini 这种,**直接让它 function call,让它自己决定要不要先"想"**,效果更好。ReAct 这个 prompt 模板更适合 Sonnet、Haiku、GPT-4o 这种"非 reasoning"的模型。

另外一个 2025 年才注意到的点:**ReAct 的"Observation" 字段容易被滥用。** 我见过很多 agent 框架,把每一步的工具输出原封不动塞进 history。一次工具调用返回 5 万 token,下次 LLM 看的 context 直接爆炸。所以我们后来在生产里强制加了一个 `truncate_observation` 的中间层,任何 observation 超过 3000 token 就要被压缩。这个数字是我拍脑袋试出来的——太短会丢关键信息,太长就 context 爆炸,3000 是个还不错的起点。

## Plan-and-Execute:让用户先看到方向

如果你的任务用户能等 30 秒以上、且能容忍"先告诉我你要干嘛,再开干"这种节奏,Plan-and-Execute 通常比 ReAct 好。

核心思路是分两个阶段:

1. **Planner**: 拿到用户任务,吐出一份完整的步骤计划
2. **Executor**: 拿到计划,一步步执行,每步只关注"我现在该做哪一步"

好处是什么?三个:

- **用户能 early reject**。模型刚吐完计划,用户一看"这不对,我要的不是这个",直接 cancel,不用等它跑完才发现跑偏。
- **token 效率高**。Planner 一次性把计划吐完,后面 executor 不用每次重新想"接下来干嘛"。
- **debug 容易**。计划是显式的,某一步失败你能精确定位。

我 2024 年那个 code agent 改完之后,大概长这样:

```python
def plan_and_execute(task):
    plan = planner_llm(
        f"任务: {task}\n"
        f"请输出一个分步骤计划,每步包含: 1) 目标 2) 用什么工具 3) 预期输出"
    )
    # plan = [
    #   {"step": 1, "goal": "找 deprecated API",
    #    "tool": "grep", "expected": "文件列表"},
    #   ...
    # ]
    
    if not user_approves(plan):  # UI 上让用户确认
        return "cancelled"
    
    results = []
    for i, step in enumerate(plan):
        step_result = executor_llm(
            task=task,
            plan=plan[:i+1],
            previous_results=results,
            current_step=step
        )
        results.append(step_result)
        if step_result.failed:
            return replan(task, plan, results)  # 失败重规划
    return synthesize(results)
```

注意 `replan` 那一步——**Plan-and-Execute 不是"计划完就一往无前",失败要能重规划**。这是 2024 年我见很多新手踩的坑:计划写得很漂亮,但中间一步崩了就整个 task 失败,没有任何 recovery。

我自己的经验是:replan 这个能力,加进去之后,任务的 end-to-end 成功率大概能从 70% 提到 85-90%。这个数字我没法给你严谨的 ablation,但我们在两个内部 agent 上都观察到类似的提升。

Plan-and-Execute 不适合什么?**任务高度动态、计划在执行前根本定不下来的场景。** 比如"用户给一个数据库,让它自己探索 schema,找到最有趣的 pattern"——这种东西 plan 出来也是瞎猜,反而浪费 token。这种场景用 ReAct 那种"边走边看"的模式更合适。

## 反思、ToT 和那些"看起来很美"的方案

我必须老实讲:**Reflexion、Self-Refine、Tree of Thoughts 这些"反思/搜索"机制,在生产 agent 里的实际使用率,远低于论文热度。**

原因有几个:

**第一,反思要烧双倍 token。** 模型做完一步,再调一次 LLM 评估"做得对不对",再调一次根据反馈修改。三个 call 干一件事,token 成本直接 *3。我们组 2024 年中做过一个实验,一个 10 步的 agent 任务,加 Reflexion 之后成功率从 78% 升到 84%,但 token 涨了 2.3 倍。老板看了一眼账单说:"别用。"

**第二,反思经常是无效反思。** LLM 对自己刚生成的输出天然不敏感——它倾向于说"看起来不错"。我在 Anthropic 的 prompt 库里翻到一份关于 self-critique 的指南,里面直接讲:"LLM 经常无法识别自己输出中的错误,简单的 'check your work' prompt 效果有限。"这是业界的共识。

**第三,反思和 reason model 是冲突的。** 你让 o1 反思一下,它会"重新想一遍",但它内部已经在第一次 think 时考虑过同样的东西。重复 think 浪费算力,产出也不一定更好。

**那反思什么时候有用?** 我自己的经验是:在**有外部 verifier** 的场景下特别有用。比如代码任务有"能不能跑测试"这个 verifier,数学任务有"答案对不对"这个 verifier。这种场景下,反思不再是"LLM 评估 LLM",而是"LLM 看着 verifier 的反馈改"。这种 reflection 成功率就高很多。

Tree of Thoughts(ToT)那个"展开多棵树,挑最好的"的设计,听起来很 elegant,但**它的 token 消耗是指数级的**。深度 4、宽度 3,就是 3^4 = 81 个分支,每次 LLM call 还要打分。学术界 benchmark 跑得飞起,production 没人用得起。2024 年我们试过用 ToT 做一个 strategy 决策模块,3 个分支就 1500 美元/天的账单,直接砍掉。

HuggingGPT(也叫 JARVIS)是另一种思路——**让 LLM 当调度器,把任务分解成多个 expert model 协作**。这个思路在 2023 年很火,但 2024 年 GPT-4V、Gemini 这种多模态原生模型出来后,HuggingGPT 的"调度-分发"优势就没了。**它的历史价值更多是证明了"LLM 能做 planning"这件事,而不是它本身是一个好方案。**

## Reasoning model 怎么改变了 planning 的形状

这是我 2025 年最强烈的一个体感变化,我得单独讲讲。

o1 出来之前,主流的 planning 思路都是"显式 plan":你必须让模型在 prompt 里"先想清楚再动手",要么通过 ReAct 的 Thought 字段,要么通过 Plan-and-Execute 的显式计划文档。

o1 出来之后,**模型自带了 thinking**,而且这个 thinking 是 hidden 的——你看不到它内部在想啥,只能看到最终输出。这就带来了一个尴尬的问题:你还该不该在 prompt 里让模型"先想一下"?

我的经验是:**不该。** 让 o1/o3 显式想,相当于让它"先把自己的 think 翻译成自然语言,然后再 think 一次"。这既浪费 token,又可能让最终输出和内部推理脱节(因为显式 think 的时候,模型可能没把全部内部推理都说出来,导致后续步骤基于不完整的"显式 think"在做决策)。

2025 年我们组的 production agent 90% 以上跑在 reasoning model 上,**显式 planning 的代码基本被删掉了**。取而代之的是:

1. **把任务描述写清楚,告诉模型"我要的是什么"**(相当于传统 plan 的"目标"部分)
2. **用 tool use 让模型在执行层面有抓手**(对应传统 plan 的"步骤")
3. **用 verifier 在执行后检查**(对应传统 plan 的"验收")
4. **对长任务,把它拆成多个 sub-task,每个 sub-task 独立 reasoning**(代替传统 plan 的"分步执行")

最后一条特别重要。**Reasoning model 在 5-7 步以内的 chain 上表现最好,超过 10 步就开始不稳定。** 所以我们后来做长任务的标准做法就是:外层用一个 orchestrator 把任务拆成 5-7 步的子任务,每个子任务独立 reasoning + 执行。这其实是一种"hierarchical planning"——但和 Plan-and-Execute 不同,plan 不是 LLM 吐出来的,而是 orchestrator 通过反复试错学习出来的(或者直接 hardcode)。

举个例子,我们的 code agent 在 2025 年下半年是这么组织的:

```python
# 顶层 orchestrator(可以是 hardcoded 的 workflow,也可以是另一个 LLM)
subtasks = [
    "explore_repo",       # 探索 repo 结构
    "identify_changes",   # 找到要改的地方
    "make_edits",         # 改代码
    "run_tests",          # 跑测试
    "fix_failures",       # 修测试失败
    "commit_and_pr"       # 提交 PR
]

for sub in subtasks:
    result = reasoning_agent(sub, context)  # 每次都是独立 reasoning
    if result.failed_permanently:
        escalate_to_human(result)
    context.update(result)
```

**外层是流程,内层是 reasoning。** 这是 2025 年我看到的、最稳的 agent 架构。

## 那到底怎么选

讲完这么多,给几个 actionable 的判断标准(不是 checklist,是我自己在脑子里跑的决策树):

**任务步骤 < 5、且步骤动态不确定** → ReAct 风格,不要 planner。代码简单、token 省、对 reasoning model 友好。

**任务步骤 > 5、用户能等 30 秒+、任务可静态分解** → Plan-and-Execute + replan。给用户 early visibility,失败有 recovery。

**任务步骤 > 5、但每步有明确的 verifier(测试、断言、reward)** → 用 reason model + 反复试错,不要显式 plan。直接把任务给模型,告诉它"做到了再停"。

**任务需要多个 expert/domain 协作** → 不要自己造 LLM 调度器了,要么用现成的 multi-agent 框架(下一章会讲),要么直接 hardcode 一个 workflow。LLM 调度器在 2025 年已经被证明不稳。

**任务很复杂、但你能把它拆成 5-7 步的子任务** → Hierarchical planning(orchestrator 拆任务,子 agent 做 reasoning)。这是 2025 年我最推荐的模式。

**最后一条忠告:** 如果你的任务用一句"先 X 再 Y 再 Z"就能说清楚,**那根本不需要 planning 模块,直接写死 workflow 就行。** 别为了"显得像 agent"硬塞一个 LLM planner。我 2024 年见过太多"LLM 调一个 LLM 调一个 LLM"的架构,跑起来比 if-else 还慢。

---

后面聊 memory、tool use、RAG 的时候,你会发现 planning 这个话题会反复回来——RAG 要不要先 plan 再 retrieve,tool use 要不要先 plan 再调用,memory 要不要先 plan 再回忆。说白了,**planning 是 agent 思考的"形状",其他模块都是它在不同维度的延伸。** 下一章讲 RAG,本质上就是"agent 怎么用外部知识"——它和 planning 的关系,会和这一章讲的 ReAct 紧密耦合。

继续往前:[RAG: Agent 的外脑](./07-rag.md)