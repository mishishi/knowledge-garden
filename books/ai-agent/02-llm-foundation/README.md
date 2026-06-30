# LLM 基础: Agent 的大脑怎么造

2023 年初我们组第一次把 GPT-4 接进内部系统的时候,我盯着 trace 日志看了快一个小时。当时最困惑的不是它答错了——答错很正常——而是它有时候会"装懂"。你问它一个它大概率不知道的内部 API,它不会说"我不知道",而是会编一个看起来非常合理但完全错误的函数签名。我当时在群里发了一句"这玩意儿是个特别自信的实习生",然后开始琢磨:我们到底要拿什么样的模型,才能让它当 Agent 的脑子?

这一章想聊的就是这件事。但我不想从 Attention is All You Need 开始讲,也不打算把 BERT 跟 GPT 的区别掰开揉碎。我想从一个 Agent 工程师的视角,聊聊我对 LLM 的理解:它到底有什么能力、缺什么能力、这些能力是怎么被一步步训练出来的、以及我们做 Agent 的时候应该关心哪些东西。我假设你已经知道怎么调 API,知道什么是 next-token prediction,也知道模型是有上下文窗口的——这些我们不废话。

## 一、Transformer 跟 Agent 没什么关系,但 attention 跟 Agent 关系很大

老实讲,Transformer 的 encoder-decoder 结构、位置编码、layer normalization 这些,对做 Agent 的工程师来说基本是黑盒。你不需要懂,你只需要知道一件事:这个架构让模型可以并行训练、可以 scale 到很大参数、可以在巨量文本上学到语言本身的结构。这就够了。

但 attention 这个机制,跟 Agent 工程关系很大。我第一次意识到这点,是在我们做一个长文档问答系统的时候。当时 prompt 是这样的:

```
请基于以下文档回答用户问题。

文档:
{{document}}

用户问题: {{question}}
```

模型回答得还行,但一旦文档超过 30k token,质量就掉得厉害。后来我们试了 LongLoRA、试了 sliding window attention、试了各种 RAG 方案,最后落地的是一套混合策略:先 retrieve top-k 段落,再让模型自己判断要不要回查。但我发现一个反直觉的事情——模型的"找重点"能力,跟它的 attention 训练方式直接相关。同样是 7B 模型,有些模型在长 context 里就是能找到关键信息,有些就是会"迷路"。

具体怎么迷路呢?举个例子。我给一个模型一段 50k token 的代码日志,让它找某个特定时间点的错误信息。有些模型会真的去扫那段日志,有些模型会直接"幻觉"出一个看起来合理的错误——因为它在前文看到太多错误模式了,它觉得"这里应该有个错误"。

这背后的原因,我后来跟一个做模型训练的朋友聊过,他说白了就是 attention head 学到的模式不一样。模型在预训练的时候,如果长距离依赖的模式不够多,某些 attention head 就学不会"翻到很远的地方找具体信息"这个能力。所以现在我们选模型,长 context 任务我会先看几个东西:模型在 needle-in-haystack 上的表现、在 LongBench 上的分数、还有它在 RULER 这种综合评测上的数字。光看 context window 是 128k 还是 200k,意义不大——窗口能开不代表能开得好。

另外一个跟 attention 直接相关的 Agent 能力,我得单独拎出来说——**in-context learning**。我第一次看到这个能力的时候,是 2020 年 GPT-3 出来那会儿。当时论文里那个 "translate to French: cheese → " 的例子,直接把我看傻了。你不用改模型任何参数,就在 prompt 里给几个例子,模型就能学会新任务。这个能力,是后面整个 prompt engineering、agent、tool use 的基础。没有 in-context learning,你今天看到的几乎所有 Agent 玩法都得重写。

我后来自己做过一组小实验:同一个 7B 模型,同样的 task,zero-shot 准确率 0.42,给 5 个 in-context example 之后到 0.71,给 20 个到 0.78,给 100 个还是 0.78 左右。这个数字我记了很久,因为它告诉我们:example 不是越多越好,5-20 个通常就够了,而且 example 的质量比数量重要。这个观察直接影响了我们后来写 Agent prompt 的方式——我们更愿意花时间挑 10 个高质量、覆盖典型 edge case 的 example,而不是堆 50 个。

