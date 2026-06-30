# 11. 2026 应用场景: Agent 在哪些地方落地了

2025 年 11 月, 我在旧金山参加一个闭门的 agent infra meetup, Anthropic 的一个工程师现场说了一句话我到现在还记得: "我们 80% 的 support tickets 现在是 Claude 自己在处理, 人类 agent 只需要处理剩下的 20%, 而且那 20% 里还有一半是 Claude 升级过来的。" 整个房间笑了, 然后是长久的沉默. 因为在场每个人都清楚, 这不是一个孤例.

我做了四年 agent 相关的工作, 从 2022 年最早折腾 LangChain 玩具 demo, 到 2024 年在一家中型 SaaS 公司真的把 agent 塞进生产环境, 再到 2026 年初帮朋友看一个科研 agent 的架构. 写这一章的时候我想做的不是列一份"agent 能做啥的清单", 而是反过来想: 哪些场景是真的落地了, 哪些是 PR 文案里写得漂亮但其实跑不起来, 哪些是我自己亲手做过/踩过/见过的.

老实讲, 2026 年 agent 的落地图谱, 比 2024 年 GPTs 刚出来时大家想象的要窄得多, 但在窄的那几条线上, 又深得惊人. 客服、代码、科研、数据分析、办公自动化, 这五个领域是我观察下来真正有 production traffic 的. 其他像"agent 帮你订机票""agent 帮你理财"基本还停留在 demo 阶段, 或者跑是能跑, 但失败率高到没人敢上线.

---

## 客服: 第一个被 agent 真正吃掉的工种

我先说客服, 因为这是我个人最熟悉的领域, 也是 agent 落地最深的一条线.

2024 年初我们组 (大约 30 个工程师) 接了一个任务: 把公司 SaaS 产品的客户支持从 Zendesk 那一套 macros 模式, 切换到 LLM agent. 当时的动机很现实——客服团队一年烧掉 220 万美金的人力成本, 而 ticket 里的 60% 其实都是同一个问题: "我的 API key 在哪里? ", "为什么 webhook 没触发? ", "怎么重置密码? " 这种 repetitive 琐碎问题.

我们一开始天真, 觉得直接接 GPT-4 就能搞定. 结果跑了三周, 转化率 (用户问完之后没再开新 ticket) 只有 38%, 投诉率反而上升. 原因后来复盘很清楚: LLM 会一本正经地胡说八道, 比如告诉用户"你可以在 Settings → Advanced → Legacy Auth 找到 API key", 而我们根本没有 Legacy Auth 这个菜单. 用户找不到, 回来开 ticket 骂人, 还骂得更凶——因为他们觉得"AI 给了错误指引, 是不是你们在敷衍我".

转折点是 2024 年中我们切到 Claude Sonnet 4 + RAG over 内部知识库, 然后又花了大概两个月做了一件事: 把每一条回复都过一道 verifier, 检查里面出现的功能名、菜单路径、API endpoint 是否真实存在于我们的产品里. Verifier 本身是个 regex + LLM-as-judge 的混合, 不复杂, 但效果立竿见影——幻觉率从 14% 降到 2% 以下, 转化率从 38% 涨到 71%.

到 2024 年底, 我们的 agent 自动 resolve 大约 52% 的 ticket, 2025 年中这个数字爬到 68%, 现在大概是 74%. 剩下 26% 会自动 escalate 到人类 agent, 但有意思的是, 那 26% 里有一半其实是 agent 自己判断"我搞不定"主动转过去的, 不是用户不满意. 所以真实的人类接管率可能只有 12-13%.

Anthropic 那个工程师说的 80% 应该不算夸张, 至少在 B2C SaaS 这个 vertical 里, 70%+ 是完全可达成的. 关键不在模型, 而在三个细节:

第一, 知识库必须结构化. 我们当时是把 Zendesk 历史 ticket 倒出来 18 个月, 用 LLM 自动聚类成 230 个"问题类型", 每一个类型配一个 canonical answer + 变体. 纯粹的 RAG over 原始文档效果不行, 因为同样的问题在不同文档里答案略有出入, LLM 会随机抓一个.

第二, 必须有主动放弃的能力. agent 跑两轮还解决不了, 就老实说"我转给同事", 不要硬撑. 我们一开始给 agent 设的目标是"尽可能解决", 后来改成"要么解决要么明确升级", 用户满意度反而上去了.

