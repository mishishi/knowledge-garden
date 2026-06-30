# Memory: Agent 怎么记得

我第一次觉得 agent 的 memory 是个真问题,是在 2023 年底跑一个客服 bot 的时候。当时用户问完一个问题,bot 答完一轮,下一轮它就忘了。不是"答得不好"那种忘了,是"完全不记得你叫张三、你三分钟前提过订单号 12345"那种。这种"上一秒还聊着,下一秒就失忆"的状态,让我意识到 context window 不是 memory。

后来两年里,我先后做过 SaaS 客服、内部知识库助手、code review agent、还有两个偏研究性质的多 agent 仿真项目。Memory 这块,我从一个"塞进 prompt 就行"的朴素观念,演进到现在系统性地把 memory 当成一个分层架构来设计,中间踩过的坑够写一章。

这一章我想讲的是:agent 的 memory 到底分几层,每一层解决什么问题,2024 到 2026 这两年我们是怎么把这些概念从论文里搬到线上系统里的,以及哪些工程上的取舍你做 agent 绕不开。

## 为什么不能只靠 context window

先把一个直觉误区捅破:context window 变大了,memory 问题就解决了。这话对 10% 的场景成立,对剩下 90% 是错的。

2024 年初我用 8K 窗口跑一个 code review agent,经常掉链子。后来切到 128K 窗口,平均能装下一个中型 PR 的所有文件 + 评论 + 几轮对话,我以为稳了。结果跑了三周发现问题:agent 会"变懒"。具体表现是,prompt 越长,模型对 prompt 末尾的指令遵守率越低,中段的细节召回率也掉。这个现象后来有论文研究过(Anthropic 2024 那篇关于 lost-in-the-middle 的研究就是讲这个),跟我观察的体感一致。

更深层的问题是:context window 是 working memory,不是 episodic memory。它没有"时间"的概念,没有"重要 vs 琐碎"的区分,也没有"哪些信息已经过期"的标记。把所有历史都塞进 prompt,就像一个人试图通过把日记本每一页都摊在桌上办公——信息都在,但你找不到。

所以我们需要一个独立的 memory 子系统。问题是:它应该长什么样?

## 四层 memory 是工程抽象,不是学术分类

2024 年我做第一个认真点的 agent 项目时,参考了 Generative Agents 那篇论文(Stanford 2023),里面提了 memory stream + reflection + retrieval 的架构。挺好,但搬到生产里发现不够用。后来我自己用一套四层模型来组织工程实现,这不是什么学术上的新东西,纯粹是为了让代码好写、bug 好查。

第一层是 working memory,就是当前这一轮对话的 context。这层最简单,就是一个 message list,system + user + assistant 交替堆。在 LangGraph 里就是 state 里的 messages 字段,在我们自己的框架里就是个 list of dict。容量上限就是 context window,通常 8K 到 200K tokens。

第二层是 short-term / session memory,跨度是单个会话(一次任务、一次对话、一个 PR review)。它要解决的是"用户在同一个任务里反复提到的事"。比如用户说"我刚才说的那个文件"——"那个文件"指什么?得在这次会话里记住。最简单的实现是个 in-memory dict,key 是 session_id,value 是结构化或者非结构化的状态。我们最早用 Redis,后来切到 Postgres 的一张 session_state 表,带 TTL,默认 24 小时过期。

第三层是 long-term memory,跨度是跨会话、跨用户(如果做 B 端)、跨时间。这才是真正难的部分。它要回答"这个用户上周提过的偏好""这个项目上个月定下来的架构决策"这类问题。

第四层是 shared / world memory,不是某个 agent 自己的,是所有 agent 或者整个系统共享的事实。比如"公司会议室预订规则",或者"这个 codebase 的架构文档摘要"。这层本质上是知识库,只是被当成了 memory 的一部分在用。

我之所以强调这是工程抽象,是因为学术圈会把它分成 declarative / procedural / episodic / semantic 之类的细类。我没那个耐心去严格区分,工程上能用就行。重要的不是分类多漂亮,而是每一层用什么存储、怎么检索、什么时候写入、多久过期。

