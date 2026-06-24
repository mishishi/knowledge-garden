# 03. Tool 设计：Tool 是 LLM 的手，怎么造好这只手

> 第 2 章讲了 agent loop 怎么跑。这章讲 loop 里那个最常被低估的部分——tool 本身。Tool 设计不好，LLM 再强也发挥不出来。

## 一个真实的翻车

我 2025 年初写过一个天气 agent，tool 长这样：

```python
{
    "name": "get_weather",
    "description": "Get the weather",
    "input_schema": {
        "type": "object",
        "properties": {"location": {"type": "string"}},
        "required": ["location"]
    }
}
```

看起来没问题对吧？跑起来 LLM 调了几百次，成功率只有 41%。为啥？

第一个事故：用户问"今天冷不冷"，LLM 调 `get_weather("今天冷不冷")`——把整个自然语言当 location 传进去，API 返回 404。

第二个事故：用户问"北京和上海明天天气"，LLM 调 `get_weather("北京和上海")`——一个参数塞两个城市，API 随机返回其中一个。

第三个事故：API 偶尔超时 30 秒，LLM 把这次失败当成"weather API 不可用"，整个 loop 退化成"抱歉我没法查天气"。

三次事故根因都指向同一个问题：**tool description 没写清楚、schema 不够严格、错误信息没帮 LLM 自纠**。Tool 不是个 API endpoint——它是给 LLM 用的接口，LLM 不像人那样能"猜"。

## 社区视角：tool 设计是 first-class 工程

Anthropic 在 2024-2025 年的多篇 engineering blog 里反复强调同一个观点：tool 是 LLM 的"手和脚"，tool 设计直接决定 agent 能力上限。他们列的几条原则我基本认同：

第一，**description 不是文档，是 prompt 的一部分**——LLM 读 description 决定什么时候调、传什么参数。description 写得模糊，LLM 就乱调。Anthropic 内部 review tool 时会拿掉 description 看 LLM 是否还能合理使用——拿掉就乱用的 description 写得不够。

第二，**schema 是约束，不是建议**——`required`、`enum`、`minimum`/`maximum` 这些字段必须严格，否则 LLM 会传奇怪的值（我上面"今天冷不冷"就是反例）。Claude Code 的 tool 库大部分参数有 enum 限制或 regex pattern。

第三，**错误信息要帮 LLM 自纠**——不是"Error: 400"，而是"Error: location must be a city name in English or Chinese, got: '今天冷不冷'. Try again with just the city name."。把"怎么改"写进错误信息。

OpenAI Function Calling、Anthropic Tool Use、Google Vertex AI Function Calling——三家 schema 几乎一致（JSON Schema 子集），所以同一份 tool 定义基本能跨模型跑。但**description 风格各家略有差异**：Anthropic 偏好更详尽（因为 Claude 喜欢长 prompt），OpenAI 偏好简洁（GPT 对短 prompt 反应更好）。同一份 tool 在不同模型上要做 description 微调。

## Tool 设计的 6 条原则（我自己的版本）

翻够车之后总结的：

**1. Description 包含 3 件事——什么时候用、什么时候不用、举例**。"Use this when the user asks about current weather for a specific location. Do NOT use for forecasts (use get_forecast instead). Example: get_weather(location='Beijing') returns temperature, condition, humidity for now."

**2. 参数尽量原子化**——`location` 拆成 `city` + `country`，不传整个字符串。强制 LLM 思考每个字段。

**3. Enum 限制所有"可枚举值"**——`unit: ["celsius", "fahrenheit"]` 比 `unit: string` 好 10 倍。LLM 不会传错。

**4. 错误信息分两类**——"输入错误"（帮 LLM 自纠，返回可重试）和"系统错误"（帮 LLM 放弃或换路径，返回不可重试）。LLM 收到错误后行为完全不同。

**5. 返回结果结构化且短**——LLM 处理 200 字 JSON 比处理 2000 字 prose 稳。返回必要的 key，别 dump 整个 API response。

**6. Tool 之间正交**——不要有 `get_weather_and_forecast` 这种"全家桶" tool。LLM 不知道该用全家桶还是单独 tool，会乱选。Anthropic 内部 review 看到复合 tool 直接打回。

## 重写后的天气 tool

按上面 6 条重写：