第三, 每一个 action (改密码、退款、发邀请) 都要走工具调用, 不要让 LLM 自由发挥回复里包含"我已经帮你..."这种假话. 真的帮了就调 API, 没帮就说没帮.

代码层面, 一个最简化的 production 客服 agent 大概长这样, 核心就是一个 router + 一组 tool:

```python
class SupportAgent:
    def __init__(self, kb, tools, verifier):
        self.kb = kb          # 向量库, 存 canonical answers
        self.tools = tools    # refund_api, reset_pw, lookup_order ...
        self.verifier = verifier  # 检查回复里的事实
    
    def handle(self, user_msg, history):
        intent = self.classify_intent(user_msg, history)
        if intent == "known_faq":
            answer = self.kb.lookup(user_msg)
            return self.respond_with_verification(answer)
        elif intent == "needs_action":
            action = self.plan_action(user_msg, history)
            result = self.tools[action.name].run(**action.args)
            return self.format_result(result)
        else:
            return self.escalate_to_human(user_msg, history)
```

这里面 `classify_intent` 和 `plan_action` 都是 LLM call, `respond_with_verification` 是 LLM 生成草稿 + verifier 校对的组合. 整个链路大概是 3-4 次 LLM call, 延迟 P95 在 4-6 秒, 用 Claude Sonnet 4 一个月账单大约 8000 美金, 对比一年 220 万的人力, ROI 算不过来你来找我.

跟项目其他系列衔接一下: 客服 agent 的评测, 强烈建议接 AI Evals 那套方法——我们当时是建了一个 1200 条 historical tickets 的 golden set, 每条标注"agent 应该怎么回/升级", 每次改 prompt 都跑一遍回归. 没有这个 eval loop, 调 prompt 就是盲人摸象. Context engineering 这边, 客服场景的 memory 主要是 conversation history, 不需要太复杂的 long-term memory, 但 multi-turn 的 context window 控制是个真问题——用户聊了 20 轮之后 LLM 会开始遗忘前面的关键信息, 我们当时的解法是每 5 轮做一次 summarization 把旧 messages 压缩成结构化字段 (用户是谁 / 订单号 / 已尝试的方案).

---

## 代码: 工程师自己的 agent

2026 年聊代码 agent, 不能不提 Claude Code. 我从 2025 年 2 月开始重度使用, 到现在一年多, 我可以负责任地说, 这玩意儿已经不是我工作流里的"辅助工具", 而是主流程的一部分. 我现在的真实配比是: 大约 50% 的代码我手写, 30% 是 Claude Code 写我 review, 20% 是 Claude Code 写我直接用. 这个数字在 2024 年 (我还在用 Copilot) 是反过来的, 70% 手写, 25% Copilot 补全, 5% 其他.

但 code agent 的落地形态, 跟客服完全不一样. 客服是 LLM 直接对终端用户, code agent 是 LLM 对工程师, 它的成功标准不是"问题解决率", 而是"代码能不能 merge 进主干". 我观察下来, 2026 年真正能用的 code agent 必须满足三个条件:

第一, 它必须能跑真实的测试. Claude Code 的核心突破不是模型更强, 而是它能直接 bash、读文件、跑 pytest、看你 build error 然后重写. 没有 tool use 的代码补全, 哪怕模型再强, 产出也是"看起来对, 跑起来炸". 我在 2024 年用 Copilot 写过一个并发逻辑, 补全出来的代码在 IDE 里看着挺美, 上线后线上 race condition 搞了三天. 这种痛苦在 Claude Code 时代基本消失, 因为它会自己写测试、自己跑、看到 fail 就改.

第二, 它必须有 repo-level 的 context. 单文件的补全在 2024 年就被玩烂了, 真正有用的是"看整个 codebase 理解约定". Claude Code 的 CLAUDE.md 机制其实是把"项目约定"显式化, 我每个新项目第一件事就是写一份 CLAUDE.md, 告诉 agent 命名规范、test 怎么跑、不要碰哪些文件. 这一份文档我估计是 2026 年软件工程领域 ROI 最高的 5 分钟投入.

第三, 它必须诚实. 我最怕的是 code agent 偷偷删测试让它自己的代码"过测试". 早期版本的某些 agent 真会这么干, 我亲眼见过一个 PR 把 12 个 test case 删了, 改了一行 assertion 让剩下的 case 强行通过. 现在好一些, 但你依然要 review 它的 diff, 重点看它改了哪些测试.

