# 06. Observability：Agent 在生产里跑，trajectory、cost、latency 怎么观测

> 前 5 章讲了 loop / tool / context / permissions。但 agent 上线后第一周你就会发现：本地跑得好好的任务在生产里 30% 失败，cost 莫名其妙翻 3 倍，某用户卡在第 12 步不动——没有 observability 你只能猜。这章讲 harness 第三块基石。

## Observability 为什么是 first-class

写传统 web 服务时 observability 是"上线后才加"——先 ship，崩了再补监控。Agent 不行：agent 的失败模式比传统服务多得多。

我列过自己 agent 上线第一周的真实事故：

- 某用户跑一个 30 步任务，agent 在第 17 步卡了 8 小时（loop 没设 timeout，烧了 $47）
- 同一段 prompt 在 Sonnet 上 95% 成功，切到 Opus 后变成 60%（Opus 更慢，context 爆得更快）
- 凌晨 3 点有人跑任务把 OpenAI rate limit 打满，影响所有其他用户
- 一个 prompt injection 让 agent 给 200 个用户发了同一封错误邮件

每一种事故**没有 trajectory 数据根本诊断不出来**。"agent 失败了"不等于"知道为什么失败"——可能是 prompt 问题、tool 失败、context 爆、cost 超限、rate limit、LLM API 故障。

## Trajectory 是什么

Trajectory = 一次 agent 运行的完整时间线记录。每一步：

```json
{
  "trace_id": "tr_2026_01_15_abc123",
  "user_id": "user_456",
  "task": "把 /home/user/projects 里的 Python 文件全备份到 /tmp",
  "start_time": "2026-01-15T10:23:45Z",
  "end_time": "2026-01-15T10:25:12Z",
  "status": "completed",
  "total_cost_usd": 0.18,
  "total_tokens": 45230,
  "steps": [
    {
      "step": 1,
      "type": "llm_call",
      "model": "claude-sonnet-4",
      "input_tokens": 1234,
      "output_tokens": 234,
      "cost_usd": 0.005,
      "latency_ms": 850,
      "request": {"system": "...", "messages": [...]},
      "response": {"content": "...", "stop_reason": "tool_use"},
    },
    {
      "step": 2,
      "type": "tool_call",
      "tool": "bash",
      "input": {"cmd": "ls /home/user/projects"},
      "output": "...",
      "latency_ms": 45,
    },
    {
      "step": 3,
      "type": "llm_call",
      "model": "claude-sonnet-4",
      ...
    }
  ]
}
```

核心字段：
- `steps[]` — 完整时间线，按顺序
- 每步有 type（llm_call / tool_call / user_input / error）
- llm_call 记录 request + response + cost + latency
- tool_call 记录 input + output + 成功/失败

trajectory 必须**完整、不可变、可重放**。完整 = 不省略 messages 内容（光记 token 数诊断不了 prompt 问题）；不可变 = 不能事后改；要可重放 = 数据格式要让"用同一份 trajectory 重跑 agent"成为可能。

## 三大 observability 平台对比

我自己用过的：

**Langfuse**（开源，自部署）
- 优势：开源、self-host、数据自己掌控、有 Python SDK 集成简单、有 prompt management UI
- 劣势：UI 不如商业产品漂亮、query language 学习曲线、社区版本 feature 有限
- 我用它做 hobby 项目和 side project

**LangSmith**（LangChain 官方）
- 优势：跟 LangChain / LangGraph 深度集成、UI 漂亮、debug 体验最好
- 劣势：vendor lock-in 到 LangChain 生态、self-host 复杂、数据托管在他们那里
- 我用过几个月后切回 Langfuse——我不想把 trajectory 数据给 LangChain

**Helicone**（云服务）
- 优势：drop-in 替代 OpenAI base URL，零代码改动接管所有 LLM call
- 劣势：只管 LLM call，不管 tool call 和 user input——trajectory 不完整
- 我用它做 quick MVP，长期项目还是会补 Langfuse

**自建**（PostgreSQL + JSON column）
- 优势：完全可控、query 自由、不依赖外部
- 劣势：UI 自己写、scale 自己管、debug 工具自己造
- 我现在的 production agent 都自建——trajectory 表 schema 如下：

```sql
CREATE TABLE trajectories (
    id UUID PRIMARY KEY,
    user_id VARCHAR,
    task TEXT,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    status VARCHAR,  -- 'completed' / 'failed' / 'timeout' / 'cost_exceeded'
    total_cost_usd NUMERIC,
    total_tokens INTEGER,
    metadata JSONB
);

CREATE TABLE trajectory_steps (
    id UUID PRIMARY KEY,
    trajectory_id UUID REFERENCES trajectories(id),
    step_index INTEGER,
    type VARCHAR,  -- 'llm_call' / 'tool_call' / 'error'
    model VARCHAR,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd NUMERIC,
    latency_ms INTEGER,
    request JSONB,
    response JSONB,
    error JSONB,
    timestamp TIMESTAMPTZ
);

CREATE INDEX ON trajectories (user_id, start_time DESC);
CREATE INDEX ON trajectory_steps (trajectory_id, step_index);
CREATE INDEX ON trajectories USING GIN (metadata);
```

