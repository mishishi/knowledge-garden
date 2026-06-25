# 09. 工具调用省钱模式

prompt 和 model 选对了，账单砍 70%。但**工具调用本身**是另一个 cost center，我之前没意识。

agent 一个 task 里调 3-5 个 tool 很常见。每个 tool call：
- 把 tool schema 塞进 prompt（input）
- 模型生成 tool name + arguments（output）
- tool 执行，把 result 塞回 prompt（input again）
- 模型再生成下一步

一个"查 3 个 URL"的简单 task，token 走 4-5 轮 LLM + 3 轮 tool。**token 成本是纯 LLM 调用的 3-4 倍**。

我 review 之后从 5 件事里抠出 $35/月。

## 1. Parallel tool calls

agent 框架（OpenAI function calling、CrewAI、LangGraph）都支持同轮调多个 tool。但你**显式鼓励** model 用，model 才会用。

```python
# 系统 prompt 里加一行
"如果你需要查多个 URL 或者做多个独立操作，把它们列出来一起调用，不要一个一个来。"
```

模型在 90% 场景下会响应，把 3 个 sequential tool call 合并成 1 round。

```python
# 之前 (sequential):
fetch(url_a)  # round 1
fetch(url_b)  # round 2
fetch(url_c)  # round 3
# 3 轮 LLM + 3 轮 tool

# 之后 (parallel):
fetch([url_a, url_b, url_c])  # 1 轮
# 1 轮 LLM + 1 轮 tool
```

**省 60% 工具 task 的 token**。因为我那个 agent 1/3 的 task 是"查 X 查 Y 查 Z"，影响大。

## 2. Batched tool calls

有些 tool 一次能处理多个输入，但 model 默认是逐个调。

我有个 `search(query)` tool。一次能处理 5 个 query 返回 5 个 result。但 model 看到"查 X"会调一次 `search(X)`，再看到"查 Y"再调一次。

我加了 system prompt 暗示：

```
如果有多个独立 query 需要 search，把它们合并到一次调用：
search(["query1", "query2", "query3"]) 而不是 search("query1"); search("query2")。
```

实际效果：模型从 5 次 `search("单个")` 变成 1 次 `search([5 个])`。**token 省 70%**。

通用 pattern：**任何"一次能处理 N 个"的 tool，在 system prompt 里明确说"用 N 个一起"**。

## 3. Tool result truncation

tool 返回结果塞回 prompt 时常常太大。我那个 `search` tool 单次返回 8000 token（包括完整文档），但模型只需要 title + 200 token 摘要。

```python
def truncated_tool_result(result, max_tokens=500):
    # 用 mini 总结
    summary = call_llm(
        f"用 {max_tokens} token 总结以下内容的关键信息：\n{result}",
        model="gpt-4o-mini",
    )
    return summary
```

但这本身也花钱（mini 0.5K input + 0.3K output = $0.00004）。**只有当 truncation 节省的 token > 总结成本时才用**。

经验：tool result 超过 2000 token 才值得 truncate。小的直接发。

**省 30% 输入 token**。我的 agent 一个月 $30 左右的 input 是从这来的。

## 4. Speculative pre-fetch

有时候 agent 在"思考"下一步时会调一些"很可能需要"的 tool。比如它在准备回答"对比 A 和 B"，会先调 `get_a()` 和 `get_b()`，再调 `compare(a, b)`。

**预取是好的**，但**不要 over-fetch**。model 有时候会调一堆用不上的 tool（"以防万一"）。

```python
def tool_call_with_budget(agent_state, max_calls=5):
    """限制单 task 的 tool call 总数"""
    if agent_state.tool_calls > max_calls:
        return ToolResult(
            error="tool budget exceeded, summarize what you have"
        )
```

我那个 agent 之前平均 7-9 tool call/task，加了这个限到 5 个。**质量 -2%，成本 -25%**。

过度调用 tool 的另一面是 model 自己也累——tool 结果越多 context 越长，model 后续决策越不准。**限制 tool call 数同时省 token 又提质量**。

## 5. Tool schema minimization

每个 tool 的 schema 都会塞进 prompt。如果有 10 个 tool，每个 tool 200 token 的 schema = 2000 token context，**每个 call 都付**。

优化：

- **删掉不用或很少用的 tool**。agent 框架鼓励"tool 越多越好"，实际是 token 灾难。
- **tool schema 写得紧凑**。description 用一行而不是一段。parameters 用 oneOf 而不是嵌套。
- **动态 tool 加载**。让 model 先决定要哪类 tool，再加载那 2-3 个具体 tool。`tool_registry.filter(category="search")` 比 `tool_registry.all()` 省 80%。

我精简 tool 描述前后：tool schema 总 2000 → 600 token。**省 70% tool schema cost**。

## 真实成本：tool heavy task 拆解

我那个 agent 一个月 27K call，其中 8K call 调 tool（30%）。**这 8K call 平均每个 5K input + 800 output = $0.014**（按 4o 价格）。**$112/月**。

优化后（5 件事全上）：

| 优化 | 节省 |
|---|---|
| Parallel | 30% |
| Batched | 25% |
| Truncation | 15% |
| Pre-fetch budget | 25% |
| Schema minimization | 20% |

**总节省 50%**。$112 → $56。**省 $56/月**。

不是所有优化都对你适用。我的 agent 偏 tool heavy（research 场景），如果是 conversational agent 工具调用少，这章的 ROI 没那么高。**但 conversational agent 的 prompt 优化 ROI 更高（看 ch05）**。

## 写一个 tool cost dashboard

如果你想知道 tool call 实际花多少，最简单的：

```python
def instrument_tool_call(tool_name, args, result):
    cost = estimate_cost(args, result)  # 用 token 估算
    log_to_db({
        "tool": tool_name,
        "cost": cost,
        "timestamp": time.time(),
        "user_id": current_user.id,
    })
```

每周跑一次：

```sql
SELECT tool_name, COUNT(*), SUM(cost), AVG(cost)
FROM tool_calls
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY tool_name
ORDER BY SUM(cost) DESC;
```

你会发现**80% 的 tool cost 来自 20% 的 tool**。把这 20% 优化掉收益最大。

下一章是最后一章——把这些数据汇总成一个 cost dashboard，让你不用每周手写 SQL 也能看见。