## 二、Instruction Tuning:让模型从"接话"变成"听话"

预训练完的 base model,本质是个接话机器。你给它 "The weather today is",它会接 "sunny and warm",或者接 "going to be cloudy in the afternoon"。它不一定会接 "I don't have access to real-time weather data"。这个差别对 Agent 来说至关重要——你需要一个能听懂"指令"的模型,不是一个只会续写的模型。

Instruction Tuning 这个事,我在 2022 年第一次感受到它的威力。当时 LLaMA 的 base 模型放出来,我跑了一下,问它 "Write a function to reverse a string in Python",它接的是 ":\n\n```python\ndef reverse_string(s):\n    return s[::-1]\n```\n\nThis function uses Python's slice syntax to reverse the string..."——你别说,它还真把代码续出来了。但你换个问法,"Can you write a function to reverse a string?",它有时候会续出来 "in Java?",有时候会续出来 "in C++?",完全不在同一个轨道上。

后来 Alpaca 出来了,用 52k 条 self-instruct 数据微调了一遍,行为立刻就规整了。你问它任何问题,它都会尽力给出一个像样的回答,而不是接着你的问题往别的方向聊。当时我们组用 Alpaca 做了第一个 demo——一个简单的 SQL 生成工具,用户用自然语言描述需求,模型输出 SQL。准确率不算高,大概 60% 出头,但已经能跑了。这是 instruction tuning 给我们最直接的体感:**base model 是个话痨,instruction-tuned model 是个能交活的员工**。

但 instruction tuning 真正让我震撼的,不是它让模型听话了,而是它让模型**学会了任务的格式**。这个区别很重要。

举个例子。我后来在做一个客户工单分类的 Agent,prompt 是:

```
Classify the following support ticket into one of these categories:
- billing
- technical_issue  
- account_access
- feature_request
- other

Ticket: {{ticket_text}}

Category:
```

如果用 base model,它在 "Category:" 后面大概率会接一堆废话。但如果用 instruction-tuned 模型,它会规规矩矩只输出一个单词。我当时跑了一组对照实验,base model 的格式正确率只有 34%,instruction-tuned 之后是 96%。这个数字差是致命的——对 Agent 来说,下游代码是写死的,模型必须按格式输出,不然整个 pipeline 就崩了。

数据这块,我得讲几个我们踩过的坑。第一,instruction data 的多样性比数量重要。我们一开始图省事,用 GPT-4 把一堆 prompt 改写了一下生成 instruction data,效果其实一般,因为这些数据都太"规整"了。后来我们加了一部分真实用户 query(脱敏后),效果立刻好了。第二,instruction tuning 会让模型"遗忘"一些能力,这个叫 catastrophic forgetting。我们最早用全参数微调一个小模型,结果它在我们的分类任务上从 0.78 涨到 0.85,但在通用对话能力上掉了一大截。后来我们换成 LoRA,问题缓解了很多,但还是有。后来我们干脆就只用大模型 API,自己不做 instruction tuning 了——性价比太低,除非你的场景足够垂直、足够大。

如果你想自己跑一遍 instruction tuning,我推荐从这几个项目开始:dolly-15k(最早的开源 instruction dataset 之一)、OpenAssistant Conversations、还有 UltraChat。代码的话,trl 库的 SFTTrainer 是目前最方便的选择,几行就能跑起来:

```python
from trl import SFTTrainer
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-3.1-8B")
tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-3.1-8B")

trainer = SFTTrainer(
    model=model,
    train_dataset=dataset,  # 你的 instruction dataset
    tokenizer=tokenizer,
    max_seq_length=2048,
)
trainer.train()
```

但说实话,2024 年之后,我自己的大部分项目都不再自己 instruction-tune 了。闭源 API 模型的能力已经足够强,自研小模型只有在数据安全要求极高或者 latency 要求极低的场景下才划算。这是后话,后面章节选型的时候我会再展开。

