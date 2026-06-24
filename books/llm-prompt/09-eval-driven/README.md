# 09. Eval-driven 迭代

> Prompt 写完不评测 = 赌博。没评估的 prompt 调优就是凭感觉——这一章讲怎么用 LLM-as-judge + A/B + 版本管理，把 prompt 调优从「感觉」变成「数据」。

## 为什么需要 Eval

我自己早期调 prompt 经常这样：花 2 小时改了 prompt，跑 5 个 case 觉得「好像更好了」，上线后用户反馈某类 query 效果变差。

写完 prompt 怎么知道它好？3 种「评估方法」：

凭感觉（"看着对"）—— 不可量化、不可比较、不可复盘。我早期全靠这个，结果新 prompt 在某些 case 上变差但我没发现。

人工 spot check（看 20 个 case）—— 样本小、贵、慢。每次改 prompt 都人工看 20 个 case 不 scale。

自动 eval（规则 + LLM-as-judge）—— 可量化、可比较、可重跑。改完 prompt 30 分钟跑全套 eval 立刻看到分数变化。

没 eval 的代价：改 prompt 不知道变好还是变差、跨模型迁移效果未知、回滚不知道哪个版本好、团队成员各凭感觉吵架。

目标：改 prompt 有数据支撑，不是 taste 决定。

## 3 个评估指标

准确率——任务正确率，分类 / 提取 / 翻译等明确任务。

```python
def accuracy(llm_output: str, expected: str) -> float:
    return 1.0 if llm_output.strip() == expected.strip() else 0.0
```

适用：分类（情感 / 主题 / 意图）、实体提取、JSON schema 校验、翻译（与 reference 对比）。

不适用：开放式生成（"写一篇关于 X 的文章" 没有唯一正确答案）。

忠实度——RAG 任务专用，LLM 回答是否基于检索到的 context 而不是幻觉。

```python
def faithfulness(answer: str, context_docs: list[str]) -> float:
    # 用 LLM 判断 answer 的每个 claim 是否都能在 context 找到
    claims = extract_claims(answer)
    supported = 0
    for claim in claims:
        if any(claim_supported_in_doc(claim, doc) for doc in context_docs):
            supported += 1
    return supported / len(claims) if claims else 1.0
```

我自己用 Braintrust / DeepEval 的 faithfulness 评估函数。Llamaindex 也有 RAGAS 库专门做 RAG 评估。

相关性——答案跟用户问题的相关度（不是忠实度——相关但可能幻觉）。

```python
def relevance(question: str, answer: str) -> float:
    # LLM-as-judge 打分 0-1
    prompt = f"""Rate how relevant this answer is to the question.
Question: {question}
Answer: {answer}
Reply with 0-1 score only."""
    return float(llm.call(prompt).strip())
```

我自己 prompt 调优时盯 3 个指标的加权平均：accuracy × 0.5 + faithfulness × 0.3 + relevance × 0.2。不同任务权重不同——RAG 任务 faithfulness 权重要高，开放式生成 relevance 权重要高。

## LLM-as-Judge 的 4 个 bias

用 LLM 评估 LLM 输出有 4 个常见 bias，必须防御：

**Bias 1：位置偏见**——把候选答案放前面，judge LLM 倾向判它更好。修：随机化位置 + 双向评估取一致结果。

**Bias 2：长度偏见**——Judge LLM 倾向给更长答案更高分。修：judge prompt 明确说「忽略长度」。

**Bias 3：自我偏见**——Judge LLM 是 Claude 时倾向判 Claude 生成的答案更好。修：跑 eval 时 judge 用不同模型（agent 用 Sonnet 时 judge 用 Opus，agent 用 Opus 时 judge 用 Sonnet）。

**Bias 4：Trivial Compliance**——Judge LLM 看到「看起来合理」的输出就判对，即使包含关键错误。修：judge prompt 列出具体 PASS/FAIL 验证点，让 abstract "好答案" 变成 5 个具体可验证 criteria。

我自己的 judge prompt 模板（参考 [Harness Engineering 09](../harness-engineering/09-eval-driven/) 那章的细节）：

```
Evaluate this agent answer against specific criteria.

Task: {task}
Agent answer: {answer}

Check each criterion (reply PASS/FAIL for each):
1. Does answer contain the user's name?
2. Does answer reference the specific file mentioned in task?
3. Did the agent actually CALL the required tool, or just claim to?
4. Are all factual claims accurate?
5. Does answer include any hallucinated content?

After each criterion, give a one-line justification.

Final verdict: PASS only if all 5 criteria PASS.
```

抽象「好答案」拆成 5 个具体 PASS/FAIL，judge LLM 骗 abstract 容易，骗 5 个具体 PASS/FAIL 难。

## Golden Set 构建

eval 的核心是 golden set——一组真实任务 + 期望输出（属性）。

3 个来源持续累积：

**真实用户任务（脱敏）**——用户允许的前提下，把真实任务脱敏加入 golden set。这是最好的来源，代表真实场景。我自己每 50 次成功完成的任务，挑 1-2 个加入 golden set。

**Bug 报告任务化**——每次用户报 bug，把 bug 写成 golden set 的 task：

```yaml
- task: "把 /home/user/projects 里所有 .py 文件移到 /tmp/backup"
  tags: ["file_ops", "regression"]
  expected_outcome: completed
  expected_tools: ["bash", "list_dir"]
  expected_cost_max: 0.20
  bug_reference: "issue-2026-01-10"
```

这样修 bug 时跑的 regression test 包含这个 case，下次再退化立刻发现。