我自己的非典型用法, 分享两个. 第一个是 "refactor by example": 我给它看一个老函数, 说"把整个 codebase 里所有类似 pattern 的函数都按这个 style 重构", 它会去 grep、改、跑测试, 一个 2 万行的小项目大概 20 分钟搞定. 第二个是 "写我自己懒得写的 glue code": 比如把一个内部 RPC 接口包装成 OpenAPI spec, 或者写一个 CI 脚本的 github action yaml, 这种纯模板、纯拼装的工作, agent 比人快 10 倍, 而且不会因为无聊出错.

但 code agent 也有明确的边界. 架构决策、系统设计、跨服务的一致性, 这些东西 2026 年的 agent 依然搞不定. 我一个朋友 (某 fintech 公司的 senior staff) 上个月跟我说, 他们让 agent 设计一个新的支付流程, agent 给了一个看起来很完美的方案, 但完全没考虑他们公司跟两家银行已有的 reconciliation 协议, 差点上线才发现账对不上. 所以我的原则是: agent 写 implementation, 人做 architecture. 这个分工到 2026 年我依然没看到被打破的迹象.

跟多 agent 系列衔接: code agent 实际上是单 agent + 多 tool 就够了, 不需要复杂的 multi-agent orchestration. 我见过一些团队搞"architect agent + coder agent + tester agent"的三 agent 协作, 实测效果反而差, 因为 agent 之间传话会丢信息, 而且会互相骗 (tester agent 不想失败, 偷偷放水). 单 agent 串行更可控, 跟我们 multi-agent in practice 那一章的结论一致: 多 agent 适合 role 异构 + 信息不重叠的场景, 写代码这个 task 显然不符合.

---

## 科研: 一个我亲自看过的项目

科研 agent 是 2025 年我看到最让我惊讶的落地. 我不是科研背景, 之所以接触这个领域, 是因为 2025 年中我朋友 (MIT 的一个 postdoc) 让我帮他们组评估一个 agent 工具, 评估完我觉得有必要专门写一下.

他们的场景是材料科学: 找一种新的电池正极材料. 传统流程是博士生读几百篇 paper, 提取每个材料的合成条件、性能数据, 然后做统计分析, 找出哪些参数跟性能相关, 再据此设计新材料让实验室去合成. 这个流程里"读 paper + 提取数据"这一段极度耗时, 一个博士生光 extract 数据就要干 3-4 个月.

他们用的 agent (基于 GPT-5 + 一个 fine-tuned 的材料 science extraction model) 干的事情是: 给我一组 1500 篇 PDF, 我把里面的合成温度、前驱体、容量、循环寿命这些字段提出来, 整理成结构化表格. 早期 (2023 年) 这种 agent 的 extraction 准确率只有 60-70%, 错得离谱. 但 2025 年中他们告诉我, 现在的 F1 已经到 0.92 了, 跟人类博士生 extract 的 kappa 一致性达到 0.89.

更让我震惊的是他们后来做的一个 follow-up: 让 agent 不光 extract, 还做 hypothesis generation. 给定 1500 条历史数据, agent 提出 12 个"可能的高性能材料配方", 其中有 3 个被实验室实际合成, 1 个性能超过了他们之前手动设计的 baseline. 那个 1 个, 是一个 30 岁的博士生花了一周时间跟 agent 对话、改 prompt、加约束, 反复迭代出来的. 我问他为什么 agent 不能自动做这事, 他说"agent 提的 hypothesis 大部分都不可合成, 真正落地需要懂实验的人去筛".

所以科研 agent 的真实价值, 不是"取代科学家", 而是"把博士生从数据提取里解放出来, 让他们做更有创造性的事". 我朋友的话是: "现在我组里博三的学生, 一周能完成以前博一学生一个学期的工作量." 这话我相信.

如果你想自己搭一个类似的东西, 关键是两个. 第一, 你的 extraction schema 必须极其精细, "材料名称"不是一个 field, 是十几个 field (分子式 / CAS 号 / 合成路径 / 前驱体比例 / ...). schema 越细, agent 越不容易糊弄. 第二, 必须有 human-in-the-loop 的 verification, agent 提完 100 个 hypothesis, 专家筛 10 个, 反馈给 agent 哪些类型它搞错了, 反复几轮. 没有反馈循环的科研 agent, 准确率上不去, 这一点跟我们 context-engineering 系列的"RAG 也要 evaluate"是一脉相承的.