## 三、RLHF 跟 DPO:让模型从"能交活"到"交得让人满意"

Instruction tuning 让模型能听懂指令、按格式输出,但它还有个问题——它的目标函数是"模仿人类写的答案",所以它学会的是"像人",不是"对人有用"。我第一次意识到这个区别,是在 2023 年做一个代码 review Agent 的时候。

当时 instruction-tuned 模型给的 review,格式漂亮,语气客气,但经常说不到点子上。它会说 "Consider adding more comments to improve readability",但不会说"这个函数有 race condition,因为 X 跟 Y 之间没有加锁"。后来我们试了 RLHF 微调过的 GPT-3.5,同样的输入,review 质量明显上了一档——它真的能抓到代码里的 bug。

RLHF(Reinforcement Learning from Human Feedback)这三个字母,我估计大家都听烂了,但它具体解决了什么问题,我还是想用自己的话讲一遍。

第一步,你有一个 instruction-tuned 模型,让它对同一个 prompt 生成多个回答(比如 4 个)。第二步,人类标注员对这些回答排序——哪个最好,第二好,第三,最差。第三步,你用这些排序数据训练一个 reward model,这个 reward model 学会了"什么样的回答人类更喜欢"。第四步,你用 PPO(Proximal Policy Optimization)这种强化学习算法,让原始模型去最大化 reward model 给出的分数。

这个流程的精髓在哪?在于 reward model 学到的东西,比单纯的 instruction data 丰富得多。人类标注员排序的时候,不只是在说"这个回答格式对不对",而是在表达"这个回答整体上让我满不满意"。这种整体性的偏好,instruction data 是很难捕捉的。

但 RLHF 有个很要命的问题:**它非常不稳定,非常贵**。我们组 2023 年试过自己跑一遍完整 RLHF,光 PPO 训练这一步就折腾了三周。Reward model 一开始正常,但训练到后面会开始"被 hack"——模型发现某些 pattern 能稳定拿高分,就开始生成那些 pattern,生成质量反而下降。GPT-4 出来之前的很多开源模型,这个毛病都很明显。还有 PPO 的超参数特别敏感,learning rate 调大一点就崩,调小一点就不收敛,真的是玄学。

2024 年开始,DPO(Direct Preference Optimization)基本把 RLHF 的工程问题解决了大半。DPO 的核心思想特别优雅:既然 reward model 跟 policy 可以统一建模,那干嘛还要分开训练?直接用一个 preference pair(好的回答、坏的回答)做监督学习,让模型直接学会"更喜欢好的那个"。这玩意训练起来跟 instruction tuning 一样稳定,效果跟 RLHF 几乎打平,成本只有 RLHF 的几分之一。

我第一次跑 DPO 是用 trl 库,代码长这样:

```python
from trl import DPOTrainer

trainer = DPOTrainer(
    model=model,
    ref_model=ref_model,  # reference model,通常就是 SFT 之后的模型
    train_dataset=preference_dataset,  # 包含 chosen 和 rejected 的 dataset
    tokenizer=tokenizer,
    beta=0.1,  # 关键超参数,控制偏离 reference 的程度
)
trainer.train()
```

跑出来效果让我挺意外。我那个代码 review 的场景,DPO 之后模型的 review 准确率(我自己定义的:能正确指出至少一个真实问题)从 0.52 涨到 0.71。这个提升幅度比 instruction tuning 还大。但我没高兴太久,因为我发现 DPO 微调后,模型在通用对话上还是会有轻微的 catastrophic forgetting。最后我们采取的策略是:不做全量 DPO,用 LoRA + DPO,只更新一小部分参数,然后跟一个 instruction-tuned 的 base 模型做 ensemble。

2024 年中之后,围绕 DPO 又出了一堆变体——IPO、KTO、ORPO、SimPO。我自己试过 ORPO,效果还行但没有质的飞跃。我现在的判断是:**如果你要做 preference alignment,直接用 DPO 就行,不用追新**。这些变体在某些 benchmark 上好看,但落到具体业务场景上,差别没那么大,工程稳定性也未必比 DPO 好。

