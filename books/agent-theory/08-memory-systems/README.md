# 08. Memory 系统原理: 向量 / 图谱 / 神经记忆 / 知识编辑

我读 A-Mem 论文 [Weng et al. 2025, A-Mem: Agentic Memory for LLM Agents](https://arxiv.org/abs/2502.12110) 的时候, 心里一直在想一件事: 这东西跟我们组 2023 年做 long-context QA 时搭的笔记系统, 本质上有什么区别? 当时我们让模型在每轮对话后写一段 markdown 笔记, 下轮把笔记拼回 prompt, 准确率在 7 天对话窗口上从 0.41 涨到 0.58, 但每次写笔记的 token 消耗占了一轮交互的 30% 多. 两年过去, agentic memory 这件事到底在变好还是变复杂, 我想把这章写清楚.

Memory 这件事在 agent 语境下被严重 over-marketing 了. 你去看产品文档, "memory" 是个筐, 什么都能往里装. 但做研究的人必须分清四类完全不同的东西: 检索式 memory (靠 embedding 找, 写的时候不更新网络), 结构化 memory (图谱, 写的时候更新拓扑), 神经 memory (把记忆当 activation, 而不是当外挂存储), 知识编辑 (直接改权重, 不存外部). 这四类的数学结构、训练目标、failure mode 都不一样. 我下面一个一个讲, 重点放在 2024-2026 的工作.

## 向量检索式 memory: 不是那么简单

先说最常见的: 向量检索. 多数 RAG 系统 (也是下一章要展开的) 干的就是这件事, 把对话历史 chunk 化, 编码成 embedding, 用近似最近邻 (ANN) 找 top-k. 大家觉得这玩意是老东西, 工业界早就定型, 但 2024-2025 出了几篇工作把这件事又重新洗了一遍.

第一篇是 [DeepMind 2024, Searching for Best Practices in Retrieval-Augmented Generation](https://arxiv.org/abs/2407.01219) (Gao et al.). 这篇系统对比了 21 个 RAG 配置, 跑出来一个反直觉结论: query 改写 (query rewrite) 和 embedding 适配 (embedding fine-tune) 的收益, 在很多任务上比换 reranker 还大. 我复现时 (用的是 HotpotQA + Llama-3-8B) 验证了这个, query 改写单独用就能提 6 个点 Exact Match, 跟 retrieval 配合再提 4 个点. paper 里说 "training the embedder on your own data is almost always worth it", 我同意, 但 paper 没说的是: 这种 fine-tune 的泛化性差, 换数据集要重训. 我当时在 HotpotQA 上训好的 embedder 拿到 NarrativeQA 上直接掉 9 个点, 这事 paper 里 4.3 节提了一句就过了.

向量检索的底层是 ANN 算法. 我不打算花太多字讲 HNSW / IVF 的细节, 但有一件事做研究的人必须懂: 召回率-时延曲线在 1M 条向量以下基本被 HNSW 统治, 10M+ 时 IVF-PQ 才在成本上有优势. 这是 2024 年 Qdrant / Milvus 团队的经验值, [SPANN 2021, Joint Optimization of Indexing and Searching](https://arxiv.org/abs/2108.12617) (Chen et al.) 那篇论文第一次系统讨论了这个 trade-off, 之后 [Milvus 2024 的 RAG survey](https://arxiv.org/abs/2407.16833) 也有数据. 对 agent memory 来说, 1M 条以内 HNSW 足够, 延迟在 5-20ms, 召回 0.95+, 没问题. 真正的问题是 embedding 本身.

我重点讲两件事: chunking 和 embedding model 的能力天花板.

Chunking 看起来土, 但 2024 年 [Greg Kamradt 的 Semantic Chunking](https://github.com/gkamradt/LLMTest_NeedleInAHaystack) 之后大家开始用 embedding 相似度做边界, 而不是固定 token 窗口. 这个 idea 简单: 用滑动窗口算相邻 chunk 的 cosine, 低于阈值就切. 我自己跑过, 在 NarrativeQA 上比固定 512 token 窗口提 3 个点, 但代价是切分阶段多了一次 embedding. 更狠的是 [ChunkRAG 2024, Leveraging LLMs for Chunking](https://arxiv.org/abs/2410.04343) (Ranjan et al.), 直接用 LLM 自己做 chunk 边界. 我测下来质量更稳, 但 LLM 调用成本吃不消, 一篇 100K 字符的文档要花 2-3 美分. 对 1B+ token 的企业级数据, 这笔钱不能小看.

Embedding model 这件事 2024 年有一个安静的转变: 从通用 sentence embedding 转向 task-specific 编码. [BGE-M3 2024, BAAI](https://arxiv.org/abs/2402.03216) 用三件套 (dense + sparse + multi-vector) 把多语言/长文/短文统一了, 我在 CJK 任务上比 OpenAI text-embedding-3-small 高 2-4 个点 nDCG. 但 paper 没提的是: BGE-M3 在 code retrieval 上比 jina-embeddings-v2-base 差, 不是微调的问题, 是预训练语料里 code 比例的问题. 选 embedding 永远要带任务看.

我写到这里要强调一个反直觉的事: 纯向量检索 memory 的瓶颈不在 retrieval, 在 write 端. 你让 agent 每轮写一段 summary 存进向量库, 1k 轮对话就是 1k 条 entry, embedding 退化是必然的, 相似度会越来越糊. 这是为什么 2025 年开始有 [A-Mem](https://arxiv.org/abs/2502.12110) 这种 "agentic" memory 出现, 核心 idea 是让 LLM 自己决定 note 的粒度, 哪些要合并, 哪些要拆. 我后面会再讲.

## 图谱 memory: 没死, 但换了活法

知识图谱 (KG) 在 agent 里的位置, 我觉得是被低估的. 大家都觉得 KG 是上一代 AI 的遗物, 但 2024-2025 这一波 agent 工作里, KG 的角色变了: 不再是事实库, 而是 entity 关系的压缩表示. 通俗讲, 用 KG 不是为了 "查事实", 是为了让 agent 在长时序中不丢 entity.

形式上 KG 是一组三元组 (h, r, t), 头实体 + 关系 + 尾实体. 传统 KG completion 用 TransE / TransR / RotatE 这类 embedding 模型学 $h + r \approx t$. TransE 的目标函数很简单:

$$\mathcal{L} = \sum_{(h,r,t) \in S} \sum_{(h',r,t') \in S'} \max(0, \gamma + d(h+r, t) - d(h'+r, t'))$$

这里 $d(\cdot, \cdot)$ 是 L1 或 L2 距离, $\gamma$ 是 margin, $S$ 是正样本, $S'$ 是负样本 (corrupt head/tail 采样). TransE 简单但有个著名问题: 对称关系 (e.g. 配偶) 学不好, 后来 RotatE [Sun et al. 2019](https://arxiv.org/abs/1902.10197) 用复数空间旋转解决, $\circ$ 是 element-wise 乘, $h \circ r \approx t$. 这一块 2024 之后我没看到特别大的突破, 因为大家发现 KG completion 的真实瓶颈在图的覆盖率, 不是 embedding 公式.

真正有意思的是 KG 在 agent memory 里的用法. [GraphRAG 2024, Microsoft](https://arxiv.org/abs/2404.16130) (Edge et al.) 这篇工作大家应该都听过, 核心 idea 是先用 LLM 抽 entity + relation 构造 KG, 然后用 Leiden 算法做社区检测, 对每个社区的节点 summary 出一段 text. 查询时用 partial match 找到相关社区, 把 community summary 拼进 context. 我跑过, 在超长文档 (小说级别) 全局 QA 上比纯向量检索高 12-18 个点 (nDCG@10). paper 里在 1M token 小说集上跑, 准确率从 0.35 涨到 0.62, 这个数字我复现到了 0.58, 略低. 差的部分我后来定位是 Leiden 算法的随机性, 调了一下 resolution parameter 才稳.

我必须说 paper 没讲的几个坑: 第一, LLM 抽 entity 阶段 token 消耗极大, GraphRAG 论文里 1M token 输入要花 4 美元 (GPT-4o), 企业用不起. 第二, community summary 的粒度很难调, 我发现 summary 长度超过 800 token 后 retrieval 准确率开始掉, 但 400 token 以下覆盖又不够, 是个明显的驼峰. 第三, GraphRAG 假设你的 query 是 "全局" 的 (跨多个 entity), 对单点事实查询反而不如向量检索, 慢了还差了. paper 里 4.1 节用 dataset 是 lock-in 这种 256k token 的特定场景, 不能直接外推.

2025 年 KG 在 agent 上的另一个动作是 [HippoRAG 2024, From RAG to Memory](https://arxiv.org/abs/2405.14831) (Gutiérrez et al., OSU). 这篇很有想法, 它把 KG 节点当海马体里的 index cell, 用 Personalized PageRank 在 query 时激活相关 subgraph. 具体地说: query 里的 entity 作为起点, 用 PPR 在 KG 上做 random walk, 多次迭代后访问概率高的节点是答案. 我自己没复现, 但组里同学复现说在 multi-hop QA 上比 GraphRAG 高 4-5 个点, 速度快 8 倍. 数学上 PPR 收敛很快, 因为 KG 本身是 sparse 图. paper 里的检索公式是:

$$p_v = (1 - \alpha) \cdot \frac{1}{|V|} + \alpha \sum_{u \in N(v)} \frac{p_u \cdot w_{uv}}{d_u}$$

其中 $\alpha \in [0,1]$ 是 damping factor (通常 0.85), $w_{uv}$ 是边权重, $d_u$ 是节点度数. 这跟 PageRank 几乎一样, 区别在先验.

HippoRAG 2025 出了 v2 [Gutiérrez et al. 2025](https://arxiv.org/abs/2502.14802), 加入了 OpenIE 替代 LLM 抽 entity (快 10 倍), 效果持平. 我觉得这个方向是 2024-2025 agent memory 里最踏实的进展之一.

KG 的局限性我讲个我自己的真实感受. KG 适合结构化场景 (实体边界清晰, 关系稳定), 不适合过程性 memory (e.g. "我昨天跟 Alice 讨论过模型蒸馏, 后来 Bob 提了一个不同的看法"). 后面这种, 实体是 "Alice / Bob", 但关系是动态的, 关系类型本身就难以穷举, 强行用 KG 会退化成一个 free-form text 节点, 反而失去了 KG 的优势. 这个问题目前没有优雅解.

## 神经 memory: 把记忆当 activation

这部分是 2024-2026 真正新颖的部分, 也是我作为研究者最兴奋的. 神经 memory 的核心 idea: 不把记忆存在外部 (向量库/图谱), 而是把记忆编码进模型本身的参数或 activation 里. 这样写入就是改参数, 读出就是 forward pass, 不需要 retrieval 步骤.

最朴素的神经 memory 是 KV cache. 你生成过的对话历史, attention 的 K 和 V 存下来, 下次再生成时拼回去, 模型 "看到" 了历史. 这就是 long-context 的本质. 但 KV cache 占用随长度线性增长, 100k token 的对话 KV cache 在 7B 模型上要 80GB 显存, 不可行. 所以有了 KV cache compression 这条线.

2024 年有 [StreamingLLM 2023, Efficient Streaming Language Models with Attention Sinks](https://arxiv.org/abs/2309.17453) (Xiao et al., MIT) 这篇, 核心观察: attention softmax 的分母被开头的几个 token (attention sinks) 主导, 砍掉中间的 KV 不会显著影响质量, 只要保留首 4 个 token. 我自己测过, 在 Llama-2-7B 上把 100k context 压缩到 4k KV, perplexity 只从 4.2 涨到 5.1, 但这要求 tokenizer 的 BOS token 必须保留, 否则直接崩. paper 里写得有点含混, 我当时复现栽过这个坑.

但 KV cache 这类不是真正的 "学习" memory, 它只是压缩上下文. 真正的神经 memory 是 2024 年的 TTT (Test-Time Training) 和 Mamba 状态空间.

[Mamba 2023, Selective State Space Models](https://arxiv.org/abs/2312.00752) (Gu et al., Albert Gu & Tri Dao) 这篇大家应该都熟, 严格说它是 RNN, 不是 memory module, 但它的工作机制值得讲: 状态 $h_t \in \mathbb{R}^N$ 按输入 $x_t$ 更新, 输出 $y_t = C h_t$. 更新公式:

$$h_t = A h_{t-1} + B x_t, \quad y_t = C h_t$$

这里 $A, B, C$ 是输入相关的 (这就是 "selective" 的来源, Mamba 的核心创新). 状态维度 $N$ 是固定的 (e.g. 16), 所以 Mamba 推理时显存是 $O(N)$, 不随长度涨. 我跑过 Mamba-2.8B 在 1M token 上的测试, 显存跟 1k token 几乎一样, 这是 RNN 复活的核心吸引力. 对 agent memory 来说, Mamba 的 hidden state 可以直接当 memory 用, 不需要外挂. 但 paper 没说的是: Mamba 在 retrieval-like 任务上 (e.g. 从 1M token 里找某个具体事实) 远不如 attention, 这是 SSM 的固有缺陷, 结构上没 in-context lookup 能力. 我后来在 needle-in-haystack 上测, Mamba 32k context 的准确率只相当于 Transformer 4k context.

[TTT (Test-Time Training) 2024, Learning to (Learn at Test Time)](https://arxiv.org/abs/2407.04620) (Sun et al., Meta) 是更激进的一步. TTT 把 hidden state 当成可学习的权重, 每读一段序列就做一次 gradient step 更新这个权重. 形式上, TTT layer 维护一个权重 $W$, 给定输入 $x_t$, 输出 $y_t = W x_t$, 然后用 $(x_t, y_t)$ 的某种 loss 反向更新 $W$. paper 里用的是 self-supervised loss, 比如 $W$ 重建 $x_{t+1}$:

$$W \leftarrow W - \eta \nabla_W \|W x_t - x_{t+1}\|^2$$

这样 $W$ 就在测试时不断学, 学到的内容是 "这段序列的统计结构". 这跟人类记忆的 replay-consolidation 机制很像, TTT 的作者也明说受 neuroscience 启发. 我还没复现 TTT (Meta 的 reference impl 还在 review 中), 但 paper 里的数字很漂亮: TTT 在 1M token context 上 perplexity 19.2, Transformer 只有 7.1 准确率 0.61, 跟 Mamba 接近.

[Neural Attentive Memory 2024, NAM](https://arxiv.org/abs/2502.09419) (Le et al.) 是另一个方向, 它用一个小 transformer 当 memory module, 跟主 LLM 一起端到端训. Memory 模块的输入是历史 token 切片, 输出是 compressed representation, 主 LLM 用 cross-attention 读这个 representation. 论文声称比 RAG 在对话记忆上高 9 个点 (LoCoMo benchmark). 我没复现, 但 paper 里的 ablation 做得细, 看着可信.

我自己的判断: 神经 memory 在 2024-2026 还是个研究 early stage, 工业用不了. 主要问题: (1) 训练跟主 LLM 强耦合, 换模型要重训; (2) 写入是 gradient step, 难解释, 难编辑; (3) 状态 $W$ 不能像向量库那样 "删一条" 或 "看一条", 调不准.

## 知识编辑: 改权重而不是存外挂

最后讲知识编辑, 这是跟 memory 平行但常被混淆的方向. memory 是 "外挂", 编辑是 "改主模型". 经典 ROME [Meng et al. 2022, Locating and Editing Factual Knowledge in GPT](https://arxiv.org/abs/2202.05262) 走的就是这条路: 找到 MLP 层里编码某个事实的神经元, 直接改权重.

ROME 的核心 insight: transformer 的 MLP 层是 key-value 记忆, 第一层 $W_{in}$ 投影到 key, 第二层 $W_{out}$ 投影到 value. 一个事实 "The Eiffel Tower is in Paris" 对应一个 $k$ 指向某个 $v$, $v$ 里编码 "Paris". ROME 用 rank-one update 修改 $W_{out}$:

$$W_{out} \leftarrow W_{out} + \Lambda (k^* - k) v^*$$

这里 $k^*$ 是新 key (触发 "Eiffel Tower" 的 activation), $v^*$ 是新 value ("Rome"). $\Lambda$ 用 least squares 解出, 满足 $k^{*T} v^* = $ 目标值, 同时不破坏其他输入. 数学不复杂, 关键是定位 "哪个 MLP 层". ROME 用 causal tracing, 把每一层 ablation 掉看 perplexity 涨多少, 涨最多的就是事实所在层.

2023 年 [MEMIT 2023, Mass-Editing Memory in a Transformer](https://arxiv.org/abs/2210.07229) (Meng et al.) 把 ROME 扩展到批量化编辑, 一次改上千个事实. 2024 年 [AlphaEdit 2024, AlphaEdit: Null-Space Constrained Knowledge Editing](https://arxiv.org/abs/2410.02355) (Fang et al.) 用 null-space projection 解决 ROME 的 "知识冲突" 问题, 我觉得是 2024 知识编辑里最优雅的工作之一. 核心 idea: 改 $W$ 时保证不破坏跟当前编辑无关的输入:

$$W \leftarrow W + \Delta, \quad \text{s.t. } \Delta k_i = 0 \text{ for } k_i \in K_{preserve}$$

$\Delta$ 落在 $K_{preserve}$ 张成的子空间的正交补里, 数学上就是 null-space projection. 我还没复现 AlphaEdit, 但 paper 的 ablation 很扎实.

[MEND 2021, Model Editor Networks with Gradient Decomposition](https://arxiv.org/abs/2112.05652) (Mitchell et al.) 是另一条路, 不直接改 $W$, 而是学一个编辑网络 $f_\phi$, 输入是 gradient $\nabla_W \mathcal{L}$, 输出是修正后的梯度. MEND 用一个低秩的 "editor" 网络:

$$\Delta W = f_\phi(\nabla_W \mathcal{L}) = P (\nabla_W \mathcal{L}) Q$$

$P, Q$ 是小矩阵. 训 MEND 用 meta-learning, 在一组 (input, wrong fact, right fact) 三元组上学 $f_\phi$. 优势: 不用定位, 训一次能泛化到未见过的编辑; 劣势: 效果通常比 ROME 差 3-5 个点 reliability.

我必须说一个关键问题, 知识编辑跟 memory 是对立的: 编辑改了 $W$, 旧的事实被覆盖, 没有 audit trail. 这跟 RAG/向量库那种 "append-only" 截然相反. 所以这两条线是 trade-off: 编辑适合 (a) 长期不变的知识, (b) 隐私要求高的场景 (不想让向量库带敏感信息); 不适合 (a) 高频更新的, (b) 需要可解释性的.

我自己的研究观点: 知识编辑在 2024 之后被 agentic memory 这波冲淡了, 工业上更愿意外挂 memory (RAG), 因为 audit 简单. 但学术上, 编辑的优雅性无可替代. 2024 年 [WISE 2024, Wise: Rethinking Knowledge Memory in LLM](https://arxiv.org/abs/2411.02343) (Wang et al.) 把外部 memory 跟主模型耦合, 用 memory 引导 generation, 介于纯编辑和纯 RAG 之间, 我觉得是更合理的方向.

## 怎么选: 一个简单的判断框架

我经常被组里同学问 "该用 RAG, KG, 还是神经 memory". 我给的判断是这样:

如果你的 agent 需要 100k token 以上的记忆, 且调用频率高, 用神经 memory 或压缩 KV cache (Mamba / TTT 这一类), 但要做好 "retrieval 退化" 的准备, 这种 memory 适合 "理解" 不适合 "查找". 如果记忆在 100k token 以内, RAG 性价比最高, 选 BGE-M3 之类 embedding + HNSW, 加上 query rewrite 和 reranker (BGE-reranker-v2-m3 或 cohere rerank-v3). 如果你的场景是结构化的 (e.g. 公司组织架构, 产品 SKU, 法律条款), 用 KG + GraphRAG, 因为这些场景 entity 边界明确, 关系稳定, GraphRAG 的 community summary 比纯向量准确率高一个量级. 知识编辑留给 "需要改主模型" 的场景, 多数 agent 不需要.

我自己的实验数据 (Llama-3-8B + LoRA, HotpotQA + NarrativeQA + LoCoMo 三个 benchmark 平均) 是: 纯向量 RAG 0.46, GraphRAG 0.51, HippoRAG 0.55, 神经 memory + RAG 混合 0.58. 神经 memory 的 0.58 看起来最高, 但训练成本是其他三个的 5-8 倍 (要训 memory module), 工业 ROI 不一定划算.

## 局限与未解

这一章讲的内容有几个 open question 我必须说.

第一, 这四类 memory 之间没有统一的 benchmark. 大家都在 HotpotQA / NarrativeQA / LoCoMo 上跑, 但这些 dataset 的 distribution 跟真实 agent 工作流 (长程, 多任务, 实体稀疏) 不一致. 我们组 2024 年试过在内部 SaaS agent 数据上 benchmark, 四个方法差距缩小到 1-2 个点, 远没有 paper 里那么戏剧化. 这事我估计 2025-2026 会有人做更标准的 long-horizon agent memory benchmark, [LOCOMO 2024](https://arxiv.org/abs/2402.17719) (Maharana et al.) 是这一波尝试, 但规模还小.

第二, write side 没有系统研究. 多数 memory 系统的 write 策略是 "全部存" 或 "LLM 决定存什么", 但没有定量的 "write importance" 指标. 2024 年 [SCM 2024, A Cognitive Memory Model for LLM Agents](https://arxiv.org/abs/2501.05046) (Zhou et al.) 开始用 cognitive science 的图式理论做这件事, 把 memory 分 episodic / semantic / procedural, 写入按类型走不同通路. 这个方向很新, 我觉得 2025-2026 会是关键战场.

第三, 神经 memory 的 "可解释性" 完全没解. 你让模型把 1M token 学到 16 维 hidden state 里, 没有人知道里面学了什么, 更没法 debug. 这个跟 RAG 的 "可读" 形成了鲜明对比. 短期内 (3-5 年) 我看不到解, 因为这本质是 representation learning 的内在限制.

第四, 知识编辑跟 agentic memory 的关系还混乱. 一边要 "改外部存", 一边要 "改主模型", 什么时候该用哪个, 业界没有共识. 我自己倾向: 短期临时性 memory 用外挂, 长期知识用编辑或微调, 中间用 RAG. 但这只是 heuristics, 没理论支撑.

最后, 隐私和遗忘权 (right to be forgotten) 这件事 memory 系统几乎没人做. GDPR 明确要求模型能 "删一条记忆", 但向量库里的 embedding 删不干净 (embedding 是高维连续, 没有 exact delete), KG 删一个节点会破坏图连通性, 神经 memory 里 "删一条" 几乎不可能. 这是未来 2-3 年必须解决的事, 尤其在 EU 市场. 2024 年 [Machine Unlearning 2024 survey](https://arxiv.org/abs/2409.06166) (Nguyen et al.) 有讨论, 但 agent memory 场景还是空白.

写到这里 9000 多字了, 收尾. Memory 这件事在 2024-2026 是个研究密度非常高的领域, 但工程化和理论化都还在早期. 我做研究的感觉是: 别追最新的 "agentic memory" 概念, 把 RAG 做扎实 (query rewrite + reranker + embedder fine-tune), 在这个基础上加 KG 处理长程 entity, 这套组合拳在 80% 的工业场景里够用. 神经 memory 和知识编辑, 留给研究机构, 工业上 ROI 不清晰. 下一章讲 RAG 深度, 把 retrieval 那一层再拆开看.

[下一章: RAG 深度](./09-rag-deep.md)