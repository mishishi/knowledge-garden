# 07. RAG: Agent 的外脑

我第一次见到 RAG 跑通是 2023 年初, 团队内部用 LangChain 0.0.x 拼了一个 demo, 喂了 200 页 PDF 进去, 问 "上一季度的营收是多少", 模型答对了。那一刻很兴奋——觉得外接知识这事成了。但接下来两周, 同样的 demo 换了个文档格式就崩了: chunk size 选不对, embedding 检索出来全是公司内部缩写, LLM 拿到一堆噪声就开始胡说。

三年过去, RAG 从一个 LangChain 里的小示例演化成了一套独立的技术体系。Naive RAG、Advanced RAG、Modular RAG、GraphRAG、Self-RAG、Agentic RAG、Corrective RAG…… 每隔几个月就有新名词冒出来, 但说实话, 90% 的项目用不到那么花哨。我 2024 年给一个法律科技团队做技术评估, 最后交付的方案里 RAG 模块不到 300 行代码, 没上 GraphRAG, 也没上 Self-RAG, 但 80% 的查询准确率提升就是这么来的。

这一章我想讲清楚三件事: RAG 这东西到底是什么、为什么 2024-2026 年它变了那么多、以及作为一个 agent 工程师, 我在真实项目里怎么选型和踩坑。我不会按论文的时间线讲, 那是综述该干的事; 我会按我踩坑的顺序讲。

## 当年那个朴素想法, 为什么跑不通

RAG 的原始想法朴素到几乎不值一提: 把文档切成块, 用 embedding 模型转成向量, 用户提问时检索最相关的块, 塞进 prompt 里让 LLM 回答。这个思路 Lewis 等人在 2020 年的论文里就提了, 但直到 2023 年 GPT-4 把上下文窗口撑到 32K 之后才开始大规模落地。

朴素 RAG 的代码长这样, 我相信每个 agent 工程师都写过类似的东西:

```python
from langchain.document_loaders import PyPDFLoader
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.chains import RetrievalQA

loader = PyPDFLoader("report.pdf")
docs = loader.load_and_split()
db = FAISS.from_documents(docs, OpenAIEmbeddings())
qa = RetrievalQA.from_chain_type(llm=chat, retriever=db.as_retriever())
print(qa.run("上季度营收是多少"))
```

这玩意儿能跑, 但问题在哪呢? 我 2024 年初接的一个项目, 客户是家医疗器械公司, 他们把 5000 份产品说明书塞进去, 提问 "A 型号的 B 配件兼容哪些主机", 系统返回了三段完全不相关的文字, LLM 强行拼出一个答案, 还是错的。

朴素的拆分方式按固定 token 数切, 一个章节的结尾被砍掉, 下一段的开头就没了上下文; embedding 用的是通用模型, "B 配件" 在产品说明书里是 "B-200 接口适配器", 通用模型根本不知道这是同一个东西; 检索只看 cosine 相似度, 拿到的 top-3 可能都是噪声; LLM 拿到噪声就开始编。

这就是 Advanced RAG 要解决的核心问题: 在索引、检索、生成三个阶段都做优化。索引阶段用语义切分而不是固定长度、用 hierarchical structure 保留文档层级、用 metadata 标注来源; 检索阶段用 hybrid search (BM25 + 向量)、用 re-ranking 模型 (Cohere Rerank / BGE Rerank) 把 top-K 先粗排再精排、用 query rewriting 让模型先改写问题再检索; 生成阶段用上下文压缩 (ContextualCompressionRetriever)、用 citation 强制让 LLM 标注引用来源。

我那医疗器械的项目最后怎么救回来的? 三板斧: 第一, 切文档改成按章节切, 而不是按 token 数; 第二, 检索用 BM25 + 向量混合, BM25 拿精确关键词, 向量拿语义相似; 第三, 答案生成前加了一个 "这文档够不够回答" 的判断步骤, 不够就拒答。三板斧做下来, 准确率从 38% 干到 78%。没用 GraphRAG, 没用 Self-RAG, 就是把朴素 RAG 的每个环节都收紧了一遍。

## Modular RAG: 当 RAG 变成乐高

2024 年中 Modular RAG 这个概念开始流行, 说白了就是 RAG 不再是一条直线 (query → retrieve → generate), 而是一个可以组装、可以加支路、可以循环的模块化系统。