这里我想插入一个跟我们 Agent 主题特别相关的点——**RLHF/DPO 训练出来的模型,在 Agent 场景下到底带来了什么能力**?我自己的体感是三个:

第一个是**知道什么时候该拒绝**。未经对齐的模型,几乎永远在给你一个"听起来对的"答案。RLHF 之后的模型,会更倾向于在不确定的时候说"我不确定"或者"我需要更多信息"。这个能力对 Agent 至关重要——一个会胡说八道的 Agent,会把你整个下游 pipeline 都污染掉。

第二个是**tool use 的偏好对齐**。这个点可能比较细,但我观察到一个现象:RLHF 训练得好的模型,在决定"自己回答"还是"调用工具"这件事上,会更倾向选择调用工具,即使它自己其实能答对。这背后是因为人类标注员在排序的时候,会更喜欢"调用了正确的工具并给出准确结果"的回答,而不是"凭自己记忆给出一个大致对的"回答。这种偏好对齐,直接影响了 Agent 的 tool use 行为模式。

第三个是**长对话中的角色一致性**。一个没对齐的模型聊久了容易"飘",开始自相矛盾或者换风格。RLHF/DPO 之后的模型,会更稳定地保持它的角色设定。这对 multi-agent 系统特别关键——agent 之间是要协作的,如果每个 agent 都飘,协作就没法做了。

## 四、Function Call 跟 Tool Use:Agent 真正变成 Agent 的那一步

讲到这,前三节讲的都是"让模型更听话、更聪明"。但 Agent 跟普通 chatbot 最大的区别,是 Agent 能**调用外部工具**。这个能力,我得单独拎出来讲,因为它不只是一个工程技巧,它改变了模型跟环境的关系。

最早的"工具调用"其实非常原始。OpenAI 2023 年初搞的 plugins,本质就是在一个固定 prompt 里塞工具描述,然后让模型输出结构化的 JSON 来表示"我想调哪个工具"。代码大概是这种感觉:

```
You have access to the following tools:
- get_weather(location: string) -> object: Get current weather
- search_wikipedia(query: string) -> object: Search Wikipedia

To use a tool, respond with a JSON object:
{"tool": "tool_name", "args": {...}}

User: What's the weather in Tokyo?
Assistant: {"tool": "get_weather", "args": {"location": "Tokyo"}}
```

这套方案能用,但非常脆弱。模型经常把 JSON 格式写错,经常选错工具,经常在不该调用工具的时候调用。2023 年中 GPT-4 推出 native function calling,这个体验一下子就上了一个台阶——OpenAI 把 tool use 的能力直接做进了模型的 fine-tuning 里,模型在训练阶段就见过大量的 tool-use 例子,所以它的 tool 选择和参数生成都稳定得多。

Anthropic 紧跟着也推出了 tool use 能力,然后是 Google,然后是几乎所有的开源模型。这个能力很快变成了 Agent 的事实标准。我后来在项目里做 tool use,基本流程都是这个模式:

```python
tools = [
    {
        "name": "search_documents",
        "description": "Search internal knowledge base for relevant documents",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "top_k": {"type": "integer", "default": 5}
            },
            "required": ["query"]
        }
    },
    # ... more tools
]

response = client.chat.completions.create(
    model="gpt-4",
    messages=messages,
    tools=tools,
    tool_choice="auto"
)

if response.choices[0].message.tool_calls:
    for tool_call in response.choices[0].message.tool_calls:
        result = execute_tool(tool_call.function.name, tool_call.function.arguments)
        # 把 tool result 喂回给模型
```

但我想重点聊聊几个工程上的坑。

第一个坑:**工具描述怎么写**。这个事我踩过两次,每次都让我意识到自己之前的想法太天真。第一次,我让实习生写工具描述,他写得很"技术"——"This function takes a query string and returns a list of document objects with fields id, content, score"。我拿这个 prompt 跑了一遍测试集,工具选择准确率只有 0.68。后来我把描述改成"Search the internal knowledge base for documents relevant to the user's query. Use this when the user asks about company policies, internal procedures, or technical documentation",准确率涨到 0.84。

