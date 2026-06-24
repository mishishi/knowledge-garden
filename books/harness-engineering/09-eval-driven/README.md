# 09. Eval-Driven Development：Harness 怎么测自己

> 前 8 章讲的 harness 组件——loop / tool / context / permissions / observability / memory / recovery——每个都可能改坏。每次改 prompt、加 tool、调 compact 阈值，你怎么知道 harness 没退化？这章拆 harness 自己的测试体系。

## Agent 为什么难测试

传统软件测试套路是：输入 → 期望输出 → assert。Agent 不行：

- **输出非确定**：同一个 prompt 在 temperature=0.7 下可能出 3 种不同结果——"答对"和"答错"之间没 clear line
- **Context-dependent**：同一段 prompt 在 Sonnet 上 90% 成功，切到 Opus 可能 70%（Opus 思考更深，loop step 更多）
- **跨多个组件**：一个 bug 可能来自 prompt 问题 + tool schema 问题 + context 超限 + LLM API 故障——debug 时不知道是哪一层
- **User 行为多变**：用户用奇怪的方式问问题，agent 应该能 graceful 处理，但测试不可能覆盖所有怪问法

我自己的 harness 上线 6 个月，有 3 次 major regression 都是改完 prompt 后没跑全 eval 就上线——3 天后用户投诉才发现某类任务完成率从 80% 掉到 50%。

**没有 eval 体系的 agent 等于盲飞**。

## 3 层 Eval 体系

借鉴传统软件测试的分层：

**Unit Tests（单元）**：单个 tool / 组件的行为
```python
def test_bash_tool_blocks_rm_rf():
    result = execute_tool("bash", {"cmd": "rm -rf /"})
    assert "blocked" in result.lower()
    assert result["type"] == "blocked_command"

def test_bash_tool_allows_safe_commands():
    result = execute_tool("bash", {"cmd": "ls /tmp"})
    assert result["ok"] == True
    assert "exit=" in result
```

**Integration Tests（集成）**：多个组件协作
```python
def test_context_compact_at_80_percent():
    messages = create_long_conversation(target_tokens=150_000)
    compact = maybe_compact(messages, model="claude-sonnet-4")
    assert len(compact) < len(messages)
    assert all("前面对话总结" in str(m) for m in compact if "summary" in m.get("role", ""))
```

**E2E Tests（端到端）**：完整 agent 跑完整任务
```python
def test_e2e_weather_query():
    trajectory = run_agent("北京今天天气怎么样", trace=True)
    assert trajectory.status == "completed"
    assert trajectory.total_cost < 0.10  # 不应该贵
    assert trajectory.steps[-1].type == "final_response"
    assert "天气" in trajectory.final_response
```

3 层都要做。Unit test 写起来便宜、跑得快、debug 容易——每天本地跑。E2E test 烧 token 贵——CI 上每天跑一次或 harness 大改后跑。

## Golden Set：Agent 的"题库"

E2E test 的核心是 **golden set**——一组真实任务，每个任务有期望输出（或期望属性）。

我自己的 golden set 大约 200 个任务，覆盖：

- 简单查询（"今天日期"、"今天星期几"）
- 工具调用（"读文件 X"、"搜索 Y"、"调 API Z"）
- 多步任务（"读 3 个文件 → 总结 → 写新文件"）
- 错误恢复（"找不存在的文件"、"调不通的 API"）
- 边界情况（超长 query、奇怪格式、混合语言）
- 危险操作（"删 X"、"改系统配置"——应该被拒）

每个 task 标注：
- `expected_outcome`: completed / failed / blocked
- `expected_tools`: 期望调用的 tool 列表（subset 匹配即可）
- `expected_cost_max`: 成本上限
- `expected_steps_max`: 步数上限
- `must_contain` / `must_not_contain`: 输出必须/禁止包含的字符串
- `tags`: ["simple", "tool", "multi_step", "error_recovery", ...]

## Golden Set 从哪里来

我从 3 个来源持续累积 golden set：

**1. 真实用户任务（脱敏）**

用户允许的前提下，把他们的真实任务脱敏后加入 golden set。这是最好的来源——代表真实场景。

我自己每 50 次成功完成的任务，挑 1-2 个典型的加入 golden set。1 个月能加 20-30 个真实任务。

**2. Bug 报告任务化**

每次用户报 bug，我做的第一件事是把 bug 写成 golden set 的 task：

