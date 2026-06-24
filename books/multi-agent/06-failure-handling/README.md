# 06. 失败的艺术

> Multi-Agent 系统的失败是单 Agent 的 N 倍（N = Agent 数量）。这章讲失败怎么分类、4 层防御、人机协同的边界。

## Multi-Agent 为什么失败率更高

我维护过一个 5-Agent 链路（研究 → 写 → 审 → 润色 → 校对），第一周 production 数据：单 session 平均跑 12 轮、失败率 38%、单次成本峰值 $4.20。失败里 60% 不是某个 Agent 本身出错，而是**Agent 之间传递出错了**——上游 Agent 输出格式不对、下游解析失败、状态丢失。

单 Agent 失败基本是 LLM 或工具的事，定位明确。Multi-Agent 失败可能是：某个 Agent 内部失败、Agent 之间通信失败、级联失败（一个挂下游全挂）、系统级失败（cost / 时延 / 死循环）。Debug 时不知道是哪一层。

这一章讲 4 类失败、4 层防御、Human-in-the-Loop、graceful degradation、监控指标。

## 失败的 4 个层级

我自己归类 multi-agent 失败的方式：

**Agent 自身失败**——LLM 输出 malformed（JSON 错、字段缺）、LLM 调用超时、LLM 违反 prompt 约束（比如「必须基于事实」但它编了）、Agent 死循环（反复调同一个工具不结束）。

**工具失败**——工具超时、工具返回错误、工具不可用（API 限流、服务挂）、工具鉴权失败。

**通信失败**——上游 Agent 输出格式不对（下游解析失败）、状态丢失（共享 State 被意外清空）、消息过大（超过 context 窗口）。

**系统级失败**——Token 烧光（成本失控）、死循环导致无限次 LLM 调用、级联失败（一个 Agent 挂所有下游挂）、时延过高（用户体验差）。

实际生产里 4 类比例大概是 30% / 35% / 15% / 20%。工具失败占比最高（外部 API 不可控），系统级失败代价最高（一次烧 $50+）。

## 防御 1：死循环检测（3 重保险）

Agent 反复调同一个工具、LLM 每次都觉得「还需要再调一次」永远不结束——这是 multi-agent 最常见的失败。

我自己用 3 重保险，任何一重触发就强制终止：

```python
MAX_ITERATIONS = 10
WATCHDOG_THRESHOLD = 3
TOTAL_TOKEN_BUDGET = 50_000

recent_tool_calls = []
used_tokens = 0

for round_idx in range(MAX_ITERATIONS):
    # 保险 1: max_iterations 强制终止
    tool_call = agent.decide()
    
    # 保险 2: Watchdog 检测重复模式
    recent_tool_calls.append(tool_call)
    if len(recent_tool_calls) > WATCHDOG_THRESHOLD:
        recent_tool_calls.pop(0)
    if len(set(recent_tool_calls)) == 1:  # 全部相同
        return "[强制终止] 检测到重复调用"
    
    # 保险 3: Cost Budget 限制 token 消耗
    response = llm.call(...)
    used_tokens += response.usage.total_tokens
    if used_tokens > TOTAL_TOKEN_BUDGET:
        return "[强制终止] 超过 token 预算"
    
    if finished:
        break
else:
    return "[强制终止] 超过最大循环次数"
```

3 重保险的理由：单一保险都有盲区。max_iterations 不知道"合理"轮数（不同任务差异大）；Watchdog 只检测重复模式，不检测「轮次高但不重复」（比如 LLM 在不同子任务间跳来跳去）；Cost Budget 在 LLM 单价高时一触发就超。3 重叠加才能保证不烧钱。

我自己的真实事故：有一次 production agent 死循环烧了 $47 才被 alert 发现（cost alarm 设的是 $5/小时，但 alert 是小时粒度）。之后所有 agent 强制 3 重保险，cost alarm 改 5 分钟粒度。

## 防御 2：超时与重试

工具调用卡住整个 Agent 链路等待——常见于外部 API（搜天气、抓网页、调 LLM）。两层防护：

**工具层：指数退避重试**

```python
import time
from functools import wraps

def retry_with_backoff(max_retries=3, base_delay=1.0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    delay = base_delay * (2 ** attempt)  # 1s / 2s / 4s
                    time.sleep(delay)
        return wrapper
    return decorator
```

**Agent 层：Fallback 链**

工具彻底失败时 Agent 应该降级，不是死等：

```python
def get_weather_with_fallback(city: str) -> str:
    try:
        return primary_weather_api(city)
    except Exception:
        try:
            return secondary_weather_api(city)  # Fallback 1: 另一个 API
        except Exception:
            return f"{city} 的天气暂时无法查询，请稍后再试"  # Fallback 2: 诚实说不知道
```

**关键原则**：不要让 LLM 猜，宁可让 Agent 说「不知道」。我见过让 LLM 「既然 API 挂了编一个合理的回答吧」——这种 fallback 是反模式，会污染下游 Agent 的输入。

## 防御 3：级联失败隔离