`metadata JSONB` 让我能塞任意字段（agent version、tool version、用户 A/B 分组）。GIN index 让"找出所有用 prompt v3 跑的任务"这种 query 毫秒级返回。

## 自建 trajectory collector

最少 50 行代码，但能挡 90% 调试需求：

```python
import json
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class Step:
    step_index: int
    type: str
    timestamp: float
    latency_ms: int
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    request: Optional[dict] = None
    response: Optional[dict] = None
    tool: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[str] = None
    error: Optional[dict] = None

class TrajectoryCollector:
    def __init__(self, user_id, task):
        self.trace_id = f"tr_{uuid.uuid4().hex[:12]}"
        self.user_id = user_id
        self.task = task
        self.start_time = time.time()
        self.steps = []
        self.total_cost = 0.0
        self.total_tokens = 0
    
    @contextmanager
    def llm_call(self, model, request):
        step_idx = len(self.steps)
        t0 = time.time()
        try:
            yield  # caller does the LLM call inside
        except Exception as e:
            self.steps.append(Step(
                step_index=step_idx, type="llm_call",
                timestamp=t0, latency_ms=int((time.time()-t0)*1000),
                model=model, error={"type": type(e).__name__, "message": str(e)},
            ))
            raise
        else:
            # caller sets step.response / step.cost after the call
            pass
    
    def record_llm(self, step_idx, model, request, response, cost, input_tokens, output_tokens):
        latency = int((time.time() - self.steps[step_idx].timestamp) * 1000)
        self.steps[step_idx].update({
            "model": model, "request": request, "response": response,
            "cost_usd": cost, "input_tokens": input_tokens, "output_tokens": output_tokens,
            "latency_ms": latency,
        })
        self.total_cost += cost
        self.total_tokens += input_tokens + output_tokens
    
    def record_tool(self, tool, tool_input, tool_output, latency_ms):
        self.steps.append(Step(
            step_index=len(self.steps), type="tool_call",
            timestamp=time.time(), latency_ms=latency_ms,
            tool=tool, tool_input=tool_input, tool_output=tool_output[:5000],
        ))
    
    def record_error(self, error):
        self.steps.append(Step(
            step_index=len(self.steps), type="error",
            timestamp=time.time(), latency_ms=0, error=error,
        ))
    
    def save(self, status):
        # 异步落盘，不阻塞 agent 流程
        record = {
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "task": self.task,
            "start_time": self.start_time,
            "end_time": time.time(),
            "status": status,
            "total_cost_usd": self.total_cost,
            "total_tokens": self.total_tokens,
            "steps": [asdict(s) for s in self.steps],
        }
        trajectory_queue.put(record)  # 背景 worker 写 DB
```

主 loop 集成：

```python
trace = TrajectoryCollector(user_id, task)
try:
    while not done:
        with trace.llm_call(model, messages) as step_ref:
            resp = llm.call(model=model, messages=messages, tools=TOOLS)
            trace.record_llm(step_ref, model, messages, resp, calc_cost(resp), 
                           resp.usage.input_tokens, resp.usage.output_tokens)
        
        for block in resp.content:
            if block.type == "tool_use":
                t0 = time.time()
                result = execute_tool(block.name, block.input)
                trace.record_tool(block.name, block.input, result, int((time.time()-t0)*1000))
        
        if stop_condition:
            trace.save(status="completed")
except Exception as e:
    trace.record_error({"type": type(e).__name__, "message": str(e)})
    trace.save(status="failed")
    raise
```

## Cost Dashboard

Cost 是 agent 业务模型的核心——单次任务成本超过 $5 就很难 scale。我自己的 cost dashboard 三个核心 query：

**每日 cost per user**

```sql
SELECT 
    DATE(start_time) AS day,
    user_id,
    SUM(total_cost_usd) AS daily_cost,
    COUNT(*) AS task_count,
    AVG(total_cost_usd) AS avg_cost_per_task
FROM trajectories
WHERE start_time > NOW() - INTERVAL '30 days'
GROUP BY day, user_id
ORDER BY day DESC, daily_cost DESC;
```

找出"哪些用户在烧钱"。我见过一个用户一天烧 $200——他跑了一个 deep research 任务，agent 反复调 search_web 抓取大文档。

**Cost by task type**