## 长期 memory 才是真正难啃的骨头

短期那两层,坦白讲,KV 存储 + TTL 就够了。真正烧脑的是长期 memory。我从 2024 年到现在,大概经历了三个阶段的方案演进,每个阶段都对应一个我实际项目里遇到的具体问题。

第一阶段是 vector DB 崇拜期。2023 到 2024 年,大家一股脑扎进 RAG,觉得所有 memory 问题都能用 embedding + 向量检索解决。我也不例外。2024 年上半年做一个内部知识库助手,我把所有历史对话都 chunk 掉,塞进 Pinecone,每轮对话前 retrieve top 5。听着很美,跑起来两个问题。

第一个问题是 retrieval 噪声。我有次问 agent"上次我们讨论的部署流程",它返回的 top 5 里,第一条是三个月前关于另一个完全无关项目的闲聊,因为里面恰好出现了"部署"这个词。BM25 关键词 + dense embedding 混合检索,这块后来我花了不少时间调。

第二个问题更根本,就是"memory 不只是 recall"。我后来想明白一件事:用户说"上次讨论的部署流程",他要的不是任何一段提到"部署"的历史文本,而是一个高度浓缩的、已经处理过的结论。如果只做 retrieval,你每次都得让 LLM 重新消化一堆原始 chunk 才能给出答案,既慢又贵,还容易 hallucinate。

第二阶段开始,我加了一层 summarization。每次会话结束,让 LLM 把这轮对话总结成 200 字左右的事实陈述,存进 memory store。这其实就是 Generative Agents 那篇论文里的思路。效果立竿见影:同样的查询,response 准确率(我们内部人工评)从 0.61 涨到 0.78。

但 summarization 也有自己的问题。最坑的是"summarization 失真"。LLM 做总结时,会无意识地"对齐"——把模糊的细节改写成确定的事实,把小概率事件讲成"经常发生"。我们做 code review agent 时,有一次 agent 总结"用户偏好用 snake_case 命名",但其实用户只在一个特定场景提过一次,被总结成"偏好"就误导了后续所有交互。

所以到了 2024 年底,我开始认真用结构化 memory。具体的做法是:不存整段 summary,而是存 atomic facts。一条 memory 是一句话,主谓宾齐全,带 metadata(时间、来源 session、相关 entity、confidence)。比如不存"讨论了部署流程",而是存"项目 Alpha 部署流程:先用 GitHub Actions 跑 CI,再手动 ssh 到 prod 机器 pull 镜像,2024-12-10 由 session #abc123 提取"。

这套结构是 MemGPT 那篇论文(2024 年 6 月)给我的最大启发,虽然我实现得比论文简单很多。我没有做 virtual context management 那套复杂的 paging,就是朴素的:写时让 LLM 抽取 atomic facts 入库,读时根据 query 检索相关 facts。代码大概长这样:

```python
# 写 memory:会话结束后调一次
def extract_memories(messages: list[dict], user_id: str) -> list[MemoryItem]:
    prompt = f"""从以下对话中提取需要长期记住的事实。
每条事实一行,格式: [entity] [relation] [value] [confidence 0-1]
对话: {messages}
只提取关于用户偏好、项目决策、明确事实,不要提取临时状态。
"""
    response = llm.complete(prompt)
    return parse_facts(response, source_session=session_id, user_id=user_id)

# 读 memory:每轮对话前调一次
def recall_memories(query: str, user_id: str, top_k: 20) -> list[MemoryItem]:
    # 双路召回: dense embedding + 关键词 + 实体匹配
    dense_hits = vector_db.search(query, user_id=user_id, k=top_k)
    keyword_hits = bm25.search(query, user_id=user_id, k=top_k)
    # 合并去重,按 recency + relevance 加权
    return merge_and_rerank(dense_hits, keyword_hits, query)
```

这段代码看着简单,但背后是一堆调参。top_k 取多少、recency 的衰减系数怎么设、怎么去重(同一个 fact 在不同 session 被重复提取是常事)、confidence 低于多少就不返给 LLM 看,这些都不性感但决定质量。我可以老实说,我们这套 system 调到现在,内部 A/B test 显示长期 memory 让 user satisfaction 涨了 12 个百分点,但第一次跑通到稳定下来,花了差不多两个月。

