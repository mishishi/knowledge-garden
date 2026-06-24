# 08. RAG 评测：怎么知道你的系统真的有用？

> 上线 RAG 第一周就开始收到用户吐槽：「回答不对」「找不到资料」。**没有评测，你不知道改哪里有用、改哪里反而退步。**

## 评测的两层

```
[1] 检索质量
    - 给定问题，正确文档在不在 Top-K 里？
    - 指标：Recall@K、MRR、NDCG

[2] 答案质量
    - 给定检索结果，LLM 回答得好不好？
    - 指标：准确性、相关性、幻觉率、用户满意度
```

**先优化检索，再优化答案**——检索错了再好的 LLM 也救不回来。

## 准备评测集

### 方法 A：人工标注（最准但贵）

```python
# 一个评测样本
{
    "question": "2024 Q3 营收是多少？",
    "ground_truth_docs": ["doc_abc_p5", "doc_abc_p6"],  # 正确文档 ID
    "ground_truth_answer": "12.3 亿元，同比增长 18%",  # 正确答案
    "difficulty": "easy",
}
```

**至少 50 条**，覆盖：
- 高频真实问题（从用户日志拿）
- 边界 case（搜不到答案的、问的错的、问多轮的）
- 不同文档类型 / 不同难度

### 方法 B：用 LLM 自动生成（量大但有偏）

```python
GENERATION_PROMPT = """基于以下文档生成 5 个不同的问题和正确答案：

{chunk_text}

输出格式（每条）：
Q: <问题>
A: <答案>
Source: <chunk_id>

要求：
- 问题要像真实用户会问的（口语化、有上下文）
- 答案必须严格基于文档内容
- 不能编造文档里没有的信息
"""

# 用 GPT-4 生成 + 人工抽检 10%
```

**性价比**：100 条 LLM 生成 + 20 条人工 = 120 条混合评测集，2-3 小时搞定。

## 检索质量指标

### Recall@K（前 K 个里命中正确答案的比例）

```python
def recall_at_k(retrieved_ids: list[str], gold_ids: list[str], k=5) -> float:
    """retrieved: 模型返回的 Top-K doc IDs（按相关度排序）
       gold: 正确答案的 doc IDs"""
    if not gold_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    hits = len(top_k & set(gold_ids))
    return hits / len(gold_ids)

# 评测
def evaluate_retrieval(eval_set, search_fn, k=5):
    recalls = []
    for sample in eval_set:
        retrieved = search_fn(sample["question"], top_k=k)
        retrieved_ids = [r["id"] for r in retrieved]
        recall = recall_at_k(retrieved_ids, sample["ground_truth_docs"], k)
        recalls.append(recall)
    return {
        "recall@5": sum(recalls) / len(recalls),
        "details": recalls,
    }
```

**目标**：Recall@5 > 0.85（85% 情况下正确答案在 Top-5）

### MRR（Mean Reciprocal Rank）

```python
def mrr(retrieved_ids: list[str], gold_ids: list[str]) -> float:
    """第一个正确答案排在第几位"""
    gold_set = set(gold_ids)
    for rank, doc_id in enumerate(retrieved_ids, 1):
        if doc_id in gold_set:
            return 1 / rank
    return 0.0
```

**比 Recall@K 更严格**——不仅要在 Top-K，还要靠前。

## 答案质量指标

### 1. Faithfulness（忠实度：答案是否基于检索内容）

**最关键的指标**——直接对应「幻觉率」。

```python
FAITHFULNESS_PROMPT = """判断下面【答案】是否完全基于【参考资料】回答，没有添加参考资料里没有的信息。

【参考资料】
{context}

【答案】
{answer}

判断：
A: 完全基于参考资料（忠实）
B: 大部分基于，但添加了少量外部信息
C: 部分基于，但有较多编造
D: 完全没基于参考资料

输出：A / B / C / D
"""
```

用 GPT-4 当 judge，**批 200 条评测集**看 A 比例。

### 2. Answer Relevance（答案与问题的相关度）

```python
RELEVANCE_PROMPT = """【问题】{question}
【答案】{answer}

这个答案是否回答了用户的问题？
A: 直接回答
B: 部分回答
C: 没回答，跑题了
"""
```

### 3. Context Precision（检索的 chunk 有多少是相关的）

```python
# 自动评估：每个 chunk 喂给 LLM 判断「是否与问题相关」
def context_precision(retrieved_chunks, question):
    relevant = 0
    for chunk in retrieved_chunks:
        if llm_judge(f"这段文档是否相关：{question}\n{chunk['text']}") == "YES":
            relevant += 1
    return relevant / len(retrieved_chunks)
```