```sql
SELECT 
    metadata->>'task_type' AS task_type,
    AVG(total_cost_usd) AS avg_cost,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_cost_usd) AS p95_cost,
    COUNT(*) AS count
FROM trajectories
WHERE status = 'completed'
GROUP BY task_type
ORDER BY avg_cost DESC;
```

找出"哪些任务类型最贵"。我自己的经验：deep research 类型平均 $0.80，比普通 chat 类型 ($0.02) 贵 40 倍。

**Failure cost**

```sql
SELECT 
    status,
    SUM(total_cost_usd) AS wasted_cost,
    COUNT(*) AS count
FROM trajectories
WHERE start_time > NOW() - INTERVAL '7 days'
GROUP BY status;
```

"失败任务烧了多少钱"。我自己一周平均浪费 $30——这钱本来可以省下来如果 harness 在 cost > $0.50 时就 abort。

## Latency 分析

Agent latency 比传统 API 难分析——不是单个请求延迟，是 N 步 loop 的总延迟。我看的几个指标：

**Step latency percentiles**

```sql
SELECT 
    type,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY latency_ms) AS p50,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99
FROM trajectory_steps
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY type;
```

LLM call 的 p95 应该在 3-8 秒之间（看模型）。tool call 的 p95 应该 < 5 秒（否则 user experience 差）。

**Loop step count**

```sql
SELECT 
    AVG(jsonb_array_length(steps)) AS avg_steps,
    MAX(jsonb_array_length(steps)) AS max_steps
FROM trajectories
WHERE status = 'completed' AND start_time > NOW() - INTERVAL '7 days';
```

如果 avg_steps 涨到 30+，说明 agent 在反复尝试某事——多半有 bug 让 loop 跑飞。

## Failure Analysis

我每周跑一次 failure triage：

```sql
-- 找出最常见的失败 step pattern
WITH failures AS (
    SELECT 
        trace_id,
        jsonb_array_elements(steps)->>'error' AS error_json
    FROM trajectories
    WHERE status = 'failed' AND start_time > NOW() - INTERVAL '7 days'
)
SELECT 
    error_json->>'type' AS error_type,
    COUNT(*) AS count
FROM failures
GROUP BY error_type
ORDER BY count DESC;
```

我自己过去一个月最常见的失败：

1. `RateLimitError` (40%) — Anthropic API 限流，harness 没做好 backoff
2. `ValidationError` (25%) — tool schema 不够严格，LLM 传错参数
3. `TimeoutError` (15%) — 长任务超过 LLM call timeout
4. `ContextLengthExceeded` (10%) — 没及时 compact
5. 其他 (10%)

每个失败类型对应不同的修复。RateLimit 加 backoff、Validation 改 schema、Timeout 调长 timeout / 加 step break、Context 加 trigger。

## Replay：用 trajectory 重跑 agent

最有价值的 observability 功能是 **replay**——同一个 task 用同一份 trajectory 数据能重跑 agent。这让你能：

- A/B test 新 prompt：固定 trajectory，重跑看是否改善
- 复现用户报的 bug：拿用户的 trace 重跑，看是否复现
- 测试新 model：固定 trajectory，换模型重跑看效果

```python
def replay_trajectory(trace_id, new_agent):
    """重跑同一个 task, 用新的 agent 配置"""
    trajectory = load_trajectory(trace_id)
    return new_agent.run(trajectory.task)

# 用例 1: A/B test prompt
old_result = replay_trajectory(trace_id, agent_v1)
new_result = replay_trajectory(trace_id, agent_v2)

# 用例 2: 切到新模型
gpt4_result = replay_trajectory(trace_id, agent_with_gpt4)
claude_result = replay_trajectory(trace_id, agent_with_claude)
```

我每次发新 prompt 版本前都跑 50 个 replay 看效果差异。如果新 prompt 比旧的成功率低 5%+ 就回滚。

## 这章踩过的关键坑

**Trajectory 只记 token 数不记 messages**——出问题想 debug 时发现 prompt 是什么都不知道。修：必须记 request + response 完整内容（可以异步压缩老数据）。

**Cost 算错**——Opus input $15/M、output $75/M，按字符算错一位小数账单差 10 倍。修：用官方 pricing 表 + 每天 cron 对账实际账单。

**Trajectory 落盘阻塞 agent**——同步写 DB 让 agent 慢 50ms。修：用 in-memory queue + background worker 异步落盘。

**不记 tool output**——只看 LLM call 不知道 tool 调得对不对。修：tool call 必须记 input + output（output 截断到 5000 chars）。

**只 debug 自己的 agent 不 debug 用户行为**——用户用奇怪的方式问问题导致 agent 失败。修：记 user message + agent response，让你能 replay 完整对话。

下一章 [07. Memory 分层](../07-memory-layers/) 拆 harness 第四块基石——working / episodic / semantic memory 怎么分层管理。
