# 03. CoT 思维链

> "Let's think step by step" — 这一句话让 LLM 的推理能力跃升一个台阶。但这章也会讲：reasoning model 出现后，CoT 该怎么调。

## CoT 是什么

**Chain-of-Thought（思维链）** = 让 LLM 在给出最终答案前，先「想」一步——把推理过程写出来。

```python
# Zero-shot（不 CoT）
prompt = "9.11 和 9.9 哪个大？"
# LLM 可能回答 9.11 > 9.9（错的，9.9 = 9.90 > 9.11）

# CoT
prompt = """
9.11 和 9.9 哪个大？让我们一步一步想。
"""
# LLM 输出：
# 9.11 = 9 + 0.11
# 9.9 = 9 + 0.9
# 比较小数部分：0.11 < 0.9
# 所以 9.11 < 9.9
# 答案：9.9 更大
```

**原理**：LLM 不会在「一步」里同时想「问题理解」+「推理」+「输出答案」——拆成 3 步，每步独立想，准确率显著提升。

**原始论文数据**（Wei et al. 2022）：

| 任务 | Zero-shot | CoT |
|---|---|---|
| GSM8K（小学数学） | 10-20% | 40-60% |
| 数学推理（AQuA） | 25% | 45% |
| 常识推理 | 60% | 70% |
| 符号推理 | 30% | 80% |

数学 / 推理任务提升 30-50%。

## 3 种 CoT

**1. Zero-shot CoT：加一句「让我们想想」**——Wei et al. 2022 提的方法。适合不方便给例子或任务变化快的场景。单「Let's think step by step」一句话能让 GPT-3 推理能力提升 30%。

变体：中文「让我们一步一步分析这个问题」、英文「Let's think step by step」/「Let's think about this logically」/「Walk me through your reasoning」。注意点：「Let me think」比「Think」强（触发更慢思考），中文效果比英文略弱。

**2. Few-shot CoT：给推理例子**——给 3 个「问题 → 推理 → 答案」的例子。适合任务有固定模式、想要稳定输出。few-shot CoT 比 zero-shot CoT 又提升 10-20%。

```python
prompt = """
Q: 3 个苹果 + 2 个苹果等于几个苹果？
A: 3 + 2 = 5。5 个苹果。

Q: 一本书 12 章，读了 4 章，还剩几章没读？
A: 12 - 4 = 8。8 章没读。

Q: 火车从 A 出发，时速 60 km/h，开 2 小时到 B。A 到 B 多少 km？
A: 60 × 2 = 120。120 km。

Q: 鸡兔同笼，共 35 头，94 足，几只鸡几只兔？
A: 假设全是鸡，35 × 2 = 70 足。差 94 - 70 = 24 足。每只兔比鸡多 2 足。24 / 2 = 12 兔。35 - 12 = 23 鸡。
"""
```

**3. Self-Consistency：多次采样 + 投票**——跑 N 次 CoT（temperature > 0），取「出现次数最多的答案」：

```python
results = [llm.call(prompt + "\nLet's think step by step.", temperature=0.7) for _ in range(7)]
final_answer = majority_vote([extract_answer(r) for r in results])
```

**原理**：推理过程可能不同，但正确答案不变。多次采样 → 投票选最稳的。Wang et al. 2022 在 GSM8K 上把 CoT 从 56% 提到 74%。

**成本**：跑 7 次 = 7 倍 token。**只在「重要决策 + 错误代价大」场景用**（金融 / 医疗 / 合规）。

变体：Tree-of-Thought（分支推理 + 回溯）、Graph-of-Thought（图结构推理，更灵活但实现复杂）。实际生产里 80% 用 Self-Consistency 就够了。

## CoT 怎么写 prompt

**基础格式**——「让我们一步一步想」必须放任务之后：

```python
prompt = """
[任务描述]
[问题]

让我们一步一步想。
"""
```

**加约束**（复杂任务，模型推理容易跑偏）：

