# 06. 失败的艺术

> Multi-Agent 系统的失败是单 Agent 的 N 倍（N = Agent 数量）。本章系统讲**失败的分类 + 防御模式**——这是从 demo 走向生产的关键一步。

## 这一章要回答的问题

1. Multi-Agent 系统有哪些失败模式？
2. 怎么检测和防止 Agent 死循环？
3. 一个 Agent 失败时，怎么防止拖垮整个系统？
4. 关键决策时，怎么让人介入？

---

## 失败分类

```
┌─ Agent 自身失败
│   ├─ LLM 输出 malformed（JSON 格式错、字段缺失）
│   ├─ LLM 调用超时
│   ├─ LLM 输出违反 prompt 约束（比如"必须基于事实"但它编了）
│   └─ Agent 死循环（反复调同一个工具不结束）
│
├─ 工具失败
│   ├─ 工具超时
│   ├─ 工具返回错误
│   ├─ 工具不可用（API 限流、服务挂）
│   └─ 工具鉴权失败
│
├─ 通信失败
│   ├─ 上游 Agent 输出格式不对（下游解析失败）
│   ├─ 状态丢失（共享 State 被意外清空）
│   └─ 消息过大（超过 context 窗口）
│
└─ 系统级失败
    ├─ Token 烧光（成本失控）
    ├─ 死循环导致无限次 LLM 调用
    ├─ 级联失败（一个 Agent 挂，所有下游挂）
    └─ 时延过高（用户体验差）
```

完整代码：[`code/01_failure_classification.py`](./code/01_failure_classification.py)

---

## 防御 1：死循环检测

**症状**：Agent 反复调同一个工具，LLM 每次都觉得"还需要再调一次"，永远不结束。

### 3 重保险

```
保险 1：max_iterations
└─ 限制 Agent 最大循环次数（典型：5-10 次）

保险 2：Watchdog
└─ 检测重复模式（同样的 tool call 出现 N 次，强制终止）

保险 3：Cost Budget
└─ 限制单次 session 最大 token 消耗
```

完整代码：[`code/02_deadloop_detection.py`](./code/02_deadloop_detection.py)

### 关键代码模式

```python
# 保险 1: max_iterations
MAX_ITERATIONS = 10

for round_idx in range(MAX_ITERATIONS):
    # ... Agent 决策
    if finished:
        break
else:
    return "[强制终止] 超过最大循环次数"

# 保险 2: Watchdog
recent_tool_calls = []
WATCHDOG_THRESHOLD = 3

for round_idx in range(MAX_ITERATIONS):
    tool_call = agent.decide()
    
    recent_tool_calls.append(tool_call)
    if len(recent_tool_calls) > WATCHDOG_THRESHOLD:
        recent_tool_calls.pop(0)
    
    if len(set(recent_tool_calls)) == 1:  # 全部相同
        return "[强制终止] 检测到重复调用"

# 保险 3: Cost Budget
TOTAL_TOKEN_BUDGET = 50_000
used_tokens = 0

for round_idx in range(MAX_ITERATIONS):
    response = llm.call(...)
    used_tokens += response.usage.total_tokens
    
    if used_tokens > TOTAL_TOKEN_BUDGET:
        return "[强制终止] 超过 token 预算"
```

---

## 防御 2：超时与重试

**症状**：工具调用卡住，整个 Agent 链路等待。

### 工具层指数退避

```python
import time
from functools import wraps


def retry_with_backoff(max_retries=3, base_delay=1.0):
    """指数退避重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    delay = base_delay * (2 ** attempt)
                    print(f"重试 {attempt + 1}/{max_retries}，等待 {delay}s...")
                    time.sleep(delay)
        return wrapper
    return decorator
```

完整代码：[`code/03_tool_retry.py`](./code/03_tool_retry.py)

### Agent 层 Fallback

工具彻底失败时，Agent 应该有 fallback 策略：

```python
def get_weather_with_fallback(city: str) -> str:
    try:
        return primary_weather_api(city)
    except Exception:
        # Fallback 1: 用另一个 API
        try:
            return secondary_weather_api(city)
        except Exception:
            # Fallback 2: 返回"不知道"，但要诚实
            return f"{city} 的天气暂时无法查询，请稍后再试"
```

**关键原则**：不要让 LLM 猜，宁可让 Agent 说"不知道"。