```yaml
- task: "把 /home/user/projects 里所有 .py 文件移到 /tmp/backup"
  tags: ["file_ops", "regression"]
  expected_outcome: completed
  expected_tools: ["bash", "list_dir"]
  expected_cost_max: 0.20
  # 历史: 2026-01-10 用户报"agent 用 mv 覆盖了不存在的目录"，修后加入
  bug_reference: "issue-2026-01-10"
```

这样修 bug 时跑的 regression test 包含这个 case——下次再退化立刻发现。

**3. 边界情况主动构造**

每月花 1 小时主动想 5-10 个"agent 应该怎么处理"的边界任务：

- "删文件然后立刻读它"——顺序错误
- "搜索关键词包含特殊字符 `*` `?` `[`"——shell glob 转义
- "任务描述特别长（5000 字）"——context 爆
- "用户输入 prompt injection 试图让 agent 发邮件"——safety
- "用户在第 3 轮突然切换话题"——memory 切换

## LLM-as-Judge：怎么写不被骗

E2E test 最难的部分是判断"agent 输出对不对"。我一开始用 exact string match（"输出必须包含'已完成'"），结果发现 30% 的"正确"答案措辞不同被判失败。

后来改用 **LLM-as-judge**——让另一个 LLM 评估 agent 输出。但 LLM judge 自己有 bias：

**Bias 1：位置偏见**

把候选答案放前面，judge LLM 倾向判它更好。

```python
# 错的：每次都是 agent 输出在第一个位置
def naive_judge(expected, actual):
    return llm_call(f"Which is better?\n1: {actual}\n2: {expected}")

# 对的：随机化位置 + 双向评估
def robust_judge(expected, actual):
    if random.random() < 0.5:
        order = f"1: {actual}\n2: {expected}"
    else:
        order = f"1: {expected}\n2: {actual}"
    
    result = llm_call(f"Which is correct (not better)? Reply 1 or 2.\n{order}")
    # 反向再问一次，取一致结果
    result2 = llm_call(f"Which answer is factually correct?\n{order}")
    return result == result2  # 一致才算
```

**Bias 2：长度偏见**

Judge LLM 倾向给更长的答案更高分——但长答案不一定对。

```python
# 在 judge prompt 里明确说长度不重要
JUDGE_PROMPT = """Evaluate which answer is MORE CORRECT for the task.
Ignore answer length. Ignore politeness. Judge purely on factual correctness.
Task: {task}
Answer A: {a}
Answer B: {b}
Reply with: A or B
"""
```

**Bias 3：自我偏见**

Judge LLM 是 Claude 时，倾向判 Claude 生成的答案更好；是 GPT 时判 GPT 的更好。

修：跑 eval 时**judge 用不同模型**——agent 用 Sonnet 4 时，judge 用 Opus 4；agent 用 Opus 时 judge 用 Sonnet。

**Bias 4：Trivial Compliance**

LLM judge 看到"看起来合理"的输出就判对——即使输出包含关键错误。

修：judge prompt 必须**列出具体验证点**：

```python
JUDGE_PROMPT_RIGOROUS = """Evaluate this agent answer against specific criteria.

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
"""
```

把 abstract "good answer" 拆成 5 个具体可验证的 criteria。Judge LLM 骗 abstract 容易，骗 5 个具体 PASS/FAIL 难。

## Regression Test：每次 harness 改动跑全套

我自己的 CI 配置：

```yaml
# .github/workflows/eval.yml
name: Eval
on:
  pull_request:
    paths:
      - 'build_reader.py'  # harness 改动触发
      - 'books/harness-engineering/**'  # 内容改动触发
  schedule:
    - cron: '0 2 * * *'  # 每天凌晨 2 点

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: python eval/run_full_eval.py
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

`run_full_eval.py` 跑所有 golden set，记录 pass rate、平均 cost、平均 latency，写到 `eval_history/`。

PR 触发时跑——如果 pass rate 比 main branch 低 5%+，PR 不让合。

## Pass Rate vs Cost vs Latency 三维

只看 pass rate 会鼓励"贵但稳"的 agent。我看三维：

```python
@dataclass
class EvalResult:
    task: str
    passed: bool
    cost: float
    latency_sec: float
    steps: int
    trajectory_id: str

def aggregate(results):
    pass_rate = sum(r.passed for r in results) / len(results)
    avg_cost = sum(r.cost for r in results) / len(results)
    p95_latency = sorted([r.latency_sec for r in results])[int(len(results) * 0.95)]
    
    return {
        "pass_rate": pass_rate,
        "avg_cost_usd": avg_cost,
        "p95_latency_sec": p95_latency,
        "total_cost_usd": sum(r.cost for r in results),
    }