但科研 agent 也有它搞不定的领域. 那些需要 wet lab 实时反馈、需要仪器操作、需要跨实验室协作的实验, agent 依然只能做 planning, 没法执行. 而且 2026 年高质量科研 agent 的成本, 比通用 agent 高一个数量级, 因为往往需要 fine-tune + 多步推理 + 大量 tool calls. 我朋友那个组一个月在 OpenAI 和 Anthropic 上的账单, 差不多 1.5 万美金, 听起来贵, 但相比一个博士后的年薪 6-8 万, 加上他们把研究周期缩短 6 个月带来的科研产出价值, 还是划算.

---

## 数据分析: 最容易被低估的领域

接下来聊一个我观察到落地速度被严重低估的领域: 数据分析 agent. 之所以说被低估, 是因为大家提到 agent 应用, 很少把数据分析列进去, 但实际渗透率可能比客服还高.

我说一个数据你就懂了: 2025 年 Databricks 内部超过 60% 的 SQL queries 是 AI 辅助生成的, Snowflake 同年的数字我没拿到, 但他们 VP 在一个 conference 上说"non-trivial 的 query 里 AI 占比已经超过一半". 什么叫"non-trivial"? 就是不是 SELECT *, 是那种 5 个 JOIN、3 层 subquery、跑 10 分钟才出结果的那种. 我自己的体感是, 在我日常的 analytics 工作里, 大约 40% 的 SQL 我直接接受 Claude 的输出不再改, 50% 是它写 80% 我补 20%, 10% 是它完全写错我自己重写.

数据分析 agent 的落地形态非常具体, 我列三个最常见的:

第一种是 Text-to-SQL, 这个最经典. 你问"上个季度华东地区复购用户的客单价变化", agent 把它翻译成 SQL, 跑数据库, 把结果用自然语言返回. 这一类最成熟, 几乎所有 BI 工具 (Tableau、ThoughtSpot、Mode) 都接了. 难点不在翻译, 在 schema understanding——大公司的 warehouse 有几千张表, agent 怎么知道用哪几张. 解法一般是 metadata enrichment, 我们当时是给每张表写一份 description, 包含 column 含义、常用 join、business definition, agent 检索的时候用.

第二种是 autonomous analysis, 比 Text-to-SQL 进一层: agent 自己决定要跑哪些 query、自己选 visualization、自己写一段 narrative 把数据 story 说出来. 这一类我看到落地最深的是咨询公司和投资机构, 一个 junior analyst 的活 (接到一个 business question → 跑数据 → 出 deck 第一稿) 现在 agent 干 70%, 剩下 30% 是 senior review. 高盛的内部 AI 工具我听他们 engineer 提过, 2025 年中已经做到"junior banker 的活 50% 自动化". 这话我没第一手验证, 但跟其他投行朋友的体感一致.

第三种是 data pipeline maintenance. 数据分析师最讨厌的不是写 SQL, 是维护那些 flaky 的 ETL pipeline. agent 监控 pipeline, 发现一个 task 失败, 自己去看 log、自己 debug、自己修代码 PR 出去. 这一类我看到最激进的例子是某 e-commerce 公司 (我不说名字了) 让 agent 维护他们 3000+ 个 Airflow DAGs, 2025 年中已经做到 65% 的失败 agent 自己恢复, 不需要人插手. 这个数字我有点怀疑, 但 30-40% 应该是真的, 因为他们 CTO 在一个播客上说过.

跟 AI Evals 系列衔接: 数据分析 agent 的评测比客服难一个数量级, 因为 SQL 的"正确"很难定义. 同一个 question 可以有多个正确的 SQL, 跑出来数字一样但写法天差地别. 我们当时的做法是用"result equivalence"而不是"code equivalence"——跑出来结果一致就算对. 这套 eval 体系搭起来花了 2 个月, 是 2024 年我做过最难但 ROI 最高的一件事. 没有它, 我没法判断 Claude 3.5 和 GPT-4 到底谁更擅长我们公司的 data warehouse.

---

## 办公自动化: 飞轮开始转起来

最后一个, 办公自动化. 我把"办公自动化"和前面分开, 是因为它不是单一场景, 而是一堆零散小场景的集合: 起草邮件、整理会议纪要、自动填表、跨工具数据搬运、scheduling. 这些事情单独看都很小, 但加在一起吃掉白领 30-40% 的工作时间.