## Episodic vs Semantic:别混着存

做长期 memory 一年后,我慢慢意识到一个事情:不同类型的 memory 应该有不一样的存储和检索方式,混在一起会出问题。

Semantic memory 是事实和知识。"用户的名字是张三""项目用 Python 3.11"——这种,内容相对稳定,不会因为时间变化而失效(除非事实本身被推翻)。检索时关心的是"是不是这个事实",对 recency 不太敏感。

Episodic memory 是事件和经历。"2024-11-15 用户让我重构了 auth 模块,我用了 JWT"——这种,价值在于它是一段经验,告诉你"在这个情境下,用户/系统做了 X"。检索时往往需要 recency 排序,而且常常需要带上下文(不只是 fact,还有"为什么做""结果怎样")。

我犯过的错是把两者都塞进同一个 vector store。结果呢?用户问"我之前让你做过什么类似的事吗",episodic memory 应该被召回(因为是在找"过往经验"),但它经常被 semantic 类型的 memory 挤掉,因为 semantic 的 chunk 经常更长、更"信息密集",embedding 距离更近。

2025 年初我们做了拆分,现在长期 memory 内部是分 table 的:

```python
class MemoryStore:
    def __init__(self):
        self.semantic = SemanticMemoryStore(backend=postgres_with_pgvector)
        self.episodic = EpisodicMemoryStore(backend=postgres_with_jsonb)
        self.procedural = ProceduralMemoryStore(backend=postgres)  # 习惯/技能

    def write(self, item: MemoryItem):
        if item.type == MemoryType.SEMANTIC:
            self.semantic.upsert(item)
        elif item.type == MemoryType.EPISODIC:
            self.episodic.upsert(item)
        # ...

    def recall(self, query, context):
        # 不同类型用不同检索策略
        sem = self.semantic.search(query, top_k=5)
        epi = self.episodic.search(query, top_k=3, recency_weight=0.4)
        # procedural 单独处理:只在检测到"重复任务"模式时才召回
        return merge(sem, epi, context)
```

Procedural memory 是我加的第三类,代表"习惯"和"技能",比如"这个用户每次都让我先写测试再写实现"、"这个项目跑 pytest 时要加 --cov"。它更新频率低,但一旦更新就影响所有相关交互。这块的灵感一部分来自心理学里的 procedural memory 定义,一部分是被用户反复抱怨"我每次都要说一遍用 snake_case"逼出来的。

这套分类不是圣经。我在更小的项目里就只分 semantic + episodic 两类,procedural 直接放在 system prompt 的一个 user_preferences 字段里,定期更新。规模决定了复杂度。

## Memory 的写入时机:别让 agent 自己写

我必须说一个反主流的观点:让 agent 自己在每轮对话后写 memory,听起来很"智能",但生产里基本是灾难。

2024 年中我做过一个实验,让 agent 在每轮对话后自己决定"这条要不要记下来"。结果就是 agent 变成了一个记笔记狂魔,几乎什么都写,一周后 memory store 里的 noise 大到 recall 没法用。另一个极端是 agent 学会了"偷懒",只在被显式提示时写 memory,结果漏掉了用户随口提的关键偏好。

我现在的做法是:把 memory 写入做成一个独立的、有节奏的 pipeline,而不是让执行任务的 agent 自己干。

具体是这样:
- 短 session(几轮对话):会话结束后异步跑一个 consolidation job,提取 facts,存库。
- 长 session(像 code review 这种跑几十分钟甚至几小时):每完成一个"阶段"就提取一次,而不是等结束。这样中途如果挂了,也能保住一部分。
- 显式信号:用户提供明确的"记住这个"指令时,这条 fact 走高优先级通道,带个 pinned=True 的标记,recall 时优先返。

这套做法跟 Anthropic 在 2024 年底发的 Building effective agents 那篇博客里的思路挺一致:把"长任务的状态管理"和"短期对话的 context"分开。我自己的补充是:memory 写入也应该跟任务执行解耦,交给一个更"无聊"但更可靠的 component。

