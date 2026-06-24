# 09. Eval-driven 迭代

> Prompt 写完不评测 = 赌博。**没评估的 prompt 调优就是凭感觉**——这一章讲怎么用 LLM-as-judge + A/B + 版本管理，让 prompt 调优从「感觉」变成「数据」。

## 为什么需要 Eval

写完 prompt 怎么知道它好？常见 3 种「评估方法」，最差的反而最常用：

| 方法 | 优劣 |
|------|------|
| **凭感觉**（"看着对"）| ❌ 不可量化、不可比较、不可复盘 |
| **人工 spot check**（看 20 个 case）| ⚠️ 样本小、贵、慢 |
| **自动 eval**（规则 + LLM-as-judge）| ✅ 可量化、可比较、可重跑 |

**没有 eval**：

- 改 prompt 不知道是变好还是变差
- 跨模型迁移效果未知
- 回滚不知道哪个版本好
- 团队成员各凭感觉吵架

**目标**：**改 prompt 有数据支撑，不是 taste 决定**。

## 3 大评估指标

### 指标 1：准确率

**任务正确率**——分类 / 提取 / 翻译等明确任务。

```python
def accuracy(llm_output: str, expected: str) -> float:
    """1.0 对，0.0 错"""
    return 1.0 if llm_output.strip() == expected.strip() else 0.0


# 评估
test_cases = [
    ("这个产品不错", "positive"),
    ("物流太慢", "negative"),
    ("一般吧", "neutral"),
]

correct = sum(
    accuracy(llm_output(case.input), case.expected)
    for case in test_cases
)
print(f"准确率: {correct / len(test_cases):.1%}")
```

### 指标 2：格式合规率

**输出是否符合要求**——JSON 是否合法、字段是否齐全、长度是否在范围内。

```python
import json
from pydantic import BaseModel, ValidationError


class ExpectedOutput(BaseModel):
    sentiment: str
    score: int
    issues: list[str]


def format_compliance(llm_output: str) -> float:
    """1.0 合规，0.0 不合规"""
    try:
        data = json.loads(llm_output)
        ExpectedOutput(**data)
        return 1.0
    except (json.JSONDecodeError, ValidationError):
        return 0.0
```

### 指标 3：质量分（LLM-as-judge）

**主观质量**——内容是否好、风格是否对、信息是否充分。用另一个 LLM 当裁判。

```python
JUDGE_PROMPT = """
你是资深质量评估员。评估下面 LLM 输出，按 0-10 打分。

# 评估维度
- 准确性：信息是否正确（0-3 分）
- 完整性：是否覆盖要求（0-3 分）
- 风格：是否符合要求的语气 / 格式（0-2 分）
- 实用性：是否真的有用（0-2 分）

# 任务要求
{task_description}

# LLM 输出
{llm_output}

# 输出格式
{{
  "score": 0-10,
  "accuracy": 0-3,
  "completeness": 0-3,
  "style": 0-2,
  "utility": 0-2,
  "reason": "1 句话说明"
}}
"""


def quality_score(llm_output: str, task: str) -> float:
    """用 LLM 当裁判打分"""
    prompt = JUDGE_PROMPT.format(task_description=task, llm_output=llm_output)
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    return data["score"] / 10
```

**实测**：GPT-4o 跟人类评分相关性约 0.7-0.8，足够替代人工 spot check。

## 怎么建 Eval Set

**Eval set = 一组「输入 + 期望输出」的测试集**。

### 来源 1：人工标注（最准）

```python
# 100-500 个 case 起步
eval_set = [
    {
        "input": "这个产品真不错",
        "expected_sentiment": "positive",
        "expected_score": 9,
        "expected_issues": [],
    },
    {
        "input": "物流太慢",
        "expected_sentiment": "negative",
        "expected_score": 3,
        "expected_issues": ["物流"],
    },
    # ...
]
```

**100 个 case 够看出趋势，500 个 case 够做 release 门禁**。

### 来源 2：历史生产数据

```python
# 从生产日志抽 1000 条「已知正确」的 case
historical_correct = db.query("""
    SELECT input, output
    FROM production_logs
    WHERE user_feedback = 'correct'
    LIMIT 1000
""")

# 用 LLM-as-judge 重新评分，过滤掉 judge 也不确定的
eval_set = filter_with_judge(historical_correct)
```