**边界情况主动构造**——每月花 1 小时主动想 5-10 个「agent 应该怎么处理」的边界任务：「删文件然后立刻读它」（顺序错误）、「搜索关键词包含特殊字符 `*` `?` `[`」（shell glob 转义）、「任务描述特别长 5000 字」（context 爆）、「用户在第 3 轮突然切换话题」（memory 切换）。

我自己 golden set 大约 200 个任务，覆盖：简单查询（30%）、工具调用（25%）、多步任务（20%）、错误恢复（10%）、边界情况（10%）、危险操作（5%）。

## A/B 测试：两个 prompt 版本 PK

改 prompt 时必须有 A/B 测试。两个 prompt 版本在同一 golden set 上跑，看哪个指标更好：

```python
prompt_v1 = "你是 helpful assistant..."
prompt_v2 = "你是资深工程师..."

results = []
for task in golden_set:
    out_v1 = llm.call(prompt=prompt_v1, **task.inputs)
    out_v2 = llm.call(prompt=prompt_v2, **task.inputs)
    score_v1 = judge(out_v1, task.expected)
    score_v2 = judge(out_v2, task.expected)
    results.append({"task": task.id, "v1": score_v1, "v2": score_v2})

avg_v1 = sum(r["v1"] for r in results) / len(results)
avg_v2 = sum(r["v2"] for r in results) / len(results)
print(f"v1: {avg_v1:.2%}, v2: {avg_v2:.2%}")
```

我自己 prompt 改版流程：
1. 在 golden set 上跑当前版本（baseline）
2. 改 prompt
3. 在同一 golden set 上跑新版本
4. 对比指标——新版本必须 avg_score 涨 ≥ 2% 才上线
5. 如果新版本涨 ≥ 2% 但个别 case 退步 → 标注 regression，单独看

我自己的真实数据：每改 5 次 prompt 有 1 次真的提升（其余 4 次是 noise 或退步）。有 eval 才能区分。

## 版本管理：每次 prompt 改动留 trace

每次 prompt 改动必须留 trace——git commit + changelog：

```
## 2026-06-15
- prompt v3 → v4
- 改动: 加 "先共情再解决" 指令
- eval: avg_score 0.71 → 0.78 (+7%)
- regression: "退款金额" 类 case 退步 5%
```

regression 部分很重要——整体分数涨但某类 case 退步，可能上 production 后该类用户就跑了。

我自己用 git 存 prompt 文件（每个 agent 一个 .md），每次改 commit 一次：

```bash
git commit -m "prompt(客服): v3 → v4, +共情指令, eval 0.71 → 0.78"
```

CI 跑 golden set eval → 把分数写到 commit message → 团队 review 看分数变化 + regression。

## 三维评估：质量 / 成本 / 延迟

只看质量分数会鼓励「贵但稳」的 prompt。我自己看三维：

- **质量**（accuracy + faithfulness + relevance）—— 主指标
- **成本**（token / USD）—— 不能涨太多
- **延迟**（P95 latency）—— 不能涨太多

新 prompt 版本上线标准：质量涨 + 成本涨 ≤ 30% + 延迟涨 ≤ 30%。任意一项不达标就不上。

我自己真实案例：有一次 prompt v5 质量涨 5% 但 cost 涨 80%——拒绝上线。改设计后 v5.1 质量涨 4% cost 只涨 15%——上线。

## 实战：客服 prompt eval pipeline

```python
# eval/run_eval.py
from datasets import load_dataset

# 1. 加载 golden set
golden = load_dataset("customer_service_golden_v3.json")

# 2. 加载当前 prompt
with open("prompts/customer_service_v4.md") as f:
    prompt_v4 = f.read()

# 3. 跑 eval
results = []
for task in golden:
    response = llm.call(
        system=prompt_v4,
        user=task["user_message"],
    )
    
    score = judge_with_5_criteria(
        task=task["task"],
        answer=response,
    )
    
    results.append({
        "task_id": task["id"],
        "score": score,
        "cost": calculate_cost(response),
        "latency": measure_latency(response),
    })

# 4. 输出报告
avg_score = sum(r["score"] for r in results) / len(results)
avg_cost = sum(r["cost"] for r in results) / len(results)
p95_latency = sorted(r["latency"] for r in results)[int(len(results) * 0.95)]

print(f"Score: {avg_score:.2%}")
print(f"Avg cost: ${avg_cost:.4f}")
print(f"P95 latency: {p95_latency:.0f}ms")

# 5. 写入 history
with open(f"eval/history/{today()}.json", "w") as f:
    json.dump({
        "prompt_version": "v4",
        "avg_score": avg_score,
        "avg_cost": avg_cost,
        "p95_latency": p95_latency,
        "results": results,
    }, f, indent=2)
```

CI 跑这个脚本 → 分数写到 history → 任何 commit 触发 → 立刻看到 prompt 改动效果。

## 我自己的 prompt 调优 checklist

- 改 prompt 前：跑 baseline（当前版本在 golden set 上的分数）
- 改 prompt 时：每次只改一处（不要同时改 role + style + boundary）
- 改 prompt 后：跑新版本，对比三维指标
- 上线标准：质量涨 ≥ 2% + 成本涨 ≤ 30% + 延迟涨 ≤ 30%
- 每次上线：git commit + eval history 留 trace
- 每月 review：golden set 覆盖率（有没有新场景没覆盖），prompt 简化（能不能砍冗余指令）

[10. Real Cases](../10-real-cases/) 5 个真实 prompt 调优 case study——客服 / 代码审查 / 内容生成 / 数据分析 / 教学，每条 prompt 怎么从 v1 演化到 v5。
