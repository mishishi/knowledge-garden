# 08. 可观测性与成本

> 第 6 章讲了怎么防止失败，第 7 章讲了怎么选框架。本章讲选完框架之后，**怎么知道系统在干什么、烧了多少钱**。这是生产环境最容易被忽视的两个隐形炸弹。

## Part 1：可观测性

### 三大支柱

```
1. Trace（链路追踪）
└─ 一次请求从进入到结束，每一步做了什么、花了多少时间、消耗多少 token

2. Metric（指标）
└─ 聚合统计：每分钟调用次数、平均耗时、错误率、P95 延迟

3. Log（日志）
└─ 详细记录：每次 LLM 调用的输入输出、每次工具调用的参数和结果
```

---

### Trace 的核心概念

```
Trace（一次完整请求）
├── Span 1（Agent A 调用 LLM）
│   ├── 输入: prompt + tools
│   ├── 输出: response
│   ├── 耗时: 1.2s
│   └── tokens: 1500 input + 200 output
├── Span 2（Agent A 调用工具 get_weather）
│   ├── 输入: city="Tokyo"
│   ├── 输出: "22°C"
│   └── 耗时: 0.3s
└── Span 3（Agent B 调用 LLM）
    └── ...
```

完整代码：[`code/01_trace_demo.py`](./code/01_trace_demo.py)

---

### LangSmith：LangChain 生态的标准

```python
import os

# 启用 LangSmith
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_API_KEY"] = "lsv2_xxx"
os.environ["LANGSMITH_PROJECT"] = "my-multi-agent"

# 之后所有 LangChain / LangGraph / CrewAI 调用自动 trace
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4o-mini")
llm.invoke("hi")  # 自动上报到 LangSmith
```

**优点**：零代码集成、可视化最好

**缺点**：绑定 LangChain 生态、要付费（个人有免费额度）

---

### OpenTelemetry：跨框架标准

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="localhost:4317"))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)

# 在 Agent 调用处手动打点
with tracer.start_as_current_span("agent-call") as span:
    span.set_attribute("agent.name", "researcher")
    span.set_attribute("llm.model", "gpt-4o-mini")
    response = llm.invoke(...)
    span.set_attribute("llm.tokens", response.usage.total_tokens)
```

**优点**：跨框架、跨语言

**缺点**：要自己写集成代码

完整代码：[`code/02_otel_demo.py`](./code/02_otel_demo.py)

---

### 自建轻量 Trace

不依赖云服务的最小实现：

```python
import time
import json
from contextlib import contextmanager


class SimpleTracer:
    def __init__(self):
        self.spans = []

    @contextmanager
    def span(self, name: str, **attrs):
        span = {"name": name, "start": time.time(), "attrs": attrs}
        try:
            yield span
        finally:
            span["duration"] = time.time() - span["start"]
            self.spans.append(span)
            print(f"[Trace] {name}: {span['duration']:.3f}s {attrs}")

    def dump(self):
        return json.dumps(self.spans, indent=2, ensure_ascii=False)
```

**优点**：零依赖、5 行代码起步

**缺点**：没有可视化、不能跨服务

---

## Part 2：成本控制

### Token 成本估算

```
GPT-4o 输入:        $2.50 / 1M tokens
GPT-4o 输出:        $10.00 / 1M tokens
GPT-4o-mini 输入:   $0.15 / 1M tokens
GPT-4o-mini 输出:   $0.60 / 1M tokens
DeepSeek-V3 输入:   $0.14 / 1M tokens
DeepSeek-V3 输出:   $0.28 / 1M tokens
```

**一次 Multi-Agent 调用大概多少 token？**

```
单轮对话:     ~2,000 input + 500 output = ~$0.005 (gpt-4o-mini)
3 步 Pipeline: ~6,000 input + 1,500 output = ~$0.015
5 个并行评审:  ~10,000 input + 2,500 output = ~$0.025
```

1000 次调用 = $15-25。100,000 次 = $1,500-2,500。

完整代码：[`code/03_cost_tracker.py`](./code/03_cost_tracker.py)

---

### Token 预算强制

```python
class TokenBudget:
    def __init__(self, max_tokens: int):
        self.max = max_tokens
        self.used = 0

    def consume(self, tokens: int) -> bool:
        """返回 True 表示还能继续，False 表示超预算"""
        if self.used + tokens > self.max:
            return False
        self.used += tokens
        return True


# 在 Agent 循环里检查
budget = TokenBudget(max_tokens=20_000)