### 来源 3：LLM 生成 + 人工抽检

```python
# 用 LLM 生成测试 case
gen_prompt = """
为「电商评论情感分析」任务生成 50 个测试 case。
格式：
{"input": "...", "expected": "positive|negative|neutral", "notes": "为什么"}
"""
generated = llm.call(gen_prompt)
# 人工抽检 20 个，修掉错标
```

## LLM-as-Judge 实战

### 单维度评分

```python
def single_score_judge(
    output: str,
    criteria: str,
    judge_model: str = "gpt-4o",
) -> dict:
    """单维度评分"""
    prompt = f"""
评估下面输出是否满足标准：{criteria}

输出：
{output}

# 格式
{{
  "pass": true | false,
  "score": 0-10,
  "reason": "1 句话"
}}
"""
    response = openai.chat.completions.create(
        model=judge_model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)
```

### 多维度评分

```python
def multi_score_judge(output: str, task: str) -> dict:
    """多维度评分"""
    prompt = f"""
任务：{task}

输出：
{output}

# 多维度评分
{{
  "accuracy": 0-3,    // 准确性
  "completeness": 0-3,  // 完整性
  "style": 0-2,        // 风格
  "clarity": 0-2,      // 清晰度
  "total": 0-10,       // 总分
  "pass": true|false,  // total >= 7?
  "weakest": "..."     // 最弱的维度
}}
"""
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)
```

### LLM-as-Judge 的陷阱

**陷阱 1：位置偏见**

```python
# LLM 倾向给「第一个」或「最后一个」高分
# 解决：每次跑 A/B 测时把候选打乱顺序跑 2 次
```

**陷阱 2：自己审自己**

```python
# 错：GPT-4o 输出 + GPT-4o 评分（循环论证）
# 对：用更强模型评分（GPT-4o 输出，o3 评分）
# 或：用另一个独立 prompt 评分
```

**陷阱 3：评分 prompt 不准**

```python
# 错：评分 prompt 太宽
"评估这个输出好不好"

# 对：评分 prompt 具体
"评估这个产品介绍是否满足：1) 100 字以内；2) 包含问题/方案/特点；3) 没有 emoji"
```

**实测相关性**（GPT-4o 评 GPT-4o 输出）：

| 任务 | 跟人类评分的相关性 |
|------|------------------|
| 翻译质量 | 0.85 |
| 代码生成 | 0.78 |
| 创意写作 | 0.65 |
| 事实问答 | 0.92 |

**事实类任务评得准，创意类差些**。

## A/B 测试 prompt

**改 prompt 不知道好坏——A/B 看数据**。

```python
# 1. 定义 prompt A 和 B
prompt_v1 = """
你是客服。回答用户问题。
"""
prompt_v2 = """
你是 Acme 平台资深客服，5 年售后经验。
先共情再解决。用「您」不用「你」。
"""


# 2. 在 eval set 上跑
def ab_test(prompts: dict, eval_set: list) -> dict:
    results = {name: [] for name in prompts}

    for case in eval_set:
        for name, prompt in prompts.items():
            response = llm.call(f"{prompt}\n\n用户：{case['input']}")
            score = single_score_judge(response, case["criteria"])
            results[name].append(score["score"])

    summary = {
        name: {
            "mean": sum(scores) / len(scores),
            "pass_rate": sum(1 for s in scores if s >= 7) / len(scores),
            "std": statistics.stdev(scores) if len(scores) > 1 else 0,
        }
        for name, scores in results.items()
    }
    return summary


# 3. 跑
summary = ab_test(
    {"v1_basic": prompt_v1, "v2_detailed": prompt_v2},
    eval_set,
)
print(summary)
# {'v1_basic': {'mean': 5.2, 'pass_rate': 0.3, 'std': 2.1},
#  'v2_detailed': {'mean': 7.8, 'pass_rate': 0.85, 'std': 1.5}}
```

**决策规则**：
- pass_rate 提升 ≥ 10% → 用新 prompt
- pass_rate 差不多但 mean 提升 ≥ 0.5 → 用新 prompt
- 都没提升 → 保留旧的

## Prompt 版本管理

**Prompt 也是代码——用 Git 管**。

