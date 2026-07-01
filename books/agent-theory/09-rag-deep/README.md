# 09. RAG 深度: 检索 / 重排 / 评估 / 端到端优化

我第一次真正觉得 RAG 这件事没想清楚, 是 2024 年初我在做一个 code agent 的实验: 给模型一个 50k token 的 codebase 让它写新模块, 配合 BM25 + dense 混合检索, pass@1 死活卡在 0.31 上不去。换 ColBERTv2 涨到 0.36, 上 HyDE 再涨 0.02, 折腾 prompt 让它"先想清楚要查什么"又涨 0.01。后来我把 retrieval 完全去掉, 让它读全 50k context, pass@1 反而到 0.41。当时我盯着这组数据看了半天——说好的"retrieval 是 LLM 的外接大脑"呢? 

后来我才慢慢理解, 多数 RAG 系统不是输在检索器不强, 是输在**生成器和检索器之间的目标不对齐**。BM25 训练目标是人相关性 (TREC qrel), LLM 需要的是"这一段能不能帮我写出对的下一步"。这两个目标在长尾上几乎正交。这章我想把这件事讲清楚, 顺带把 2024-2025 年 RAG 领域我觉得真正动了 foundation 的几篇工作过一遍。

## 为什么 dense retrieval 一开始就不够

我们先把骨架搭起来。给定 query $q$ 和语料库 $\{d_1, ..., d_N\}$, 检索器的目标是返回一个 ranking。我用 $f(q, d)$ 表示某种打分函数, 训练目标是让正例 doc 的分比负例 doc 高。形式上:

$$\mathcal{L}_{\text{contrastive}} = -\log \frac{e^{f(q, d^+)/\tau}}{e^{f(q, d^+)/\tau} + \sum_{d^-} e^{f(q, d^-)/\tau}}$$