我第一次认真用 Modular RAG 是给一家券商做合规问答系统, 这个场景有个特殊需求: 用户的问题常常需要先查询 A 文档里的某条规则, 再查询 B 文档里的具体案例, 最后才能给出答案。单次 retrieve 不够, 必须是 multi-hop 的。

Modular RAG 的思路就是把这个流程拆成几个可重用的模块: 一个 Router 决定走哪条路径 (查规则? 查案例? 都查?), 一个 Query Rewriter 改写子问题, 多个 Retriever 分别去不同数据源, 一个 Aggregator 把结果汇总, 一个 Generator 最终生成答案。每个模块可以独立替换和优化。

代码层面, LangChain 的 LCEL 和 LlamaIndex 的 QueryEngine 都在往这个方向走, 但说实话, 我自己更喜欢用 AutoGen 或者直接写 orchestration 代码, 因为 RAG 的复杂流程经常要带状态机, 框架反而碍事。

举个具体的例子, multi-hop retrieval 大概长这样:

```python
def multi_hop_rag(question, max_hops=3):
    context = []
    sub_question = question
    for hop in range(max_hops):
        docs = retriever.search(sub_question, top_k=5)
        context.extend(docs)
        # 让 LLM 判断还需不需要继续查
        needs_more = llm.invoke(
            f"基于已有上下文, 这个问题还需要查询更多信息吗? "
            f"问题: {question}\n已有上下文: {format(context)}"
        )
        if "不需要" in needs_more:
            break
        # 生成下一跳的子问题
        sub_question = llm.invoke(
            f"基于已有上下文, 下一步该查什么? "
            f"原问题: {question}\n已有上下文: {format(context)}"
        )
    return llm.invoke(f"基于以下上下文回答问题: {format(context)}\n问题: {question}")
```

这代码写得糙, 真实项目里要加很多细节 (比如怎么判断 needs_more 是 LLM 的幻觉、怎么控制 context 长度), 但骨架就是这么回事。

Modular RAG 真正让我觉得值, 是它把 "调试 RAG" 这件事从玄学变成了工程。你可以独立测试 Retriever 的召回率、独立测试 Rewriter 的改写质量、独立测试 Generator 的幻觉率。我们组当时做了一套 evals, 把每个模块单独打分, 这才能发现到底是哪个环节拉胯——更多 evals 细节在 AI Evals 那本书里展开讲。

跟 GraphRAG 和 Self-RAG 比起来, Modular RAG 的优势是 "工程可控性": 你不用押注一个新范式, 就能拿到明显的提升。代价是复杂度上升, 一个原本 200 行的 RAG 系统可能膨胀到 2000 行, 维护成本和出 bug 的概率都涨。

## GraphRAG 与 Self-RAG: 两个极端

GraphRAG 是微软 2024 年中推出来的方案, 一夜之间火遍全网。它的核心想法是把文档先抽成知识图谱 (实体 + 关系), 然后在图上做检索和推理。优势是能处理 "跨文档关系" 类问题——比如 "A 公司的供应商里有哪些是和 B 公司有关联的", 这种查询纯向量检索基本无解, 图谱查询几行 Cypher 就搞定。

但 GraphRAG 的工程门槛是真高。我们组 2024 年底试过在一个金融研报场景里上 GraphRAG, 折腾了六周才勉强跑通。问题在哪? 实体抽取这一步就够你喝一壶: LLM 抽取实体有 5-10% 的错误率, 实体对齐 (合并 "Apple"、"苹果公司"、"AAPL" 为同一个节点) 又是一道坎, 关系抽取更别提了, 经常给你抽出一堆莫名其妙的关系。最后算账, GraphRAG 的索引成本是普通 RAG 的 10-20 倍 (因为要先抽实体再建图), 检索延迟也明显高。

我的判断是: GraphRAG 适合那种数据规模有限 (几千到几万文档)、查询明确需要关系推理、且团队有图数据库经验的场景。普通业务问答、客服助手、文档摘要这些, 别上 GraphRAG, 性价比极低。

