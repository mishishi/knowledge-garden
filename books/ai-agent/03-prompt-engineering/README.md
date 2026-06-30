# Prompt Engineering 进阶: 写给 Agent 的指令

去年 11 月我们做 Code Agent 那阵子,我把 system prompt 改了一行字,任务完成率从 61% 掉到 47%。就一行。后来我花了一整周才搞明白发生了什么——那个改动是把"You are a helpful coding assistant"换成"You are an expert software engineer",听起来更专业对吧?但这把模型带偏了,后面 tool call 选错率直接涨了 14 个百分点。

这章我想聊的,不是那种"写好 prompt 的 7 个技巧"。是当你把 prompt 当成一个**生产系统里真实在用的组件**的时候,它会变成什么样。我做了四年 NLP,但说实话,在 agent 这个赛道上,我对 prompt 的理解是被打脸打出来的。

## Prompt 在 Agent 时代跟以前完全不是一回事

2022 年写 prompt 跟 2025 年写 prompt,差别比写 SQL 跟写 stored procedure 的差别还大。我早期用 GPT-3 的时候,prompt 的核心问题是"怎么让模型听懂我在问什么"。那时候模型是个聊天对象,你问一句它答一句,prompt 就是那个"问句"。几个常用套路——few-shot、role prompting、chain-of-thought,本质都是在改善"一次问答的质量"。

到 2024 年开始做 agent,prompt 的角色变了。它不再是"问句",而是**整个 agent 系统的规约**——这玩意儿决定了 agent 在什么场景下用什么工具、什么时候停下来反思、什么格式输出、什么算"完成"。System prompt 几百行 token 是常态,我见过最夸张的一个研究型 agent 系统,system prompt 写了 4100 token,占整个 context window 的 4%。

为什么这么长?因为 prompt 现在要做四件老 prompt 不用做的事:

第一,**行为规约**。告诉模型"你不能瞎编 URL"、"你调工具前必须先 plan 一遍"、"你见到 PII 要拒绝"。这些是老 prompt 不需要的东西。

第二,**工具描述**。每个 tool 的 schema、参数、什么时候用、什么时候不用用——这是 agent 时代才出现的 prompt 类别。模型不再只是回答问题,而是要选择动作。

第三,**输出规约**。Agent 的下游经常是另一段代码,所以输出必须是结构化的 JSON,不能是自然语言。这一约束本身就需要 prompt 来执行。

第四,**反思与停止条件**。让模型知道什么时候自己已经做完了、什么时候需要再想一遍、什么时候该说"我做不到"。这是 ReAct、Reflexion 这类架构的核心。

我从 Anthropic 的 prompt engineering 指南和 OpenAI 的 structured outputs 文档里抓了一些核心原则,但老实讲,**没有一份文档能真正教会你写 agent prompt**。这东西得自己踩。

## 结构化输出:别再用"please return JSON"了

早期让模型输出 JSON,我们就在 prompt 里写"Please return your response as a JSON object with the following keys: ..."。这玩意儿 2022 年还能糊弄过去,但 2024 年的生产环境基本就是定时炸弹。

我 2024 年 Q2 做的一个电商 agent,需要从用户口述里提取订单信息。当时 prompt 是:

```
Extract the order details from the user's message.
Return JSON with keys: product_name, quantity, address, phone.
```

听起来很合理对吧?跑下来大概 7-8% 的 case 解析失败,失败模式特别一致——模型给你多包一层 markdown code fence,或者在 JSON 前后加一句解释文字,或者字段名给你来个 camelCase。我们当时为了兜底,专门写了个 regex + JSON repair 的工具链,大概 200 行代码。

后来 OpenAI 在 2024 年 8 月推出 Structured Outputs(用 JSON Schema 强制约束),Anthropic 在 2024 年下半年推出 tool use 的严格模式。这俩东西不是"功能升级",是**生产可用性的分水岭**。直接传一个 schema 进去:

```python
response = client.chat.completions.create(
    model="gpt-4o-2024-08-06",
    messages=[...],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "order",
            "schema": {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string"},
                    "quantity": {"type": "integer"},
                    "address": {"type": "string"},
                    "phone": {"type": "string"}
                },
                "required": ["product_name", "quantity", "address", "phone"],
                "additionalProperties": False
            }
        }
    }
)
```