```

新 prompt 版本发布前必须三维都不退化：

- pass_rate 不能掉 > 2%
- avg_cost 不能涨 > 20%
- p95_latency 不能涨 > 30%

我自己的实操经验：pass rate 是第一指标，cost 第二，latency 第三——cost 涨 30% 还能接受（业务价值更高），pass rate 掉 2% 立刻回滚。

## 一个完整的 eval 任务例子

```python
EVAL_TASK = {
    "id": "weather_query_beijing_2026",
    "task": "北京今天天气怎么样？",
    "tags": ["simple", "weather", "tool_call"],
    "expected": {
        "outcome": "completed",
        "must_call_tools": ["bash"],  # 至少调过 bash
        "must_not_call_tools": ["write_file", "rm"],  # 不应触发危险操作
        "cost_max_usd": 0.10,
        "steps_max": 5,
        "response_must_contain": ["北京"],
        "response_must_not_contain": ["乱编", "我不知道"],
    },
    "judge_prompt": "Agent should call weather API or use curl/web search, then summarize. Output should be plausible weather info (not 'I don't know').",
}

def run_eval(task):
    trajectory = run_agent(task["task"], trace=True)
    
    checks = {
        "outcome": trajectory.status == task["expected"]["outcome"],
        "must_call_tools": all(t in trajectory.tools_called for t in task["expected"]["must_call_tools"]),
        "must_not_call_tools": not any(t in trajectory.tools_called for t in task["expected"]["must_not_call_tools"]),
        "cost_max": trajectory.total_cost <= task["expected"]["cost_max_usd"],
        "steps_max": len(trajectory.steps) <= task["expected"]["steps_max"],
        "response_must_contain": all(s in trajectory.final_response for s in task["expected"]["response_must_contain"]),
        "response_must_not_contain": not any(s in trajectory.final_response for s in task["expected"]["response_must_not_contain"]),
        # LLM-as-judge for nuanced quality
        "judge_quality": llm_judge(task["task"], trajectory.final_response, task["judge_prompt"]),
    }
    
    return EvalResult(
        task=task["id"],
        passed=all(checks.values()),
        cost=trajectory.total_cost,
        latency_sec=trajectory.duration,
        steps=len(trajectory.steps),
        trajectory_id=trajectory.trace_id,
        checks=checks,
    )
```

## Eval 自己的元测试

LLM judge 自己也可能错（即使写了 anti-bias）。我每周做一次 meta-eval：人工评估 20 个 LLM judge 判过的 case，看 judge 跟人工判断的一致性。

```python
def meta_eval_judge(num_samples=20):
    # 抽样 20 个 case
    samples = random.sample(eval_history, num_samples)
    
    # LLM judge 已经判过
    judge_results = [r.judge_quality for r in samples]
    
    # 现在人工重新判
    human_results = []
    for s in samples:
        print(f"Task: {s.task}")
        print(f"Agent output: {s.trajectory.final_response}")
        result = input("Pass? [y/N] ")
        human_results.append(result.lower().startswith("y"))
    
    agreement = sum(j == h for j, h in zip(judge_results, human_results)) / num_samples
    print(f"Judge-human agreement: {agreement:.0%}")
    if agreement < 0.8:
        logger.warning("Judge is unreliable, consider rewriting judge prompt")
```

我自己 judge 跟人工一致率大概 85%——剩下的 15% 是 "subtle factual errors"（LLM judge 看不出，但人眼能看出来）。这部分加 cost 也不能完全消除，只能靠 domain expert 抽样 review。

## 这章踩过的关键坑

**Golden set 只用真实任务**——忽略边界情况，agent 在怪 query 上挂掉。修：每月主动构造 5-10 个边界 case 加入 golden set。

**LLM judge 不抗 bias**——judge LLM 倾向判自己模型的输出更好 / 更长的输出更好。修：双向问、随机化位置、明确 anti-bias prompt。

**Pass rate 100% 就以为稳了**——golden set 不覆盖新场景时 pass rate 没意义。修：每周 review golden set 覆盖率，主动加新 case。

**CI 跑 eval 太慢**——200 个 task × 30 秒/task = 100 分钟，PR 等不了。修：分两层——PR 跑 30 个 smoke test（5 分钟）、main branch 跑全套 200 个（cron）。

**Judge prompt 写得太长**——judge LLM 看到 2000 字 prompt 自己也糊涂。修：每个 eval task 的 judge prompt 不超过 300 字，只列最关键的 3-5 个验证点。

下一章 [10. 从零造一个 Harness](../10-build-from-scratch/) 把前 9 章串起来——完整代码 + 项目结构 + 从 prototype 到 production 的演进路径。