Self-RAG 是另一个极端, 它的核心是让 LLM 自己判断 "需不需要检索"、"检索到的内容可不可信"、"这个答案能不能用", 把这些判断 token 嵌入到生成过程里。听起来很美, 但我自己的实验里, Self-RAG 的成本是普通 RAG 的 3-5 倍 (因为每个 token 都要做额外判断), 提升的幅度却很难讲——在我们组的内部 benchmark 上, Self-RAG 比 Advanced RAG 平均只好了 3-5 个百分点, 个别场景甚至不如 Advanced RAG。

2025 年初我们跟一个硅谷团队对过方案, 他们就死活要上 Self-RAG, 觉得不酷; 我劝了半天没用, 最后交付出来效果确实没达到预期。所以我的建议是: Self-RAG 适合那种错误代价极高的场景 (比如医疗、法律建议), 普通场景别追这个时髦。

## 我怎么选: 一张简化的决策树

讲了这么多方案, 工程师最关心的是 "我手上这个项目该用哪个"。我不喜欢用表格, 用叙述的方式讲我的决策逻辑。

第一, 先评估你的数据规模和数据特性。几千份文档、查询主要是事实性问题 (FAQ / 知识库查询)、不需要复杂推理——上 Advanced RAG 就够了, 这是 80% 的项目的情况。数据规模上万、查询涉及跨文档关系、且关系是关键价值——考虑 GraphRAG。数据规模很小但对准确率要求极高、且愿意付算力成本——考虑 Self-RAG 或者 Modular RAG 加 Self-RAG 的混合方案。

第二, 评估你的工程能力。如果团队没人熟悉 Neo4j 或者图数据库, 别碰 GraphRAG, 那个 entity alignment 的坑够你踩三个月的。如果团队对 LLM 的 prompt 工程不熟, 别碰 Self-RAG, 你会让 LLM 自己陷入决策循环。

第三, 评估你的成本预算。朴素的 RAG 一次查询大概 $0.001-0.01 (假设 5 个 chunk 进 prompt); Advanced RAG 加个 reranker 大概 $0.01-0.03; GraphRAG 因为索引成本高, 单次查询摊销下来可能到 $0.05-0.10; Self-RAG 至少 $0.03-0.05。这些数字看着不大, 乘以 QPS 就是实打实的钱。

我个人在 2025 年交付的项目里, 大概 60% 是 Advanced RAG (加了 rerank + query rewrite + metadata filtering), 25% 是 Modular RAG (multi-hop 场景), 10% 是朴素 RAG (内部 demo 或者预算极小的场景), 只有 5% 用到了 GraphRAG 或者 Self-RAG。

## 给工程师的两个具体建议

第一, 别追新, 先把朴素 RAG 调到位。我见过太多项目, 一上来就要上 GraphRAG, 结果连 chunk size 怎么选都没想清楚。先把朴素的 RAG 调好: 切分策略选对、retrieval top_k 调对、加个 reranker、看下召回率能不能上 80%。如果这些做到了还不行, 再考虑升级方案。Advanced RAG 听起来 fancy, 其实就是朴素 RAG 的每个环节都做一次小优化, 没必要当成一个独立的 "阶段" 来对待。

第二, 把 RAG 当成系统来看, 而不是当成 LLM 的一个 wrapper。我最早做 RAG 也是 "embedding 一下, retrieve 一下, generate 一下" 三步走, 后来吃了几次亏才明白: RAG 是一个有状态、有缓存、有版本管理、有可观测性的系统。你需要缓存高频查询 (我一般用 Redis 存 30 天), 你需要给文档打版本号 (不然改了一个错别字你都不知道), 你需要记录每次检索的 recall 和 precision (这跟 context-engineering 系列里的可观测性方法是一脉相承的)。

最后, 关于 RAG 在 agent 体系里的定位: 它本质上是 agent 的一个 "外脑", 但不是唯一的脑。agent 还可以调工具 (tool use)、可以走 multi-agent 协作、可以用 working memory 暂存上下文。RAG 解决的是 "长期事实性知识的检索", 跟 short-term memory、tool use 是互补关系, 不是替代关系。下一章讲 multi-agent, 那个是 agent 之间怎么协作, 但每个 agent 内部大概率还是带着 RAG 模块的。

我自己在做 agent 架构设计的时候, RAG 模块一般作为一个 "tool" 暴露给 agent, agent 自己决定什么时候去查。这样比把 RAG 硬塞进 prompt 灵活得多, agent 可以根据问题复杂度决定查几次、查哪里。这块的具体写法会在 multi-agent 那章展开。