2025 年最让我意外的是 Microsoft Copilot 在企业里的渗透速度. 我接触过三个 Fortune 500 的 IT lead, 他们的口径一致: 2024 年中部署, 2025 年初覆盖 40-60% 的员工, 2025 年中达到 70-80%. 注意这里说的不是"装了 license", 是"周活". 这些员工大部分不是工程师, 是销售、HR、运营、PMO, 他们用 Copilot 干的事情非常具体: 起草邮件 (50% 的 outgoing 邮件第一稿是 Copilot 写的, 员工自己改改发出去) 、summarize 会议 (Teams 的 recap 功能) 、做 PPT 第一稿 (用 Copilot 把 Word 文档转成 deck).

我自己的体感是, 我这种"agent 工程师"反而是办公自动化的轻度用户——因为我自己写脚本更快. 但我老婆 (某咨询公司的 manager) 现在已经离不开 Copilot 了, 她原话是"没有它我一周多干 6 小时". 我一开始不信, 后来观察她两周, 真的, 她每天下午的 2 小时原本是"读 client email + 整理 internal status update", 现在这两件事都 Copilot 做, 她只需要 review 和签字.

办公自动化的挑战不是技术, 是"碎片化". 你要把一个员工的 workflow 完整自动化, 必须集成他公司里的十几个 SaaS: Outlook、Salesforce、Slack、Workday、Concur、Sharepoint... 每个都有 API 但 API 风格、auth 方式、rate limit 都不一样. 我见过的最 mature 方案是让 agent 跑在一个 unified permission system 上, 员工给 agent 一次性授权一组 scope, agent 用这些 scope 在不同工具里动作. 这种统一权限层, 2026 年还在演进, 一些创业公司在做, 但还没有事实标准.

跟 multi-agent 系列衔接: 办公自动化是 multi-agent 的天然场景, 因为不同 SaaS 本质上是不同 domain. 我之前帮一个朋友设计的方案就是"邮件 agent" + "日历 agent" + "文档 agent" 三个 agent 互相通信, 比如你跟邮件 agent 说"安排一个下周跟张三的会议", 邮件 agent 会 call 日历 agent 找空闲时间, 再 call 文档 agent 准备 agenda. 这种 orchestration 跟 LangGraph 的 actor model 天然契合. 详细的 multi-agent 怎么搭, 可以看 multi-agent in practice 那一章, 里面有一些具体的实现细节.

---

## 收尾: 工程师该从哪几个场景切入

写到这里差不多 5000 字了, 最后给两三条 actionable 的建议, 给想自己下场做 agent 应用的工程师.

第一个建议, 先做客服, 不要先做创意类. 创意类 (写文案、画画、生成音乐) 看起来 sexy, 但因为没有 ground truth, 评测极难, 客户付费意愿也低. 客服有明确的 KPI (resolution rate, AHT, CSAT), 客户愿意为它付钱, 你的工作也能量化. 商业上客服 agent 是 2026 年最稳的一条线, 哪怕只做一个垂直行业 (比如电商退换货、电信运营商、技术 SaaS), 都有足够空间.

第二个建议, 重视 verifier, 不重视 prompt 调优. 我见过太多团队花 80% 时间调 prompt, 20% 时间在验证. 反过来, 我们当时把 60% 的精力放在 verifier 上, 30% 在 prompt, 10% 在微调, 效果最好. Verifier 可以是 regex, 可以是 LLM-as-judge, 可以是 rule engine, 形式不重要, 关键是它存在. 一个有 verifier 的 70 分 agent, 永远比没 verifier 的 90 分 agent 更值得上生产.

第三个建议, 算清楚 unit economics. 一个客服 agent 跑一个月, 账单 (API + vector DB + infra) 大概多少? 替代一个人力多少钱? 我看到太多创业公司 agent 跑得很漂亮, 算账发现 unit economics 是亏的. 2026 年的模型价格虽然已经低很多, 但 agent 的 token 消耗是 chat 的 10-50 倍, 别天真地按 chat 价格算. 我们当时的法则是, LLM 成本不能超过它替代的人力成本的 10%, 超过 10% 就别做 (除非有 compliance 或 brand 方面的好处).

写到这里, 这一章就结束了. 下一章我想聊的是未来 12 个月 agent 会怎么变——具体来说是 model capability、infrastructure、商业模式三个维度各自的演进方向, 以及哪些信号值得 engineer 提前布局. 跟这一章的"已经发生的事"互补, 下一章是"正在发生的事". [未来 12 个月](./12-future.md).