for round_idx in range(MAX_ITERATIONS):
    response = llm.call(...)
    tokens_used = response.usage.total_tokens

    if not budget.consume(tokens_used):
        return "[强制终止] 超过 token 预算"
```

完整代码：[`code/04_token_budget.py`](./code/04_token_budget.py)

---

### 模型分级（Model Routing）

```
简单任务（问候、分类、提取）→ gpt-4o-mini ($0.0006/1k tokens)
中等任务（写作、分析、总结）→ gpt-4o ($0.0125/1k tokens)
复杂任务（推理、规划、代码）→ gpt-4-turbo ($0.030/1k tokens)
```

**实现**：根据任务复杂度自动选模型

```python
def route_model(task_complexity: str) -> str:
    if task_complexity == "simple":
        return "gpt-4o-mini"
    elif task_complexity == "medium":
        return "gpt-4o"
    else:
        return "gpt-4-turbo"
```

完整代码：[`code/05_model_routing.py`](./code/05_model_routing.py)

---

### 缓存策略

```
缓存类型 1：Tool 结果缓存
└─ 同样的 tool call 不重复执行（天气查询、文档搜索）

缓存类型 2：LLM Response 缓存
└─ 同样的 prompt 不重复调 LLM

缓存类型 3：Embedding 缓存
└─ 同样的文本不重复计算 embedding
```

**最简单的实现**：用 functools.lru_cache 或 hash key

```python
from functools import lru_cache


@lru_cache(maxsize=100)
def cached_search(query: str) -> str:
    """同一个 query 只调一次"""
    return expensive_search_api(query)
```

---

### 循环检测（避免 Token 黑洞）

```python
# 已经在第 6 章讲过
# 关键：用 watchdog 检测重复调用
recent_tool_calls = deque(maxlen=3)

if len(set(recent_tool_calls)) == 1:
    return "[强制终止] 检测到重复调用"
```

---

### 提前终止（Quality Threshold）

Agent 不一定要"打磨到完美"——达到质量阈值就停。

```python
def evaluate_quality(output: str) -> float:
    """用 LLM 评估输出质量"""
    response = llm.invoke(f"评估以下输出的质量（0-1分）：\n{output}")
    return float(response.content)


# Agent 输出后评估质量
quality = evaluate_quality(agent_output)
if quality >= 0.8:
    return agent_output  # 质量够了，结束
else:
    # 让 Agent 继续改进
    ...
```

---

## 监控指标 Checklist

生产环境必须监控的指标：

```
业务指标
├─ 每小时请求数
├─ 平均处理时长
└─ 用户满意度（点赞/反馈）

技术指标
├─ Token 消耗 / session
├─ Token 消耗 / 用户 / 天
├─ LLM 调用错误率
├─ 工具调用错误率
├─ 单 session 最大循环次数
└─ P95 / P99 延迟

成本指标
├─ 单次请求成本
├─ 日成本 / 用户
├─ 月成本 / 功能模块
└─ 异常成本（死循环、过度调用）
```

---

## 告警规则

| 指标 | 阈值 | 告警级别 |
|------|------|---------|
| 错误率 | > 5% | 🔴 |
| 单 session 循环次数 | > 10 | 🔴 |
| 单 session Token 消耗 | > $0.5 | ⚠️ |
| 日成本环比 | +50% | ⚠️ |
| P95 延迟 | > 30s | ⚠️ |
| HITL 中断次数 | 持续增长 | ⚠️ |

---

## 本章小结

- **可观测性**：Trace / Metric / Log 三件套
- **Trace 工具**：LangSmith（最方便）/ OpenTelemetry（跨框架）/ 自建（最轻）
- **成本控制**：Token 预算 + 模型分级 + 缓存 + 提前终止 + 循环检测
- **监控**：业务 / 技术 / 成本三类指标
- **告警**：成本异常 + 错误率 + 延迟

## 下篇

[09. 实战：CrewAI 代码评审系统](../09-code-review-project/) —— 用 CrewAI 搭一个完整的代码评审 Multi-Agent 系统，从需求到部署。

## 生产化提示

可观测性的工程化：

- [ ] 启用 LangSmith 或 OpenTelemetry（必须有一个）
- [ ] 每个 Agent 调用有 trace
- [ ] Token 消耗实时统计
- [ ] 单 session 有成本上限
- [ ] 关键指标有 dashboard
- [ ] 异常有告警（Slack / 钉钉 / 飞书）