我看过有人让 agent 在 system prompt 里写"你有一段 memory,使用 write_memory tool 来存储",然后让 agent 自己管。我对这套一直有保留意见,主要原因不在于它跑不通——其实在小规模场景下能跑——而是它的失败模式是静默的。agent 漏写一条 memory,你不会立刻知道,可能几天后才发现"咦我之前跟它说过这个怎么不记得"。这种 silent failure 在生产里最难查。

## 跟 context engineering 的接缝

这一章跟项目里的 [context-engineering 实战] 系列是直接相接的。说清楚一下边界:这一系列讲的是 memory 的**架构和概念**——分层、分类、检索策略;context-engineering 那一系列讲的是**怎么把 memory 跟 prompt 组装起来**——给 LLM 看什么、怎么压缩、怎么排序、怎么避免信息冲突。

举个具体例子。Memory 系统返回了 20 条相关 facts,但 context window 只够塞 5 条。怎么选?这就不是 memory 层该决定的事,是 context assembly 层的事。Memory 层应该老老实实返回所有相关的,带完整的 metadata(score、recency、type、pinned),让上层决定怎么裁剪。

我们在两个系列的接缝处定义了一个相对清晰的 interface:

```python
@dataclass
class MemoryItem:
    content: str
    type: MemoryType  # SEMANTIC / EPISODIC / PROCEDURAL
    score: float  # 跟 query 的相关度
    recency: datetime
    pinned: bool
    confidence: float
    source_session: str

def recall(query: str, user_id: str, limit: int = 50) -> list[MemoryItem]:
    """返回所有相关的 memory items,不做最后裁剪。"""
    ...
```

context-engineering 那边拿到这个 list 之后,会做:去重(同一个 fact 重复提取很常见)、压缩(把 20 条 facts 总结成一段 natural language)、排序(pinned > procedural > 经常访问的 semantic > episodic),最后才塞进 system prompt。

这两个东西如果混在一起做,就会变成一个几万能搞定的、谁也调不明白的超级大函数。分开之后,debug 起来快很多——memory 召回有问题就查 recall 函数,context 组装有问题就查 assembly 函数。

## 给工程师的两个具体建议

讲到这里,如果你是个要开始做 agent memory 的工程师,我会给两个建议。不是"应该考虑"那种软话,是"下周就动手"那种。

第一个:不管你做多小的项目,先把 short-term 和 long-term 分开。短期用 Redis 或者内存都行,长期用 Postgres 加个 pgvector 起步。哪怕你的"长期 memory"现在就只是一张表,也要从第一天就把它当一个独立的子系统来写接口。别把所有对话历史堆在 messages 数组里,等三个月后想加 memory 功能时发现数据全是 unstructured 的、没法回溯。Memory 的写入 schema 从一开始就要认真设计,后面改起来要命。

第二个:跑一个 memory eval,哪怕是最土的那种。准备 30 到 50 个真实的"用户曾经问过的问题",手动标注"应该召回哪些 memory",然后定期跑一遍算 recall@5、recall@10。我自己在 2024 年底被一件事教育过:当时我觉得 memory 系统跑得不错,后来才意识到是 eval 缺失导致我高估了真实表现。现在我们组里所有 memory 相关的改动都必须过这个 eval,包括 chunk size、embedding 模型选择、summarization prompt 改一个字都要过。这种"小作坊 eval"比没有强一百倍,工程上成本也就两三天搭起来。

Memory 这块接下来还会有不少变化,我比较期待的方向是 agent 自己维护一个 hierarchical summary tree(类似 MEMORYLLM 那篇 2024 年的工作),还有更结构化的"memory graph"而不是 flat list。但不管架构怎么变,核心问题就两个:什么东西值得记,怎么在对的时机把它捞出来。这两件事做好了,八成的 memory 问题就解决了。

下一章我们聊 [Planning: Agent 怎么想](./06-planning.md),看看 agent 怎么把一个模糊的目标拆成可执行的步骤,以及为什么 planning 经常是 agent 失败的第一站。