```python
prompt = """
[任务]

我们一步一步分析这个问题：
1. 提取问题中的关键数字
2. 列出已知条件
3. 列出未知量
4. 列出公式 / 关系
5. 求解
6. 验证答案合理性

问题：{question}
"""
```

**加格式**（让推理可解析，下游只取答案）：

```python
prompt = """
[任务]

让我们一步一步想。

输出格式：
【思考】
<逐步推理>

【答案】
<最终答案>
"""
```

## CoT 的 4 大实战场景

**数学 / 逻辑题**：

```python
prompt = """
让我们一步一步算。

小明有 50 元。他买了 3 本书，每本 12 元。又花了 5 元坐车。还剩多少？

# 期望输出：
# 1. 买书花了 3 × 12 = 36 元
# 2. 加上坐车 5 元，共花 36 + 5 = 41 元
# 3. 50 - 41 = 9 元
# 还剩 9 元
"""
```

**多步推理**——涉及多个逻辑步骤：

```python
prompt = """
事件 A：客户在 3 天前下单。
事件 B：商品缺货。
事件 C：客服昨天联系客户。
事件 D：客户没回。

现在能不能直接给客户退款？

让我们一步一步分析：
"""
```

**分类 + 解释**——不是「分类」，是「分类 + 给理由」：

```python
prompt = """
评论：'哎妈这客服太贴心了，等了一小时终于解决了我的问题！'
情感分类：？

让我们一步一步想：
# 期望：「讽刺 → 负面」 OR 「真心夸 → 正面」
# CoT 让模型「解释为什么」，避免表面误判
```

**代码 / Debug**：

```python
prompt = """
def add(a, b):
    return a - b  # 应该是 +

# 这段代码的 bug 在哪？让我们一步一步分析：
# 期望：
# 1. 函数名叫 add，但实际是减法
# 2. 应该是 return a + b
# 修复：return a + b
"""
```

## Reasoning Model 时代还要 CoT 吗

**2024 年底 OpenAI o1/o3、Claude 3.7 with thinking 出现**——这些模型**自动思考**，不强制要 CoT prompt。

**答案：传统 LLM（GPT-4o / Claude Sonnet）需要 CoT；reasoning model 不要。**

**reasoning model 加 CoT 引导反而干扰**：

```python
# 错：给 reasoning model 加 CoT 引导
prompt = "Let's think step by step. 任务：证明这个定理。"

# 对：直接给完整信息
prompt = "证明：对于任意正整数 n > 1，存在素数 p 满足 n < p < 2n。直接给完整证明。"
```

reasoning model 加 CoT 引导的问题：它自己会「think」被强制按你的格式反而不自然 / 浪费 token（reasoning model 输出本身就包含思考）/ 慢（加 CoT 引导让模型「双思考」）。

**Reasoning model 的最佳实践**：

1. 给完整背景（上下文 + 约束 + 任务 + 输出格式）
2. **不要给思考提示**（「think carefully / step by step」会让它双思考）
3. 选 temperature = 0（reasoning model 内部思考已经够随机）
4. 用 `max_completion_tokens` 控制输出长度（避免 reasoning + 答案太长）
5. 简单任务别用（「翻译这句话」用 o3 反而更差，过度思考）

**什么时候用 reasoning model**：

- 翻译 / 摘要 → GPT-4o-mini / Claude Haiku
- 代码生成 → Claude Sonnet / GPT-4o
- 数据提取 → GPT-4o-mini（JSON mode）
- 数学证明 / 复杂推理 → o3 / Claude with thinking
- 策略规划 → o3
- 多步决策 → o3
- 代码 debug → o3 / Claude with thinking
- 常识推理 → Claude Sonnet（够用）

**判断标准**：任务需要「分多步想」才用 reasoning model。

## CoT 的 6 大反模式

**1. CoT 用于简单任务**——翻译不需要「想」，加 CoT 浪费 token。