---

## 防御 3：级联失败隔离

**症状**：一个 Agent 失败，下游全挂（比如 5 个 Agent 链路，第 3 个挂了，4 和 5 永远等不到输入）。

### 模式 A：Circuit Breaker（断路器）

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

### 模式 B：Partial Failure

不要"All or Nothing"——部分成功就部分返回。

```python
def multi_step_pipeline(steps):
    results = {}
    for step_name, step_func in steps.items():
        try:
            results[step_name] = step_func()
        except Exception as e:
            results[step_name] = {"error": str(e), "skipped": True}
            # 继续下一步，不中断整个 pipeline
    return results
```

完整代码：[`code/04_cascading_failure.py`](./code/04_cascading_failure.py)

---

## 防御 4：人机协同（Human-in-the-Loop）

**场景**：关键决策卡点让人类介入，避免 LLM 自主决定高风险操作。

### LangGraph 的 interrupt

```python
from langgraph.checkpoint import MemorySaver
from langgraph.graph import StateGraph
from langgraph.prebuilt import interrupt


def critical_decision_node(state):
    """关键决策：暂停，让人类介入"""
    decision = interrupt(
        {
            "question": "是否批准删除数据库？",
            "context": state["pending_action"],
        }
    )
    return {"approved": decision == "yes"}


# 配合 checkpointer 实现"暂停-恢复"
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
# → 继续执行，根据决策决定下一步
```

完整代码：[`code/05_human_in_loop.py`](./code/05_human_in_loop.py)

### 哪些决策需要 HITL？

| 操作 | 风险 | HITL |
|------|------|------|
| 查询天气 | 低 | ❌ 不需要 |
| 写文件 | 中 | ⚠️ 可选 |
| 删文件 | 高 | ✅ 必须 |
| 删数据库 | 极高 | ✅ 强制 |
| 发送邮件给外部 | 高 | ✅ 必须 |
| 调用付费 API | 中 | ⚠️ 可选 |

---

## 优雅降级（Graceful Degradation）

**原则**：关键路径失败时，提供"次优但可用"的方案。

```
完整方案：Multi-Agent 调研 + 写 + 评审 → 高质量输出
降级方案 1：单 Agent 一次性输出 → 中等质量
降级方案 2：返回模板 + 占位符 → 低质量但可用
最终降级：返回 "服务暂时不可用" → 用户知道发生了什么
```

实现：

```python
def agent_pipeline(input_data):
    try:
        return full_multi_agent_pipeline(input_data)
    except TokenBudgetExceeded:
        return simplified_single_agent_pipeline(input_data)
    except Exception:
        return template_response(input_data)
```

---

## 监控与告警

生产环境的失败监控指标：

| 指标 | 阈值 | 告警 |
|------|------|------|
| 单 session 平均循环次数 | > 5 | ⚠️ |
| 单 session 最大循环次数 | > 10 | 🔴 |
| 工具调用失败率 | > 10% | ⚠️ |
| Token 消耗 / session | > $0.5 | ⚠️ |
| 级联失败次数 / 小时 | > 5 | 🔴 |
| HITL 中断次数 / 小时 | 持续增长 | ⚠️ |

监控集成见 [第 8 章 可观测性与成本](../08-observability-and-cost/)。

---

## 本章小结

- 失败分类：**Agent / 工具 / 通信 / 系统** 四类
- 死循环防御：**max_iterations + watchdog + cost budget** 三重保险
- 超时重试：**指数退避 + Fallback**
- 级联失败：**Circuit Breaker + Partial Failure**
- 关键决策：**Human-in-the-Loop**
- 降级策略：**多级 Fallback**

## 下篇

[07. 框架横向对比](../07-framework-comparison/) —— 用同一需求对比 4 个主流框架的代码风格、调试难度、生产成熟度。

## 生产化提示

失败处理的工程化 Checklist：

- [ ] 每个 Agent 有 max_iterations 限制（5-10）
- [ ] 每个工具有超时（典型 30s）+ 重试（3 次指数退避）
- [ ] 关键工具有 Fallback（返回"不知道"或简化版）
- [ ] 高风险操作有 HITL 中断点
- [ ] State 有 size 限制（防止 OOM）
- [ ] 单 session 有 token budget
- [ ] 失败有日志 + trace（便于事后分析）