## 综合评测 Pipeline

```python
class RAGEvaluator:
    def __init__(self, rag_pipeline, judge_llm):
        self.rag = rag_pipeline
        self.judge = judge_llm

    def evaluate(self, eval_set: list[dict]) -> dict:
        results = {
            "retrieval": {"recall@5": [], "mrr": []},
            "answer": {"faithfulness": [], "relevance": []},
            "context_precision": [],
        }

        for sample in eval_set:
            question = sample["question"]
            gold_docs = sample["ground_truth_docs"]
            gold_answer = sample["ground_truth_answer"]

            # 跑 RAG
            retrieved = self.rag.search(question, top_k=5)
            retrieved_ids = [r["id"] for r in retrieved]
            answer = self.rag.answer(question, retrieved)

            # 检索指标
            results["retrieval"]["recall@5"].append(
                recall_at_k(retrieved_ids, gold_docs, k=5)
            )
            results["retrieval"]["mrr"].append(
                mrr(retrieved_ids, gold_docs)
            )

            # 答案指标
            context = "\n".join(c["text"] for c in retrieved)
            results["answer"]["faithfulness"].append(
                self.judge.faithfulness(context, answer)
            )
            results["answer"]["relevance"].append(
                self.judge.relevance(question, answer)
            )
            results["context_precision"].append(
                self.judge.context_precision(question, retrieved)
            )

        # 汇总
        return {
            "recall@5": mean(results["retrieval"]["recall@5"]),
            "mrr": mean(results["retrieval"]["mrr"]),
            "faithfulness_A_ratio": count_a(results["answer"]["faithfulness"]),
            "relevance_A_ratio": count_a(results["answer"]["relevance"]),
            "context_precision": mean(results["context_precision"]),
        }
```

## A/B 实验框架

评测集不够代表真实用户，**上线后必须做 A/B**：

```python
# 简单分流
import hashlib
def get_variant(user_id: str) -> str:
    h = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
    return "A" if h % 2 == 0 else "B"

# A: 旧 chunk_size=500
# B: 新 chunk_size=300

# 记录每次问答
log = {
    "user_id": ...,
    "variant": get_variant(user_id),
    "question": ...,
    "answer": ...,
    "clicked_sources": [...],  # 用户点了哪个引用
    "thumbs_up": True/False,
    "thumbs_down": True/False,
    "follow_up": "...",  # 用户问了后续问题
}

# 关键指标
metrics = {
    "thumbs_up_rate": ...,
    "thumbs_down_rate": ...,
    "follow_up_rate": ...,  # 答案没解决需要追问
    "avg_session_questions": ...,
}
```

**最重要的指标是「用户不再追问」**——意味着一次答对。

## 监控线上表现

评测是离线指标，**线上实时监控**才能发现新问题：

```python
# 每次问答记录 + 监控
def log_rag_call(user_id, question, retrieved, answer, latency):
    # 1. 记录到日志
    log.info({
        "user_id": user_id,
        "question": question,
        "retrieved_ids": [r["id"] for r in retrieved],
        "answer": answer,
        "latency_ms": latency,
        "timestamp": datetime.now(),
    })

    # 2. 异常检测
    if latency > 5000:  # 5s 超时
        alert("RAG latency spike", user_id)
    if not retrieved:
        alert("No retrieval results", user_id, question)
    if is_low_quality_answer(answer):
        alert("Possible hallucination", user_id, question)
```

**告警维度**：
- 检索为空的比例（> 5% = 知识库缺数据）
- 平均 latency（> 3s = 系统瓶颈）
- 答案长度（异常短 = 答非所问）
- 引用次数（用户很少点 = 答案缺乏可追溯性）

## 调优时的对照实验

每次改参数（chunk_size、embedding 模型、prompt）必须跑评测：

```bash
# 修改 chunk_size = 500 → 300
# 跑评测
python evaluate.py --config baseline.json
# baseline: recall@5=0.78, faithfulness_A=0.72

python evaluate.py --config candidate.json
# candidate: recall@5=0.82, faithfulness_A=0.75

# ✓ candidate 更好，上线
```

**没有评测 = 盲改**。一个评测集 + 一个评测脚本 = RAG 项目的最重要投资。

## 下篇

[09. 高级模式](../09-advanced-patterns/) — Agentic RAG / Multi-hop / GraphRAG / HyDE 等进阶玩法。