```python
# prompts/
# ├── v1.0.0/
# │   ├── system.txt
# │   ├── task_rewrite.txt
# │   └── eval_results.json
# ├── v1.1.0/
# │   ├── system.txt
# │   ├── task_rewrite.txt
# │   └── eval_results.json
# └── v2.0.0/
#     └── ...
```

```python
import json
from pathlib import Path


def load_prompt_version(version: str, name: str) -> str:
    """加载指定版本的 prompt"""
    path = Path(f"prompts/{version}/{name}.txt")
    return path.read_text(encoding="utf-8")


def save_eval_result(version: str, scores: dict):
    """保存 eval 结果"""
    path = Path(f"prompts/{version}/eval_results.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scores, indent=2), encoding="utf-8")


# 加载 v1.0.0 跑 A/B
prompt_v1 = load_prompt_version("v1.0.0", "system")
prompt_v2 = load_prompt_version("v1.1.0", "system")
summary = ab_test({"v1.0.0": prompt_v1, "v1.1.0": prompt_v2}, eval_set)
save_eval_result("v1.1.0", summary)
```

**版本号规则**（跟代码一致）：

- 主版本：重大重构
- 次版本：新增功能
- 修订版本：bug fix / 微调

**commit message**：

```bash
git commit -m "prompt: v1.1.0 - 增加角色 persona (eval pass rate 30% → 85%)"
```

## 实战：从 v1 到 v5 完整迭代

```python
# 起点 v1：基础 prompt
v1 = "你是客服。回答用户问题。"

# v1 跑 eval
v1_scores = evaluate(v1, eval_set)
# {'pass_rate': 0.3, 'mean': 5.2}

# 改 v2：加 persona
v2 = """
你是 Acme 平台资深客服，5 年售后经验。
回答用户问题。
"""
v2_scores = evaluate(v2, eval_set)
# {'pass_rate': 0.5, 'mean': 6.5}
# ↑ 提升 20%，保留 v2

# 改 v3：加输出格式
v3 = v2 + """

输出格式：
- 称呼：「您好」
- 内容：直接回答问题
- 结尾：「如有其他问题随时联系」
- 长度：100-300 字
"""
v3_scores = evaluate(v3, eval_set)
# {'pass_rate': 0.65, 'mean': 7.2}
# ↑ 提升 15%，保留 v3

# 改 v4：加 few-shot
v4 = v3 + """

例子：
用户：'我的订单 ABC123 什么状态？'
客服：'您好，订单 ABC123 已发货，物流单号 SF1234567890，预计 06-26 送达。'
"""
v4_scores = evaluate(v4, eval_set)
# {'pass_rate': 0.7, 'mean': 7.5}
# ↑ 提升 5%，边际收益小

# 改 v5：加边界
v5 = v4 + """

边界：
- 不能承诺具体退款金额
- 涉及账号安全转人工
- 不在订单范围内的问题拒绝
"""
v5_scores = evaluate(v5, eval_set)
# {'pass_rate': 0.85, 'mean': 8.0}
# ↑ 提升 15%，保留 v5

# v5 → 部署
```

**5 轮迭代，pass_rate 30% → 85%**。**没有 eval 你只能凭感觉**。

## 4 大反模式

### 反模式 1：凭感觉调 prompt

```python
# 错
v2 = "我觉得 v1 不好，加个 'professional'"
# 不知道好没好

# 对：v2 = "加 persona"，跑 eval，对比 v1
```

### 反模式 2：Eval set 太均匀

```python
# 错：eval set 全是简单 case
eval_set = [
    {"input": "你好", "expected": "你好"},
    {"input": "1+1", "expected": "2"},
]

# 真实生产中 LLM 表现好；调出来的 prompt 实际生产翻车

# 对：eval set 包含边界 case、模糊 case、难 case
```

### 反模式 3：Eval set 不更新

```python
# 错：eval set 写完后再不更新
# 用户行为变了 / 任务变了，eval 还在测旧场景

# 对：每月加 20-50 个新 case
# 重点：用户实际失败 case 优先入 eval
```

### 反模式 4：只测准确率，不测成本 / 延迟