**2. CoT 引导用错关键词**——「Think about this」是弱引导（模型可能 think 但不输出推理），「Let's think step by step」是强引导。经验：含「step」「step-by-step」「chain of thought」的引导 > 「think」「consider」。

**3. CoT 推理过程太长**——「very detailed step by step」让模型写出 2000 字推理浪费 token。实际推理 200-500 字足够。

**4. CoT 输出没约束格式**——推理和答案混在一起，下游难解析。修：明确【思考】+【答案】分段。

**5. CoT 例子选错**——CoT 例子跟任务不匹配，模型学不到模式。修：例子的 CoT 推理必须跟任务同类型。

**6. CoT 后忘了给答案**——只让模型推理没让它给最终答案。修：明确「请在最后一行写『答案：<你的最终答案>』」。

## Self-Consistency 实战

```python
import openai
from collections import Counter

def self_consistent_answer(question, n_samples=7, temperature=0.7):
    prompt = f"{question}\n\nLet's think step by step."

    responses = []
    for _ in range(n_samples):
        r = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        responses.append(r.choices[0].message.content)

    answers = [extract_final_answer(r) for r in responses]
    counter = Counter(answers)
    most_common = counter.most_common(1)[0][0]
    return most_common, responses


def extract_final_answer(text):
    lines = text.strip().split('\n')
    last_line = lines[-1].strip()
    if "答案" in last_line:
        return last_line.split("答案")[-1].strip("：: ")
    return last_line
```

**成本优化**：

早期停止——4 次中已有 3 次一致就提前结束：

```python
def adaptive_self_consistent(question, target_n=7, early_stop=3):
    answers = []
    for i in range(target_n):
        r = llm.call(question)
        a = extract_final_answer(r)
        answers.append(a)
        if answers.count(a) >= early_stop:
            return a
    return Counter(answers).most_common(1)[0][0]
```

并发采样——7 次独立请求并发跑（不要串行）。

## CoT 的 4 大局限

**1. token 成本**——CoT 输出 = 任务输出 + 推理过程（3-10x 长）。1000 次调用 = 1000 × 推理 token 成本。

**2. 推理过程本身可能错**——CoT 提高了「推理 + 输出答案」整体准确率，但推理过程本身可能错。模型可能「推理得很自信但其实算错」。

**3. 不适合发散任务**——创意写作、头脑风暴加 CoT 让模型「按步骤想」反而限制发散。

**4. reasoning model 时代价值下降**——o3 / Claude thinking 已经内置「思考」，手动加 CoT 浪费 token。

## 4 个常见坑

**坑 1：CoT 引导位置错**——「Let's think step by step」放任务之前会让模型先 CoT 再读任务，推理跑偏。修：放任务之后。

**坑 2：CoT 后没让模型给答案**——只推理不给答案，下游拿不到结果。

**坑 3：CoT 推理被截断**——`max_tokens=100` 时推理 200 字 + 答案 20 字总共 220 > 100，答案被截断。修：`max_tokens` 留够空间（一般 1000+）。

**坑 4：CoT 推理污染下游**——直接 print(response) 用户看到「思考：...」体验差。修：解析后只输出【答案】部分。

## 怎么评估 CoT 效果

```python
# 1. 准确率提升
baseline_acc = evaluate(test_set, no_cot_prompt)
cot_acc = evaluate(test_set, cot_prompt)
print(f"CoT 提升：{(cot_acc - baseline_acc) * 100:.1f}%")

# 2. Token 成本增加
baseline_tokens = avg_tokens(no_cot_prompt_response)
cot_tokens = avg_tokens(cot_prompt_response)
print(f"Token 增加：{cot_tokens / baseline_tokens:.1f}x")

# 3. 成本 vs 准确率 trade-off
print(f"每 1% 准确率提升的成本：${(cot_cost - baseline_cost) / (cot_acc - baseline_acc)}")
```

**经验**：CoT 至少要提升 5% 准确率才值得加（多花的 token 要赚回来）。