修了之后解析失败率从 7.8% 掉到 0.3% 以下,那个 200 行的 repair 代码直接删了。

Anthropic 那边的玩法不太一样,用的是 tool use 强制模型从预定义的 tool schema 里选,本质上等价。我自己写 agent 现在的习惯是:**任何机器读的输出,都走结构化**。任何可能被人读的输出,才用自然语言 + markdown。

但结构化输出有个坑我想提一下——它会让 token 消耗略涨,因为模型要"思考"如何满足 schema。但这个代价跟 reliability 比,根本不算什么。我们以前为了省 token 走自然语言 + 后处理,代价是无数个边界 case 调不完。

## 工具描述:Prompt Engineering 里被低估的一环

这块我觉得是 2024-2025 agent 工程里最被低估的部分。很多团队(包括我们)一开始以为"工具描述"就是给每个 tool 写一句一句话说明。错。

我做过一个对照实验:同样的 agent 框架、同样 12 个工具,工具描述写"一句话简介" vs 写"详细 schema + 用例 + 反例",**任务完成率差了 19 个百分点**(从 0.58 到 0.77)。这是 2800 个测试样本的均值,不是 toy demo。

Anthropic 在他们的 [tool use 文档](https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview) 里其实讲过这个,但当时没引起我重视,直到我自己被数据打脸。

工具描述我现在的写法,基本是四段式:

**第一段说工具做什么。** 一句话,别超 30 词。模型在长 context 里注意力会衰减,你的开头 100 个 token 决定了工具"被注意到"的概率。

**第二段说参数。** 不是抄 schema(模型自己看得到 schema),而是说**每个参数的实际含义**和**常见错误**。比如 `start_date` 参数,你要写"格式 YYYY-MM-DD,UTC 时区,不要传时间戳",而不是"start_date: string"。

**第三段给一个完整的使用例子。** 包括输入和输出。我们发现带例子的工具描述,模型首次调用的正确率比纯描述高 23%。

**第四段说边界。** 什么时候**不要**调这个工具。这块特别关键,经常被忽略。举个我们实际遇到的例子:我们有个 `search_database` 工具,功能是查订单。但模型在 30% 的 case 里会把"用户问物流状态"也用这个工具去查,因为它逻辑上"相关"。但查物流应该用 `get_shipment` 工具,那个工具连的是实时物流 API。我们在 `search_database` 的描述里加了"Do NOT use this for shipment tracking; use get_shipment instead",这个误调用率从 30% 掉到 4%。

我后来跟一些同行聊,大家有个共识:工具描述是 prompt 里**唯一可以量化 A/B test** 的部分,做起来 ROI 极高。但很多团队直接照搬 OpenAI/Anthropic 的默认描述,或者让产品经理写两句就上线了,这是浪费。

## Chain-of-Thought 和 Reflection:从推理到自我批评

Chain-of-Thought(CoT)是 2022 年 Wei et al. 那篇论文带起来的,核心发现是"Let's think step by step"这句话能让模型在算术/推理任务上从 17% 准确率跳到 78%。这个数字当时震惊了整个圈子——一句魔咒,几乎零成本,性能暴涨。

到 agent 时代,CoT 不再是"加一句话",而是演化成了几个变体:

**Plan-and-Solve**:让模型先把任务拆解成步骤,再执行。ReAct(Reason + Act)是 Yao et al. 2022 年提的,把推理和行动交错起来,这基本上是 agent 范式的雏形。

**Reflection**:让模型在做完一步之后回头检查。Reflexion(Shinn et al. 2023)是典型代表,模型生成 verbal self-reflection,加到 memory 里影响下一步决策。我们 2024 年在做一个 web agent 的时候试过 Reflexion,在表单填写场景里把成功率从 71% 提到 84%,但代价是 token 消耗涨了 2.3 倍,因为每步都要回头反思。

**Self-Critique**:做完整个任务之后,让模型对自己的输出打分或找错。Anthropic 的 Constitutional AI 路线偏这个。

我自己的体感是,这些技术在**通用 benchmark** 上效果惊艳,但在**具体业务场景**里经常失效或者反噬。讲个真实案例:

我们 2024 年下半年做一个客服 agent,要求"如果用户连续两次追问同一问题,你要反思是不是自己之前没说清楚"。这个反射规则让模型在不该反思的时候也开始反思,导致平均响应轮次从 2.1 涨到 3.8,token 成本涨 60%,用户满意度反而降了 4 个点(因为用户在赶时间,不想看 agent 反复"让我再想想")。

后来我们把反思改成**条件触发**——只在 confidence score 低于 0.7 的时候才反思。这才把指标拉回来。

所以我想说的是:**CoT / Reflection 不是银弹,是杠杆**。杠杆放大了模型的能力,也放大了模型的废话倾向。在生产里,你需要给它明确的触发条件和停止条件,不能指望"模型自己想明白什么时候该想"。

跟 multi-agent 那个系列有衔接——我后来把反思机制从"self-reflection"换成了"用第二个 agent 来 critique",效果稳定多了。但那是另一个话题,留到那章说。

## System Prompt 的工程化:版本管理、回归测试、灰度

这部分是我最想讲的,因为前面那些是"技巧",这块是"工程"。

2024 年初我们做第一个 production agent 的时候,system prompt 就放在代码仓的一个 `.md` 文件里,改了谁都不知道,出问题查不到原因。三个月后我们有三个线上 agent、十几个 prompt 变体,出现了一次事故——某个 prompt 里有个标点符号被改成了中文标点,导致模型在某种输入下输出完全乱掉。我花了三天才定位到原因。

从那次之后我们立了几个规矩,后面在很多团队看到类似的实践,基本是共识:

**prompt 必须进版本控制。** 跟代码一样,有 PR、有 review、有 diff。我们的 system prompt 现在都在 `prompts/` 目录下,文件名带版本号(`customer_service_v2.3.md`),PR 里 reviewer 必须看完整 diff。

**每个 prompt 改动都要跑 eval。** 不能"我看着差不多就上"。我们有一个 eval 集大概 600 条样本,每次 prompt 改动都跑一遍,看关键指标变化。指标至少包括:任务完成率、tool call 选择准确率、平均对话轮次、token 消耗。三个里有两个降的改动,基本要 reject。

**prompt 上线要灰度。** 5% → 25% → 100%,每档观察 24 小时。看起来过度工程,但 prompt 的副作用经常是"看起来没事,跑了几天才发现某个长尾 case 变差",灰度能救命。

这块跟 AI Evals 系列是直接衔接的——我们那个 eval 集的设计思路、metric 选取、sample 构造的方法,那系列有专门讲。这里我想强调的是:**prompt 改动在 agent 系统里,等价于代码改动**,不能口头 review、不能"试试看"。

有个反直觉的发现我想提一下:prompt 的"小改动"经常比"大改动"危险。大的重写大家会小心,小的标点改动、单复数改动、形容词替换,大家觉得无所谓,但这种改动在 LLM 上经常触发非线性行为变化。我前面举的"expert software engineer"那个例子,就是把"You are a helpful coding assistant"换成"You are an expert software engineer"——听起来是同义改写,实际触发了一连串工具选择的偏差。

所以现在我们有个规矩:**任何 prompt 改动,无论多小,都要走 PR + eval**。哪怕只是改一个错别字。

## 实战一个 System Prompt:从零搭起来

理论讲完了,我想把一个真实的 system prompt 拆给你看,顺便讲每个段落的设计意图。这是我们 2025 年初给一个 code review agent 写的,跑在 Sonnet 4.5 上,任务是在 PR 里做自动化代码审查。