```python
{
    "name": "get_current_weather",
    "description": (
        "Get current weather for a city NOW (not forecast). "
        "Use when user asks '现在天气' / 'today weather' / 'today temperature'. "
        "Do NOT use for forecast ('明天' / 'tomorrow' / '下周') — use get_weather_forecast instead. "
        "Example: get_current_weather(city='Beijing', unit='celsius') → "
        "{temp: 18, condition: 'sunny', humidity: 45}"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name in English or Chinese, e.g. 'Beijing' or '北京'",
                "pattern": "^[\u4e00-\u9fff]+$|^[A-Za-z\\s]+$"  # 中英文限制
            },
            "unit": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"],
                "description": "Temperature unit"
            }
        },
        "required": ["city", "unit"]
    }
}
```

重写后 LLM 调用成功率从 41% 拉到 89%。三处关键改进：

- `description` 明确说"now not forecast"——LLM 不再问"今天"时调它、问"明天"时不调它
- `city` 字段有 regex pattern 限制——LLM 传"今天冷不冷"会被 schema 直接拒绝，错误信息提示"city 必须是城市名"
- `unit` 是 enum——LLM 不会传"K"或"kelvin"这种没定义的单位

## 错误处理的完整模式

错误信息是 tool 设计里最被低估的部分。我跑了 200 个失败 case 做归类，错误大致 4 类：

```python
def execute_tool(name, args):
    try:
        result = actually_execute(name, args)
        return {"ok": True, "data": result}
    except ValidationError as e:
        # 输入错误：帮 LLM 自纠
        return {
            "ok": False,
            "type": "validation",
            "message": f"Invalid input: {e}. Correct format: <hint>. Try again.",
            "retryable": True
        }
    except RateLimitError as e:
        # 速率限制：让 LLM 等待
        return {
            "ok": False,
            "type": "rate_limit",
            "message": f"Rate limited. Wait {e.retry_after}s then retry.",
            "retryable": True,
            "wait_seconds": e.retry_after
        }
    except UpstreamError as e:
        # 上游失败：让 LLM 换路径
        return {
            "ok": False,
            "type": "upstream",
            "message": f"Upstream service unavailable: {e}. Try a different approach or fallback tool.",
            "retryable": False
        }
    except Exception as e:
        # 未知错误：让 LLM 报告用户
        return {
            "ok": False,
            "type": "unknown",
            "message": f"Unexpected error: {e}. Inform user.",
            "retryable": False
        }
```

关键设计：

- `retryable: True/False` 字段让 harness 的 retry 逻辑有依据——只有 `retryable=True` 才自动 retry，否则立刻换路径或报错给用户
- `wait_seconds` 让 harness 能 sleep 而不是 busy loop
- `type` 让 LLM 知道怎么处理（"rate_limit 等"、"upstream 换"、"validation 改输入"、"unknown 报告用户"）
- 错误信息里**永远给 LLM 一个下一步动作**——不是"出错了"，是"出错了，你应该 X"

## Retry 不是简单重试

最 naive 的 retry 是失败就重试 3 次——这在 tool 失败场景下经常更糟。Rate limit 重试 3 次只会触发更严格的限流；Validation error 重试 3 次传的还是同一份坏参数；Upstream error 重试 3 次上游还是挂。

我现在的 retry 策略：

```python
def should_retry(error_type, attempt):
    if error_type == "validation":
        return attempt < 1  # 最多 1 次——再错说明 LLM 没理解 schema
    if error_type == "rate_limit":
        return attempt < 3  # 3 次但要 exponential backoff
    if error_type == "upstream":
        return attempt < 2  # 2 次，但 LLM 应该同时尝试 fallback
    return False  # unknown 不重试
```

`validation` 只 retry 1 次——因为如果 LLM 第一次传错，错误信息已经告诉它怎么改，第二次再错就是 prompt 本身有问题，重试浪费 token。

`rate_limit` retry 3 次 + exponential backoff（1s / 4s / 16s）——上游 API 通常很快恢复。

`upstream` retry 2 次 + 同时让 LLM 试 fallback tool——比如 `get_weather` 失败就建议 LLM 用 `search_web` 搜"北京天气"。

`unknown` 不重试——立刻报错给用户。

## 并行调用：tool 同时跑多个

LLM 一次可以返回多个 tool_use block。Claude 4 和 GPT-4 都支持并行 tool call：