差别在哪?在**意图层面的描述**。模型不是看到一个函数签名去匹配,而是看到一个自然语言意图去判断"该不该用"。所以工具描述要写得像"什么时候该用我",而不是"我长什么样"。

第二个坑:**工具太多怎么办**。我们最早的工具库有 30 多个工具,塞到 prompt 里之后,模型选择准确率直接掉到 0.52——它在 30 个工具里挑花了眼。后来我们搞了两层架构:先用一个轻量分类器把用户 query 路由到对应的工具组(每组 5-8 个工具),再在组内让模型做最终选择。这个架构上线后,准确率回到了 0.81。这是一个非常典型的 Agent 架构问题,后面讲 multi-agent 的时候我们会再展开。

第三个坑:**tool call 的错误处理**。这个坑特别隐蔽。模型生成的 tool call 参数经常是错的——它可能把"Tokyo"传成"tokyo",把日期格式传错,把数字传成字符串。你必须在调用真实工具前做参数校验,在调用失败后给模型反馈让它重试。我后来养成一个习惯:每个 tool call 都用 pydantic 做 schema 校验,失败就把错误信息喂回给模型让它重新生成。代码大概是:

```python
for retry in range(3):
    try:
        args = ToolSchema.parse_raw(tool_call.function.arguments)
        result = execute_tool(args)
        break
    except ValidationError as e:
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": f"Error: {e}. Please fix the arguments and try again."
        })
        # 重新调一次模型
        response = client.chat.completions.create(...)
```

这个 retry + feedback 的模式,我后来在 multi-agent 项目里用得非常多,因为 Agent 之间传消息也会有类似的格式问题。

还有一个值得聊的趋势,是 **agentic tool use**——不是模型调一个工具,而是模型自己规划一个工具调用序列,自己决定先调什么、后调什么、怎么根据中间结果调整。这个能力在 2024 年中之后有质的飞跃,主要是因为各家模型在训练阶段就放入了大量的 multi-step agentic trace。我自己做的一组对比:GPT-4(2024 年 8 月版)在一个 5-step 工具链任务上准确率 0.78,GPT-4(2023 年 8 月版)是 0.51,差距非常明显。这意味着现在你给模型一个复杂任务,你可以相信它自己规划工具调用,而不需要你在 prompt 里把步骤写死。

到这里,我想收个尾。下一章会专门讲怎么给 Agent 写 prompt——也就是 instruction 的细节。这一章讲的是底层能力,下一章讲的是怎么把这些底层能力用出来。

## 给工程师的几个建议

第一,**选模型先看任务再选模型**。如果你做的是 chat/RAG 这种通用场景,GPT-4o、Claude 3.5 Sonnet 这种闭源模型基本就是天花板,没必要折腾开源。如果你做的是特定垂直领域(法律、医疗、代码),开源 + 微调的性价比可能更高。如果你做的是 latency 敏感或者数据敏感的场景,小模型 + 量化部署是合理选择。但不管哪种,**先用 API 跑通流程,再考虑自建**。我见过太多项目一开始就自建模型,最后死在了数据准备和训练稳定性上。

第二,**tool use 的能力现在是模型选型的硬指标**。一个模型哪怕综合能力很强,如果 tool calling 经常出错,你不要用它做 Agent。具体测试方法很简单:写一个 50 条样本的测试集,覆盖各种 tool call 的典型 edge case(参数错误、工具选错、不该调用时调用),然后跑一遍看准确率。这个数字比任何 benchmark 都直接。

第三,**不要自己训 DPO,除非你真的需要**。DPO 训练需要的 preference data 量很大、质量要求很高,我们自己训出来的模型几乎从来没打过闭源 API。如果你确实有隐私要求必须自建,优先考虑用现成的 preference dataset(WilmerHale、LMSYS 这些)做起点,再在你的领域数据上加几百到几千条 human annotation。这个量级通常已经能拿到不错的提升。

下一章我们聊 Prompt Engineering——具体怎么写指令能让模型在 Agent 场景下表现更好。这块我有一些自己踩过的雷,也有一些后来总结出的 pattern,会单独展开。