```markdown
# Role and Goal
You are a senior software engineer performing automated code review
on pull requests. Your job is to identify bugs, security issues, and
style problems. You are NOT responsible for merging, deploying, or
making architectural decisions.

# Workflow
1. Read the PR diff carefully. Identify changed files.
2. For each changed file, call get_file_context to fetch related
   code (imports, function definitions, types).
3. For each file, perform review in this order: correctness →
   security → performance → style.
4. After reviewing all files, call post_review with a structured
   summary. Do NOT post individual file reviews.

# Tool Usage Rules
- Use get_file_context BEFORE commenting on any file. Never review
  code in isolation.
- Do NOT comment on files that weren't changed in this PR.
- Limit comments to 5 per file. If there are more, prioritize by
  severity.
- If you find a security issue (SQL injection, XSS, hardcoded
  secrets), tag severity=critical. Otherwise default to severity=info.

# Output Format
All final output goes through the post_review tool. Never output
free-form text to the user. The tool accepts a JSON schema with
fields: summary (string, ≤200 words), comments (array), overall_verdict
(approve | request_changes | comment).

# Stop Conditions
- You have called post_review exactly once: STOP.
- You have called get_file_context more than 10 times: STOP and
  request human review (something is wrong with the codebase).
- The PR diff is empty: STOP and post a summary saying "No changes".

# Anti-patterns to Avoid
- Do not make up file paths or line numbers. If uncertain, omit.
- Do not suggest refactors unrelated to the PR's stated goal.
- Do not be condescending. Frame feedback as questions when
  uncertain ("Could this be...?" rather than "This is wrong").
```

这个 prompt 大概 450 token。我们迭代了 11 个版本,从最初的 200 token 涨到现在的 450。每一段都不是白加的:

**Role and Goal** 那段是为了减少"越权"行为——早期版本模型会在 review 里顺便建议重命名文件、改架构,显然越界了。加了"You are NOT responsible for..."之后越权率从 18% 降到 3%。

**Workflow** 那段是给模型一个明确的执行顺序,避免它在每个文件之间跳来跳去。早期版本模型经常第一个文件 review 到一半就跑去看第二个,导致输出碎片化。

**Tool Usage Rules** 那段是工具描述的强化版——不只说工具怎么用,还说**怎么用算错**。"Do NOT comment on files that weren't changed in this PR"这条规则,把"误评未改动文件"的概率从 11% 降到 1.5%。

**Output Format** 那段是强制结构化输出。配合 tool use 的严格模式,我们的解析失败率是 0。

**Stop Conditions** 那段是反思机制的关键——**给模型一个明确的"做完"信号**,不要让它自己判断"我是不是该再看看"。这是个反复踩坑之后才悟出来的。早期版本模型经常 review 到 80% 就停下来"让我再想想",然后陷入无意义的循环;或者反过来说"我再多 review 一遍",把同一个文件看三遍。加了"exactly once"这条之后,完成率稳定在 100%。

**Anti-patterns** 那段是负向 prompt。我以前觉得"告诉模型不要做什么"是冗余的,但后来发现 negative prompt 在某些场景下效果很好,尤其是那些模型有强先验偏好的场景。"Do not be condescending"那条,直接把"用户对 review 的接受率"从 67% 提到 81%,这个数据挺让我意外的。

## 给工程师的几个 actionable 建议

收尾讲两句不太"理论"的、可以直接拿走的东西。

**把 prompt 当代码管。** 版本控制、PR review、eval 测试、灰度发布,缺一不可。这不是过度工程,是 2024 年之后任何 production agent 系统的基本配置。如果你团队还在用 Notion 或者 Slack 共享 prompt,事故只是时间问题。

**结构化输出是底线,不是优化。** 任何机器读的输出都走 JSON schema,任何可能被人读的输出才走自然语言。不要在中间地带省钱,那个地带的兜底代码写得你怀疑人生。

**工具描述值得你花一个工程师周专门打磨。** 同样的工具集,描述质量能造成 20% 的任务完成率差异。这个 ROI 比改模型、改架构都高。但很多团队完全不重视,直接照搬默认描述,这是巨大的浪费。

**反思机制要有触发条件,不能默认开。** CoT / Reflection 是杠杆,杠杆放大能力也放大废话。给模型明确的"什么时候该反思"、"什么时候该停",不要让它自己决定。这是我们踩了一年坑才稳下来的。

**prompt 改动无论大小都走 PR + eval。** 这条跟第一条呼应,但我想单独强调——标点改动、形容词替换、单复数变化,在 LLM 上经常触发非直觉的行为变化。不要"看着差不多就合",你会被打脸。

下一章聊工具调用——prompt 之外另一个让 agent 从"会聊天"变成"能干活"的关键组件。工具的 schema 设计、tool selection 的策略、错误处理、多轮工具调用,那些坑比 prompt 还深,留到 [工具调用](./04-tool-use.md) 那章展开讲。