```python
# 错：v2 比 v1 准确率高 5% 但 token 多 3 倍
v2_scores = evaluate(v2, eval_set)   # pass_rate 0.9
# 部署后发现月成本 $5,000 → $15,000

# 对：综合指标
def evaluate_with_cost(prompt, eval_set):
    scores = {"pass_rate": 0, "cost_per_call": 0, "latency": 0}

    total_cost = 0
    total_time = 0
    pass_count = 0

    for case in eval_set:
        start = time.time()
        response = llm.call(prompt, case["input"])
        elapsed = time.time() - start
        cost = (token_count(prompt) + token_count(response)) * PRICE

        if judge(response, case["expected"])["pass"]:
            pass_count += 1
        total_cost += cost
        total_time += elapsed

    n = len(eval_set)
    scores["pass_rate"] = pass_count / n
    scores["cost_per_call"] = total_cost / n
    scores["latency"] = total_time / n

    return scores
```

## 实战：eval pipeline 完整代码

```python
import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass
class EvalResult:
    version: str
    pass_rate: float
    mean_score: float
    cost_per_call: float
    latency_p50: float
    timestamp: str


class PromptEval:
    def __init__(self, eval_set_path: str):
        self.eval_set = json.loads(Path(eval_set_path).read_text(encoding="utf-8"))
        self.results = []

    def run(self, prompt: str, version: str, llm_call=None) -> EvalResult:
        scores = []
        costs = []
        latencies = []

        for case in self.eval_set:
            start = time.time()
            response = llm_call(prompt + "\n\n" + case["input"])
            elapsed = time.time() - start

            score = judge(response, case["expected"])
            scores.append(score["score"])
            costs.append(token_count(prompt + response) * 2.5e-6)
            latencies.append(elapsed)

        result = EvalResult(
            version=version,
            pass_rate=sum(1 for s in scores if s >= 7) / len(scores),
            mean_score=sum(scores) / len(scores),
            cost_per_call=sum(costs) / len(costs),
            latency_p50=sorted(latencies)[len(latencies) // 2],
            timestamp=time.strftime("%Y-%m-%d %H:%M"),
        )
        self.results.append(result)
        return result

    def compare(self, version_a: str, version_b: str) -> dict:
        a = next(r for r in self.results if r.version == version_a)
        b = next(r for r in self.results if r.version == version_b)
        return {
            "pass_rate": f"{a.pass_rate:.1%} → {b.pass_rate:.1%} ({(b.pass_rate - a.pass_rate):+.1%})",
            "cost": f"${a.cost_per_call:.4f} → ${b.cost_per_call:.4f}",
            "latency": f"{a.latency_p50:.2f}s → {b.latency_p50:.2f}s",
        }


# 用
ev = PromptEval("eval_set.json")
ev.run(v1, "v1.0.0", llm.call)
ev.run(v2, "v1.1.0", llm.call)
ev.run(v3, "v1.2.0", llm.call)
print(ev.compare("v1.0.0", "v1.2.0"))
```

## 跑不起来的常见坑

**坑 1：Eval set 在生产里漂移**

```python
# 错：eval set 写完 6 个月不更新
# 实际用户行为变了，eval 还测旧场景

# 对：每月加 50 个生产 case 进 eval set
# 重点加「生产里出错的 case」
```

**坑 2：LLM-as-judge 跟业务指标脱节**

```python
# 错：judge 给分 9 分，实际用户投诉不断
# 原因：judge 看的是「质量」，用户关心的是「解决问题」

# 对：judge 评分 + 实际用户反馈 两个指标都用
```

**坑 3：A/B 跑 5 个 case 就下结论**

```python
# 错：v1 vs v2，3 个 case 看出 v2 好
# 但 100 个 case 上 v1 可能更好（小样本不可靠）

# 对：至少 100 个 case，pass_rate 差异 ≥ 10% 才采纳
```

**坑 4：版本太多不清理**

```python
# 错：100 个 prompt 版本，混着用
# 对：保留最近 5-10 个版本，标注 deprecated
```

## 这章跑完之后你该会什么

- 3 大评估指标（准确率 / 格式合规 / 质量分）
- 3 种 eval set 来源（人工 / 历史 / LLM 生成）
- LLM-as-judge 实战 + 4 大陷阱
- A/B 测试 + 决策规则
- Git 版本管理 prompt
- v1→v5 完整迭代实战
- 4 大反模式
- 4 大常见坑

## 下篇

[10. 真实场景 4 案例](../10-real-cases/) — 客服 RAG 检索 / SQL 生成 / 文档摘要 / 代码 review 完整 prompt 拆解。