5-Agent 链路第 3 个挂了，第 4 和第 5 永远等不到输入。两种隔离模式：

**Circuit Breaker（断路器）**——失败 N 次后熔断一段时间，所有调用立刻返回失败，不让一个 Agent 持续挂死整个链路：

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=3, reset_timeout=60):
        self.failures = 0
        self.threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure_time = None
        self.state = "closed"  # closed / open / half-open

    def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "half-open"
            else:
                raise Exception("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            self.failures = 0
            self.state = "closed"
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.threshold:
                self.state = "open"
            raise
```

**Partial Failure（部分成功部分返回）**——不要"All or Nothing"。每个 step 独立 try/except，失败的标 `skipped`，继续下一步：

```python
def multi_step_pipeline(steps):
    results = {}
    for step_name, step_func in steps.items():
        try:
            results[step_name] = step_func()
        except Exception as e:
            results[step_name] = {"error": str(e), "skipped": True}
    return results
```

我的真实场景：用户问"X 项目最大风险是什么"，需要研究 → 总结 → 评审 三步。研究挂了的话，研究结果是 `{"error": "...", "skipped": True}`，但总结 + 评审还能基于"没研究结果"继续——比"全部挂"用户体验好得多。

## 防御 4：Human-in-the-Loop

关键决策点让人类介入，避免 LLM 自主决定高风险操作。LangGraph 的 `interrupt` 是常见实现：

```python
from langgraph.checkpoint import MemorySaver
from langgraph.graph import StateGraph
from langgraph.prebuilt import interrupt

def critical_decision_node(state):
    """关键决策：暂停，让人类介入"""
    decision = interrupt({
        "question": "是否批准删除数据库？",
        "context": state["pending_action"],
    })
    return {"approved": decision == "yes"}

workflow = StateGraph(...)
checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer)

# 第一次调用：会在 critical_decision_node 暂停
thread_id = "user-123"
config = {"configurable": {"thread_id": thread_id}}
result = app.invoke({"action": "delete_db"}, config=config)
# → 返回 {"__interrupt__": [...]}

# 人类决策后，传入决策继续
app.invoke(Command(resume="yes"), config=config)
```

我的「哪些操作需要 HITL」分类：

| 操作 | 风险 | HITL |
|---|---|---|
| 查询天气 | 低 | 不需要 |
| 写文件 | 中 | 可选 |
| 删文件 | 高 | 必须 |
| 删数据库 | 极高 | 强制 |
| 发送邮件给外部 | 高 | 必须 |
| 调用付费 API | 中 | 可选 |

经验法则：操作不可逆 + 有外部副作用 + 涉及金钱/隐私 → HITL 强制；只读 + 内部状态 → 不需要。

我自己的 agent 第一版对「删文件」也设的是可选——结果删错过 2 次（删了用户的 working 文件夹），改成「必须 HITL」后再没出过事故。HITL 问 1 次的成本（5 秒用户操作）远低于删错文件的代价。

## 优雅降级（Graceful Degradation）

关键路径失败时提供「次优但可用」的方案。我自己的降级链：

```
完整方案：Multi-Agent 调研 + 写 + 评审 → 高质量输出
降级 1：单 Agent 一次性输出 → 中等质量
降级 2：返回模板 + 占位符 → 低质量但可用
最终降级：返回 "服务暂时不可用" → 用户知道发生了什么
```

```python
def agent_pipeline(input_data):
    try:
        return full_multi_agent_pipeline(input_data)
    except TokenBudgetExceeded:
        return simplified_single_agent_pipeline(input_data)
    except Exception:
        return template_response(input_data)
```

降级不是「放弃」——是给用户一个可用的东西，总比「500 错误」强。我自己跑了一年 production agent，用户对降级输出的满意度是 65%，对 500 错误的满意度是 0%。

## 监控与告警

生产环境我盯 6 个指标：

| 指标 | 阈值 | 告警 |
|---|---|---|
| 单 session 平均循环次数 | > 5 | 关注 |
| 单 session 最大循环次数 | > 10 | 紧急 |
| 工具调用失败率 | > 10% | 关注 |
| Token 消耗 / session | > $0.5 | 关注 |
| 级联失败次数 / 小时 | > 5 | 紧急 |
| HITL 中断次数 / 小时 | 持续增长 | 关注 |

具体实现（Prometheus / Grafana / 自建 alert）见 [第 8 章 可观测性与成本](../08-observability-and-cost/)。

## 上线前 Checklist

- 每个 Agent 有 max_iterations 限制（5-10）
- 每个工具有超时（典型 30s）+ 重试（3 次指数退避）
- 关键工具有 Fallback（返回「不知道」或简化版）
- 高风险操作有 HITL 中断点
- State 有 size 限制（防止 OOM）
- 单 session 有 token budget
- 失败有日志 + trace（便于事后分析）
- 监控指标有 alert（不能「上线后才发现」）

[07. 框架横向对比](../07-framework-comparison/) 用同一需求对比 4 个主流 multi-agent 框架（LangGraph / CrewAI / AutoGen / 自研）的代码差异、调试难度、生产成熟度。