```python
# LLM 返回 response.content 里可能多个 tool_use
# 比如用户问"北京和上海天气"——LLM 一次返回两个 tool_use
for block in response.content:
    if block.type == "tool_use":
        # 关键：用 asyncio 并行执行
        tasks.append(execute_tool_async(block.name, block.input))
results = await asyncio.gather(*tasks, return_exceptions=True)
```

并行调用能把 multi-tool 任务的延迟从 O(N) 降到 O(1)。我跑的一个 5-tool 任务从 12 秒降到 3 秒。

但并行调用有副作用风险：

- 如果 5 个 tool 里有两个是"写文件"，并行跑可能写错顺序
- 如果有依赖（tool B 需要 tool A 的输出），并行跑就乱套
- 如果是 rate-limited API，5 个并行 = 5 倍瞬间压力

所以我的策略：

- **只读 tool**（grep / read_file / search）→ 默认并行
- **写 tool**（edit_file / write_file / rm）→ 默认串行
- **依赖链**（tool B 需要 A 输出）→ harness 检测 input schema 里的 `$ref` 引用，自动串行

```python
async def execute_tools(tool_uses):
    # 简单拓扑排序：检查 input 里有没有引用其他 tool 的输出
    sorted_uses = topological_sort(tool_uses)
    results = {}
    for use in sorted_uses:
        # 串行执行依赖链
        result = await execute_tool_async(use.name, resolve_refs(use.input, results))
        results[use.id] = result
    return results
```

## 超时是 hidden 安全网

我早期写 tool 时不加 timeout，结果一个 `sleep 999999` 的 malicious input 让整个 agent 卡 28 分钟。改后所有 tool 都强制 timeout：

```python
async def execute_tool_with_timeout(name, args, timeout=30):
    try:
        return await asyncio.wait_for(
            execute_tool_async(name, args),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        return {
            "ok": False,
            "type": "timeout",
            "message": f"Tool {name} timed out after {timeout}s. Try simpler input or different tool.",
            "retryable": False
        }
```

不同 tool 默认 timeout 不同：read_file 5 秒、search_web 15 秒、bash 30 秒、LLM call 60 秒。可以被 caller override。

## Tool 数量爆炸问题

我维护过 50+ tool 的 agent——那是噩梦。LLM 面对 50 个 tool 时选错 tool 的概率从 5 个 tool 时的 8% 涨到 30%。Schema 太多 prompt 也吃 token。

解决方法是**分群 + 动态加载**：

```python
TOOL_GROUPS = {
    "file": ["read_file", "write_file", "edit_file", "list_dir"],
    "search": ["grep", "search_web", "search_code"],
    "shell": ["bash"],
    "data": ["query_db", "query_api"],
}

def get_tools_for_task(task):
    # 用一个 lightweight LLM call 判断需要哪些 tool 组
    groups_needed = llm_call(f"Which tool groups for: {task}", options=list(TOOL_GROUPS.keys()))
    tools = []
    for g in groups_needed:
        tools.extend(TOOL_GROUPS[g])
    return tools
```

Claude Code / Cursor 都用这种模式——主 agent 不是手握所有 tool，而是按 task 动态选 tool 组。

50 个 tool 拆成 4 个 group 后，LLM 选错 tool 的概率从 30% 降回 9%，token 也省了 40%。

## 这章踩过的关键坑

**Description 不写 "Don't use when"**——LLM 不知道"什么时候不用"。description 写"Use for X" 不够，还要写"Do NOT use for Y"。我早期 tool 只有正向描述，LLM 在应该用别的 tool 的场景硬调我的 tool，结果失败。

**错误信息不带 retry 建议**——错误信息只说"出错了" 不说"怎么改"。LLM 收到错误就懵了，重试时传同样参数，浪费 3 次才放弃。

**Tool 数量一上来就堆全部**——50 个 tool 全给 LLM，selection accuracy 暴跌。必须分群 + 动态加载。

**并行调用忽略副作用**——5 个 read_file 并行 OK，5 个 write_file 并行就乱套。必须按 tool 类型区分。

**Timeout 不分 tool 类型**——bash timeout 30 秒够用，search_web 30 秒就太短。必须按 tool 设默认 timeout。

下一章 [04. Context 管理](../04-context-management/) 拆 harness 第三块基石——context window 爆了怎么 compact、怎么 cache、怎么分层。