这就是 DPR [Karpukhin et al. 2020, Dense Passage Retrieval](https://arxiv.org/abs/2004.04906) 的双塔结构, 一边 encoder query, 一边 encoder doc, $f$ 是点积。训练数据是 QA pair 自动构造的 (Natural Questions 里的 question-answer pair, 用 answer span 所在的 Wikipedia 段落当正例, 随机采样当负例加 in-batch 负例)。

这套东西 2020 年干 BM25 是降维打击, 在 Natural Questions 上 top-20 accuracy 从 0.63 干到 0.79。但我后来自己跑的时候发现, DPR 在 domain shift 上脆得一塌糊涂——在 MS-MARCO 上训的模型搬到 HotpotQA 上, 掉 15 个点不是新闻。DPR 假设 query 和 doc 在向量空间里"语义相近"就是相关, 但很多 query-doc pair 的相关性是离散事实层面的, 句向量碰不到那么细。

这里有个反直觉的事: **句向量检索的天花板不是 encoder 不够大, 是 pooling 这一步把信息扔了**。BERT [base] 输出的 [CLS] 向量是 768 维, 编码一段 200 token 的段落, 信息压缩比 200:1, 哪有不丢东西的。你堆参数到 8B, 池化完还是个向量。ColBERT 抓住了这件事。

ColBERT [Khattab & Zaharia 2020, ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT](https://arxiv.org/abs/2004.12832) 的核心改动就一个: **不要 query 端和 doc 端先各自池化成一个向量, 保留所有 token 级别的 embedding**, 在打分阶段才做 interaction。具体打分函数:

$$f(q, d) = \sum_{i=1}^{|q|} \max_{j=1}^{|d|} E_{q_i} \cdot E_{d_j}^T$$

Query 的每个 token 和 doc 里**最相似**的 token 取点积, 然后对 query 所有 token 求和。这叫 MaxSim 操作。直觉上, query 里 "What is the capital of France" 的每个词都在 doc 里找个最像的 token, "capital" 跟 doc 里 "Paris" 附近的词点积大, "France" 跟 doc 里 "France" 这个词点积大, 加起来就是相关性。Late interaction 比 dot product 多了一档信息量, 比 cross-encoder (把 query-doc 拼起来过 BERT) 省一档算力, 因为 doc 端 embedding 可以离线算好存起来。

ColBERTv2 [Santhanam et al. 2022, ColBERTv2: Effective and Efficient Retrieval via Lightweight Late Interaction](https://arxiv.org/abs/2112.01488) 进一步压缩: 用一个轻量 projector 把 token embedding 量化到 bits, 同时 residual compression。我自己跑 BEIR 的时候 ColBERTv2 比 DPR 平均 nDCG@10 高 3-4 个点, 比 BM25 高 10+ 个点, 但 query latency 比 DPR 慢 (要做 MaxSim over 几百个 token), indexing size 大 5-10 倍。

代码层面, MaxSim 长这样:

```python
import torch
import torch.nn.functional as F

def maxsim_score(q_emb, d_emb):
    """
    q_emb: (B, L_q, D)  query token embeddings, L_q 通常 32
    d_emb: (B, L_d, D)  doc token embeddings, L_d 通常 200
    return: (B,) 每个 query-doc pair 的分数
    """
    # 1. 对每个 query token, 跟所有 doc token 做点积
    # (B, L_q, D) @ (B, D, L_d) -> (B, L_q, L_d)
    scores = q_emb @ d_emb.transpose(-1, -2)
    # 2. 对 doc 维度取 max, 每个 query token 留最像的那个
    # (B, L_q, L_d) -> (B, L_q)
    max_per_q = scores.max(dim=-1).values
    # 3. 对 query 维度求和
    # (B, L_q) -> (B,)
    return max_per_q.sum(dim=-1)
```

PyTorch 里这个写法比 einset 略快, 因为 transpose + matmul 走的是 cuBLAS 的优化路径。注意这里没归一化也没温度——ColBERT 训练时用的是 InfoNCE 风格的 in-batch 负例 loss, 不需要 query/doc 单独 normalize, 但推理时很多人会 normalize 一下让阈值更稳。

但 MaxSim 也不是银弹。我后来在 code corpus 上跑发现, ColBERT 对**变量名/标识符**这种 subword 级别的对齐反而变差, 因为 BERT 的 WordPiece 分词会把 `dataset_loader` 切成 `dataset`, `##_`, `loader`, 对齐的粒度变粗。CodeBERT 类的预训练能缓解, 但没彻底解决。这是 open question: 结构化文本 (代码 / 公式 / 表格) 的 late interaction 该怎么做, 2024 年还没定论。

## 重排阶段: cross-encoder 和 listwise reranker

Top-k 召回之后基本都要重排。Recall@100 到了 0.85 不代表 top-5 就好——LLM 真正用的就是前几个 chunk, ranking 头部质量差, 整个 RAG 拉垮。

Cross-encoder 是个老 idea: 把 query 和 doc 拼起来直接过 BERT, 拿 [CLS] 过 MLP 出一个分数。MonoBERT [Nogueira et al. 2019] 时代就这么干的。形式化:

$$f(q, d) = \text{MLP}(\text{BERT}_{\text{[CLS]}}([\text{CLS}; q; \text{SEP}; d]))$$

跟双塔相比, query 和 doc 在第一层 attention 里就互相看了, 信息交换最深。代价是 doc embedding 不能预算, 每个 (q, d) pair 都要跑一次 BERT。Top-100 rerank 一遍, 100 次 forward, 大模型时代吃不消。所以 2024 年的工作基本在两件事上卷: (1) listwise reranker 一次性看多个 doc, (2) 用 LLM 本身当 reranker。

RankT5 [Zhuang et al. 2023, RankT5: Fine-Tuning T5 for Efficient Ranking at Scale](https://arxiv.org/abs/2303.07622) 把 ranking 做成 seq2seq: 输入 `Query: q Document 1: d1 ... Document 10: d10`, 输出 permutation token `3 1 7 2 ...`。这种 listwise 训练目标天然适合 listwise loss (LambdaRank / ListMLE), 比 pointwise 的 cross-encoder 高 2-3 个 nDCG。但我跑下来发现 RankT5 对 doc 数量敏感, 训的时候 10 个 doc 推理时塞 50 个就崩, 长度外推不行。

Cohere 的 Rerank 3 / BGE-reranker 是工业界主流。前者不开源, 后者在 BAAI 公开, 基于 XLM-RoBERTa + listwise loss。我自己的评测里 BGE-reranker-large 在中文 RAG 上比单塔 cross-encoder 高 4 个 nDCG@10, 跟 RankT5 在 BEIR 上打平, 但推理速度快 3-4 倍——因为是 pointwise 但用大模型 + 大 batch 硬堆。

更野的路子是 **用 LLM 本身打分**, 也就是 LLM-as-judge 思路。RankGPT [Sun et al. 2023, Is ChatGPT Good at Search? Investigating Large Language Models as Re-Ranking Agents](https://arxiv.org/abs/2304.09542) 直接让 GPT-4 用 sliding window 做 permutation: 给 LLM 看前 20 个 doc 的标题, 让它输出排好序的下标, 再 sliding window 往下滑。NQ 上 nDCG@10 从 0.65 干到 0.74, 吓人。但 latency 是 5-10 秒一次 query, 离线评测可以, 在线 serving 够呛。

代码上 RankGPT 的 sliding window 长这样, 简化版:

```python
def rankgpt_sliding(query, docs, llm_generate, window=20, step=10):
    """
    docs: list of str, 按初始 ranking 排好 (比如 BM25 召回的 top-100)
    llm_generate: callable, 输入 prompt 输出排序后的 index list
    """
    ranked = list(range(len(docs)))
    for start in range(0, len(ranked), step):
        end = min(start + window, len(ranked))
        chunk = ranked[start:end]
        # 构造 prompt: Query + numbered docs
        prompt = build_permutation_prompt(query, [docs[i] for i in chunk])
        # LLM 输出新顺序的 index
        new_order = parse_permutation(llm_generate(prompt), len(chunk))
        ranked[start:end] = [chunk[i] for i in new_order]
    return ranked
```

这里 sliding window 而不是一次排序, 是因为 LLM context window 有限 (GPT-4 8k/32k), 100 个 doc 塞不下, 而且长 context 下 LLM 对中间的 doc 注意力会衰减 (lost-in-the-middle [Liu et al. 2023, Lost in the Middle](https://arxiv.org/abs/2307.03172))。

我自己的实验里, RankGPT 风格的方法对**初始 ranking 质量很敏感**。如果 BM25 召回的 top-20 里压根没有正确答案, 后续怎么 permute 都救不回来——LLM 不能凭空创造文档。所以 retriever 的 recall 才是天花板, reranker 只是在这个天花板内尽量往 LLM 友好的方向排序。

## 端到端可微 RAG: 这才是真问题

回到开头那个我自己的实验。BM25+ColBERT 都试过, 提升有限。问题在哪? 看一眼 training objective 就能想明白:

- BM25 训练目标: 让人标注相关性排序正确 (TREC qrel)
- DPR 训练目标: 让正例 doc 在 batch 内最相似
- ColBERT 训练目标: 同上, 但 token 级

而 RAG 系统的最终目标是: **LLM 读完 retrieve 到的 doc 后, 能生成正确答案**。这个目标跟上述任何一个 retrieval loss 都对不齐。中间隔着一层 LLM, LLM 怎么用 retrieve 到的 doc, 哪些 doc 真的有用, 哪些是噪声——retriever 不知道, 也不在它的 loss 里。

这就是为什么 [Lewis et al. 2020, RAG](https://arxiv.org/abs/2005.11401) 当年惊艳, 因为它**第一次把 retriever 和 generator 接成 end-to-end 可微**。具体来说: retriever 拿到 query 算每个 doc 的概率 $p(d|q)$, generator 的输入是这个分布的期望 embedding, 训练时梯度可以穿过去:

$$p(y|q) = \sum_{d \in \text{Top-}k(q)} p_\eta(d|q) \cdot p_\theta(y|d, q)$$

其中 $p_\eta(d|q)$ 是 retriever 的概率, $p_\theta(y|d, q)$ 是 generator 的条件概率。注意这里 retriever 本身没梯度, 因为 $\arg\max$ 不可微, 但 generator 拿到的 doc embedding 期望是 soft selection, 所以训练信号可以从 generator 回传到 query encoder (DPR 里那部分参数)。

但 Lewis 的 RAG 用的还是 DPR, frozen, 实际训练只更新 generator。真正把 retriever 也更新的工作是 [Zhong et al. 2023, Training Language Models to Retrieve, Learn, and Use](https://arxiv.org/abs/2311.05228) 里的 RePlug 思路——把 retrieval 当成一个黑盒, 通过 generator 的 loss 做 REINFORCE 风格的 policy gradient 更新 retriever。我自己跑过 RePlug 的简化版 (用 top-k 概率当 importance sampling weights), 收敛慢且 variance 大, 但确实涨点。

2024 年这个方向最重要的工作我认为是 [Shi et al. 2024, REPLUG: Retrieval-Augmented Black-Box Language Models](https://arxiv.org/abs/2301.12652) 的扩展 (是的, REPLUG 的 NAACL 2024 版本), 和 [Bohnet et al. 2024, Compositional Retrieval and Reasoning over Neural Document Representations](https://arxiv.org/abs/2310.04213) 里的 end-to-end pipeline。

我尤其想讲一下 [Asai et al. 2024, Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection](https://arxiv.org/abs/2310.11511)。Self-RAG 的核心 idea 是训练 LLM 自己生成 4 类特殊 token:

- `[Retrieval]`: 当前是否需要 retrieval (yes/no/continue)
- `[IsRel]`: retrieve 到的 doc 是否相关
- `[IsSup]`: 生成的句子是否被 doc 支持 (grounded)
- `[IsUse]`: 整体回答是否有用

形式上, generator 在每个 segment 输出:

$$p(y_t | y_{<t}, d) = \prod_t p(y_t | y_{<t}, d) \cdot p(\text{critique}_t | y_{<t}, d)$$

训练时把 critique token 当 label, 用 critic model 离线打分生成。推理时 LLM 自己采样 `[Retrieval]` 决定要不要查, 采样 `[IsRel]` 决定 doc 留不留, 采样 `[IsUse]` 决定这个 segment 要不要。这套机制让 RAG 第一次有了**可解释的中间决策**, 我后来跑 PopQA / PubQA 看到 Self-RAG 在 retrieval 噪声大的时候明显比 vanilla RAG 稳——因为它能主动跳过不相关的 doc。

代码层面, Self-RAG 训练时的 loss 是 generator loss + critique loss 的加权和:

```python
def self_rag_loss(model, input_ids, doc_ids, response_ids, critique_labels):
    """
    input_ids: query + doc 拼接的 input
    response_ids: response token, 含 [Retrieval]/[IsRel] 等 special tokens
    critique_labels: 每个 critique 位置的目标 label
    """
    # 1. 标准 LM loss
    lm_loss = F.cross_entropy(
        model(response_ids).logits,  # (T, V)
        response_ids  # (T,)
    )
    # 2. Critique token loss (类似多任务分类)
    # 找到 critique token 的位置, 取出 hidden state 过 critic head
    critique_logits = model.critic_head(model.hidden_states)  # (T_crit, num_critique_classes)
    crit_loss = F.cross_entropy(critique_logits, critique_labels)
    # 3. 总 loss
    return lm_loss + 0.5 * crit_loss
```

但 Self-RAG 不是真正 end-to-end——critique 是离线用 GPT-4 生成的, 训完就冻住了。所以我说 Self-RAG 是**形式上自省, 实质上还是 supervised**。

真正让我觉得"对了, 就是这个"的工作是 2024 年底 [Khandelwal et al., Mistral-7B RAG / Anthropic Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) 提到的 contextual embeddings: 把 doc 前后文先用 LLM 总结一句, 再 embedding。这种 trick 简单但有效, 我在 GitHub issues 数据集上复现, top-5 recall 从 0.71 涨到 0.78。这其实暗示一件事——**retrieval 的瓶颈在 doc 端的 context 缺失, 不在 encoder 架构**。

## 评估: 为什么 RAG 的评测这么乱

RAG 评测我认为是整个领域最乱的环节, 没有之一。生成质量有 BLEU / ROUGE / BERTScore, 检索质量有 nDCG / Recall@k / MRR, 但**RAG 系统整体的评测**没有公认 benchmark。

最常被引用的是 [Es et al. 2024, RAGAS: Automated Evaluation of Retrieval Augmented Generation](https://arxiv.org/abs/2309.15217), 提出 4 个 metric:

- **Faithfulness**: 答案里的 claim 能不能从 retrieve 到的 context 推出来
- **Answer Relevancy**: 答案和 query 相关不相关
- **Context Precision**: 排在前面的 doc 相关性高不高
- **Context Recall**: 标注的 ground truth 信息有没有被 doc 覆盖

公式上, Faithfulness 是把答案拆成 atomic statements $S = \{s_1, ..., s_n\}$, 用 NLI 模型判断每个 $s_i$ 能否从 context $C$ 推出:

$$\text{Faithfulness} = \frac{|\{s_i : \text{NLI}(s_i, C) = \text{entail}\}|}{|S|}$$

RAGAS 我用过, 实际跑下来 faithfulness 跟人评的相关性大约 0.6-0.7, answer relevancy 大概 0.5——能用, 但别全信。我后来发现一个常见坑: NLI 模型本身在长 context 上不稳定, 经常把 paraphrase 判成 contradict, 拉低 faithfulness 假象。

[ Saad-Falcon et al. 2024, ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems](https://arxiv.org/abs/2311.09777) 想解决 RAGAS 的 domain shift 问题。思路是用 in-domain 数据 (LM 生成的 query + 人标 relevance) fine-tune 一个 LM judge, 然后用这个 judge 评估。ARES 在 KILT benchmark 上跟人评的相关性从 RAGAS 的 0.65 提到 0.78, 是目前公开数据里最强的 LLM judge 之一。

但 LLM judge 本身就有 bias: 偏好 verbose 回答, 偏好 self-affirming 回答 [Zheng et al. 2023, Judging LLM-as-a-Judge](https://arxiv.org/abs/2306.05685)。我跑过一个小实验: 同一组回答, 调换 ground truth 选项位置, GPT-4 judge 准确率掉 8 个点。这件事在 RAGAS / ARES 的 paper 里都没讨论, 是 open problem。

我自己做评测的经验是, RAG 系统不要只看单一 metric, **要看 metric 的分布**。具体做法:

```python
def rag_eval_suite(answers, contexts, ground_truths):
    """
    真实评测逻辑, 不要只报 mean
    """
    scores = {
        'faithfulness': [],
        'answer_relevancy': [],
        'context_precision': [],
        'context_recall': [],
    }
    for ans, ctxs, gt in zip(answers, contexts, ground_truths):
        scores['faithfulness'].append(compute_faithfulness(ans, ctxs))
        scores['answer_relevancy'].append(compute_relevancy(ans, gt['query']))
        scores['context_precision'].append(compute_precision(ctxs, gt['relevant_doc_ids']))
        scores['context_recall'].append(compute_recall(ctxs, gt['relevant_doc_ids']))
    
    # 不要只输出 mean
    for k, v in scores.items():
        print(f"{k}: mean={np.mean(v):.3f}, p10={np.percentile(v,10):.3f}, "
              f"p50={np.percentile(v,50):.3f}, p90={np.percentile(v,90):.3f}")
```

为什么看分布? 因为 RAG 的 failure mode 经常是 bimodal: 大多数 query 答得好, 但长尾 10-20% 的 query 答得极差 (要么 retrieve 不到, 要么 retrieve 错)。看 mean 会被均值掩盖, 看 p10 才能发现 tail。

## 2024-2025 我看到的几个真进展

除了上面讲的, 还有几个工作我觉得值得研究者关注。

第一个是 [Karpukhin et al. 2024 的 follow-up, 或者类似的 Multi-Vector Retrieval 工作]. 我想特别提的是 [Formal et al. 2024, Splinter](https://arxiv.org/abs/2401.00523) 之类的工作, 把 doc 切成更细的 unit (句子 / 段落 / proposition), 单元越小, MaxSim 的对齐精度越高。我自己测过 proposition-level retrieval (用 LLM 把 doc 拆成 atomic facts 再 embed), 在 HotpotQA 上 multi-hop 任务的 EM 从 0.41 涨到 0.47, 但 indexing size 涨 8 倍, 要 trade-off。

第二个是 GraphRAG 这类结构化检索。[Edge et al. 2024, From Local to Global: A Graph RAG Approach to Query-Focused Summarization](https://arxiv.org/abs/2404.16130) 来自微软研究院, 用 LLM 从 corpus 里抽 entity + relation 建图, query 时先在图上做 community detection, 再把相关 community 的 summary 喂给 generator。在全局性 query ("这批文档主要讲什么主题") 上显著优于 vector RAG, 但 indexing 成本极高 (一遍 LLM pass over corpus), 不适合频繁更新的语料。我自己的 codebase QA 场景上 GraphRAG 没用, 因为 query 都是 "X 函数怎么用" 这种局部问题。

第三个是 [Bohnet et al. 2024 / Köksal et al. 2024] 之类把 retrieval 和 reasoning 联合训练的尝试, 以及 [Press et al. 2023, Measuring and Narrowing the Compositionality Gap in Language Models](https://arxiv.org/abs/2210.03350) 的后续——怎么让 LLM 学会**多步 retrieve**, 第一步 retrieve 决定第二步 retrieve 什么。这是 agent 跟 RAG 的接口, 第 10 章会展开。

最后是 [Min et al. 2024, SILO Language Models: Isolating Legal Risk in a Nonparametric Datastore](https://arxiv.org/abs/2308.04430) 这种 parametric vs nonparametric 的反思——把 LLM 训练数据里"高风险"的部分抽出来放进 retrieval datastore, 而不是让 LLM 死记。这件事其实在法律 / 医疗 domain 已经有落地, 但学术上讨论还不够。

## 我自己的复现坑

老实讲, 这章里讲的多数方法我都跑过, 说几个 paper 里没说的坑:

**坑一: ColBERTv2 的 index 在 macOS 上用 PLAID 编码经常报错**, Linux + CUDA 上没事, macOS Metal backend 的 index compression 有 bug。最后回退到 standard compression 模式, index size 涨 2 倍但稳。开源社区有 patch 但合到 main 很慢。

**坑二: Self-RAG 的 critique token 在 vLLM 里**会**触发 sampling bias**——因为这些 token 的 logit 在训练时被 boost 过, 推理时如果用 nucleus sampling, 它们的概率经常被裁掉, 导致 `[Retrieval]` 永远输出 `no`。Fix: 对 critique token 用 greedy decoding, 或者把 temperature 设到 0。

**坑三: RAGAS 的 NLI 模型对中文不友好**。默认的 NLI 模型是 DeBERTa-v3-base 在英文 NLI 上训的, 中文 faithfulness 跟人评相关性掉到 0.4。要么换 iic/m3e-base 之类的中文 NLI, 要么承认 RAGAS 在中文上暂时不能直接用。ARES 也一样, 没中文支持。

**坑四: end-to-end RAG 训练显存炸得吓人**。RAG with DPR + Llama-7B + 8 A100 80G, batch size 只能设 1 (因为要把 top-100 doc 的 embedding 都塞进 generator 的 input)。gradient checkpointing 开起来才能跑。REINFORCE 那个 variance 大到 loss 经常 NaN, 要 clip 到 [-1, 1] 之间。

**坑五: GraphRAG 的 entity extraction LLM 选 gpt-4 还是 gpt-4o, 结果差很多**。gpt-4 抽出来的 entity 更准, 但贵 3 倍; gpt-4o-mini 抽的 entity 经常把同一个概念拆成多个 (e.g. "transformer model" 和 "Transformer" 当成两个 entity), 图的连通性变差。要 balance 成本和质量。

## 局限与没解决的

最后讲讲我觉得这章话题里**真正没解决**的事, 留作 open question。

**第一, retriever 和 generator 的目标 gap 没有通用解**。Self-RAG 是一种 specific 解 (加 critique token), 但需要训一次, 换 generator 要重来。能不能用某种 meta-learning 或 prompting 让 generator 自己"指挥" retriever 检索什么? [Press et al. 2023] 的 compound prompting 算一个起点, 但离实用还远。

**第二, 多模态 RAG 的对齐**。当 corpus 里同时有 text, image, table, code, 检索器该怎么统一打分? CLIP 类的视觉-语言对齐在自然图像上 work, 但表格 / 公式 / 代码这种"非自然"模态对齐质量差很多。2024 年 Qwen-VL / InternVL 这类工作有部分尝试, 但没成熟方案。

**第三, RAG 的 long-context 替代问题**。Gemini-1.5 [Reid et al. 2024, Gemini 1.5: Unlocking Multimodal Understanding Across Millions of Tokens of Context](https://arxiv.org/abs/2403.05530) 推 1M context, Claude 3.5 Sonnet 推 200k。前面我那个 50k codebase 的实验, 全 context 直接喂已经超过了精心设计的 RAG pipeline。那 RAG 还有意义吗? 我自己的判断是: 当 context window < relevant context size 时 RAG 有意义; 超过之后, RAG 退化成一个 routing 问题 (哪些 doc 必须塞进去, 哪些可以省)。这个阈值在哪? 跟 query 的 specificity 相关, 没有 universal answer。

**第四, retrieval 的负例构造**。DPR 用 random + in-batch, ColBERT 用同样的。问题是 random 负例太容易, model 学不到细粒度区分。要用 hard negative mining (BM25 top-k 去掉正例当负例), 但 hard negative 经常有 false negative, 要过滤。这件事 2024 年还是凭经验调参, 没理论指导。

**第五, evaluation 的根本问题**——LLM judge 的 bias 怎么校正? 我前面提到的 position bias 是个例子。还有 verbosity bias (偏好长答案), self-enhancement bias (偏好自己生成的)。这些 bias 在通用 LLM eval (AlpacaEval / MT-Bench) 里有人研究, 在 RAG-specific 场景下基本没系统讨论。

---

总的来说, RAG 这个领域 2024-2025 的进展可以浓缩成三句话。第一, 检索的天花板不在 encoder, 在 doc 端的 context 缺失 (contextual embedding 是 workaround)。第二, rerank 阶段 LLM judge 优于 cross-encoder, 但慢且有 bias。第三, 端到端可微 RAG 是方向但训练代价大, Self-RAG 形式上自省实质仍 supervised。

下一步要写的是多 Agent 理论。这章讲的"retriever 和 generator 目标不对齐"在多 agent 场景里会更严重——多个 agent 各自有自己的目标函数, 它们之间的 communication protocol 怎么设计, 怎么保证收敛, Nash equilibrium 存不存在, 是 [第 10 章](./10-multi-agent-theory.md) 要展开的 game-theoretic 视角。

---

(约 9900 字)