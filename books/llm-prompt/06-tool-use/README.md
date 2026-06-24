# 06. Tool Use / Function Calling

> Tool use 是 2024-2026 LLM 最关键的能力——让 LLM 从「聊天机器人」升级成「能调 API 的 Agent」。这章讲单 tool / 多 tool / parallel / 错误重试 + 客服 agent 完整案例。

## Tool Use 是什么

**Tool use = LLM 自己决定调哪个函数 + 传什么参数**。

```python
# 工具定义
@tool
def get_weather(city: str) -> str:
    """查询指定城市的天气"""
    return f"{city}: 22°C, 晴"

# 用户问
"北京天气怎么样？"

# LLM 决定：调用 get_weather(city="北京")
# 框架执行函数，把结果喂回 LLM
# LLM 输出："北京今天 22°C 晴"
```

**关键点**：LLM 不是直接调函数——它生成「调用意图」（函数名 + 参数），框架负责执行，再把结果返回 LLM。

## Tool 定义 4 大要素

每个 tool 必须有 4 个要素：

```
1. 名字：clear 名字（get_weather / search_docs / send_email）
2. 描述：LLM 看的「这个工具做什么」（决定调不调）
3. 参数：类型 + 描述（决定怎么填）
4. 返回：函数实现
```

### OpenAI 写法

```python
import openai

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的当前天气。返回温度和天气状况。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名，如 '北京' / '上海' / 'tokyo'",
                    },
                },
                "required": ["city"],
            },
        },
    }
]
```

**description 是 LLM 决定调不调的关键**——写「查询城市天气」不如写「查询指定城市的当前温度和天气状况，用于回答用户天气问题」。

### Claude 写法

```python
import anthropic

tools = [
    {
        "name": "get_weather",
        "description": "查询指定城市的当前天气。返回温度和天气状况。",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名，如 '北京' / '上海'",
                },
            },
            "required": ["city"],
        },
    }
]
```

**区别**：Claude 用 `input_schema` 而不是 `parameters`；其余结构类似。

### 用 Pydantic 自动生成 schema

```python
from pydantic import BaseModel, Field


class GetWeatherInput(BaseModel):
    """查询指定城市的当前天气。返回温度和天气状况。"""
    city: str = Field(..., description="城市名，如 '北京'")


# 自动生成 OpenAI tool schema
tool_schema = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": GetWeatherInput.__doc__,
        "parameters": GetWeatherInput.model_json_schema(),
    },
}
```

**好处**：schema 和函数实现同源，不会写错。

## 完整 Tool Use 循环

```python
import openai
import json
from typing import List, Dict, Callable


def run_conversation(user_message: str, tools: List[dict], tool_functions: Dict[str, Callable]):
    """完整的 tool use 循环"""
    messages = [{"role": "user", "content": user_message}]

    while True:
        # 1. 调 LLM
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
        )

        message = response.choices[0].message

        # 2. 如果 LLM 想调 tool
        if message.tool_calls:
            # 把 LLM 的 tool_calls 加到 messages
            messages.append(message)

            # 3. 执行每个 tool
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                # 调函数
                if function_name in tool_functions:
                    try:
                        result = tool_functions[function_name](**function_args)
                    except Exception as e:
                        result = f"Error: {e}"

                    # 4. 把结果加到 messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result),
                    })

            # 5. 继续循环，让 LLM 看到 tool 结果后给最终回答

        else:
            # 6. LLM 不调 tool，给最终回答
            return message.content
```

**关键点**：
- 循环直到 LLM 不再调 tool（最终回答）
- tool 结果通过 `role: "tool"` 加回 messages
- tool_call_id 必须对应（多 tool 并行时区分）

## 单 Tool vs 多 Tool

### 单 tool

```python
tools = [{"type": "function", "function": {"name": "search", ...}}]
```

**适合**：任务清晰、只需要 1 个能力。

### 多 tool

```python
tools = [
    {"type": "function", "function": {"name": "search", ...}},
    {"type": "function", "function": {"name": "get_weather", ...}},
    {"type": "function", "function": {"name": "calculate", ...}},
    {"type": "function", "function": {"name": "send_email", ...}},
]
```

**LLM 怎么选**：看每个 tool 的 description 决定调哪个。

**坑**：tool 越多，token 越多。**5 个 tool 已经够用，超过 10 个 LLM 选择能力下降**。

实测（OpenAI）：
- 1-5 tool：选择准确率 95%+
- 5-10 tool：90%
- 10-20 tool：80%
- 20+ tool：< 70%

**建议**：按 domain 分组，多 Agent，每个 Agent ≤ 5 tool。

## Parallel Tool Calls

LLM 可以在 1 次 response 里调**多个 tool 并行**：

```python
# 用户问
"北京和上海今天天气怎么样？"

# LLM 在 1 次 response 里调 2 个 tool
tool_calls = [
    {"function": {"name": "get_weather", "arguments": '{"city": "北京"}'}},
    {"function": {"name": "get_weather", "arguments": '{"city": "上海"}'}},
]
```

**OpenAI 默认开启 parallel tool calls**。要关掉：

```python
response = openai.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    tools=tools,
    parallel_tool_calls=False,   # ← 强制串行
)
```

**Claude 也支持 parallel**——在 content block 里多个 tool_use 块。

**节省时间**：并行 tool 节省 N 倍延迟（不是 N 倍 token）。

## 错误处理

LLM 调 tool 经常出错：

```python
# 1. 必填参数没填
{"function": {"name": "get_weather", "arguments": "{}"}}   # 缺 city

# 2. 参数类型错
{"function": {"name": "get_weather", "arguments": '{"city": 123}'}}   # city 应该是 string

# 3. 业务错误
{"function": {"name": "send_email", "arguments": '{"to": "invalid-email"}'}}

# 4. Tool 内部异常
{"function": {"name": "search", "arguments": '{"query": "X"}'}}  → search() 抛 ConnectionError
```

### 错误处理模式

```python
def safe_tool_call(name: str, args: dict, tool_functions: dict) -> str:
    """带错误处理的 tool call"""
    try:
        # 1. 参数校验
        func = tool_functions.get(name)
        if func is None:
            return f"Error: Tool '{name}' 不存在"

        # 2. 执行
        result = func(**args)
        return str(result)
    except TypeError as e:
        # 参数错
        return f"Error: 参数错: {e}"
    except Exception as e:
        # 业务错
        return f"Error: {type(e).__name__}: {e}"
```

**把错误信息喂回 LLM**——LLM 看到错误会修正重试。

### 重试策略

```python
MAX_RETRIES = 3

def run_with_retry(messages, tools, tool_functions, max_retries=MAX_RETRIES):
    for attempt in range(max_retries):
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
        )

        message = response.choices[0].message

        if not message.tool_calls:
            return message.content

        # 执行 tool，把结果（成功或失败）加回
        messages.append(message)
        for tool_call in message.tool_calls:
            args = json.loads(tool_call.function.arguments)
            result = safe_tool_call(
                tool_call.function.name, args, tool_functions
            )
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    # 重试完 LLM 还调 tool，强制结束
    return llm.summarize(messages)  # 让 LLM 总结当前状态
```

**重试太多 = token 爆炸**。3 次是经验值。

## 实战：客服 Agent 完整案例

```python
import openai
import json
from typing import List, Dict, Callable, Optional


# ========== 工具定义 ==========
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "查询订单状态。需要订单 ID。返回：订单状态、物流单号、预计到达时间。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "订单 ID 字符串"},
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "initiate_refund",
            "description": "发起退款申请。需要订单 ID 和退款原因。返回：退款工单号。**仅用于 7 天内无理由退货**。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "reason": {"type": "string", "description": "退款原因（质量问题 / 不想要了 / 收到错的）"},
                },
                "required": ["order_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_to_human",
            "description": "转人工客服。用于：客户情绪激动、要求主管介入、涉及账号安全问题、用户明确要求。",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "转人工原因"},
                },
                "required": ["reason"],
            },
        },
    },
]


# ========== 工具实现（mock）==========
def get_order_status(order_id: str) -> str:
    # 真实实现调订单系统
    return json.dumps({
        "order_id": order_id,
        "status": "shipped",
        "tracking": "SF1234567890",
        "eta": "2026-06-26",
    })


def initiate_refund(order_id: str, reason: str) -> str:
    # 真实实现调支付系统
    return json.dumps({
        "refund_ticket": "RF" + order_id,
        "estimated_arrival": "3-5 business days",
    })


def transfer_to_human(reason: str) -> str:
    return json.dumps({
        "transferred": True,
        "human_agent": "agent_007",
        "queue_position": 3,
    })


TOOL_FUNCTIONS = {
    "get_order_status": get_order_status,
    "initiate_refund": initiate_refund,
    "transfer_to_human": transfer_to_human,
}


# ========== Agent 循环 ==========
def customer_service_agent(user_message: str) -> str:
    SYSTEM_PROMPT = """
你是 Acme 电商资深客服，5 年售后经验。
- 用「您」不用「你」
- 先共情再解决
- 涉及退款先用 get_order_status 查订单
- 客户情绪激动立刻 transfer_to_human
"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    for _ in range(5):  # 最多 5 轮 tool 调用
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=TOOLS,
        )

        message = response.choices[0].message

        if not message.tool_calls:
            return message.content

        messages.append(message)

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            result = safe_tool_call(name, args, TOOL_FUNCTIONS)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    return "抱歉，处理超时，请稍后重试"


# ========== 测试 ==========
test_queries = [
    "我的订单 ABC123 现在什么状态？",
    "我想退款，订单 ABC123，产品有质量问题",
    "你们这是什么破服务！我要投诉！",
]

for q in test_queries:
    print(f"用户: {q}")
    print(f"客服: {customer_service_agent(q)}\n")
```

**3 个 query 触发 3 个不同 tool 链**：
- 订单查询 → get_order_status
- 退款 → get_order_status + initiate_refund
- 投诉 → transfer_to_human

## 4 大反模式

### 反模式 1：Tool description 写「做什么」不写「什么时候用」

```python
# 错
{"description": "查询数据库"}

# 对
{"description": "查询订单状态。当用户问订单相关问题时调用。返回状态、物流、ETA。"}
```

LLM 决定调不调**主要看 description**。

### 反模式 2：Tool 返回太多信息

```python
# 错：返回整个数据库行
def get_user_info(user_id):
    return db.execute(f"SELECT * FROM users WHERE id={user_id}")   # 100 字段

# 对：只返回 LLM 需要的
def get_user_basic_info(user_id):
    return {"name": "...", "email": "...", "tier": "..."}
```

**tool 返回 = 喂回 LLM 的 context**。返回 10K token 会爆。

### 反模式 3：Tool 没验证参数

```python
# 错
def send_email(to: str, subject: str, body: str):
    smtp.send(to, subject, body)   # to 可能是无效邮箱

# 对
def send_email(to: str, subject: str, body: str):
    if "@" not in to:
        raise ValueError(f"Invalid email: {to}")
    if len(subject) > 200:
        raise ValueError("Subject too long")
    smtp.send(to, subject, body)
```

LLM 经常填错参数（特别是 enum / 邮箱 / 数字范围）——**tool 自己也要校验**。

### 反模式 4：Tool 太多没分组

```python
# 错：1 个 Agent 30 个 tool
tools = [search, weather, calendar, email, slack, jira, ...]  # 30 个

# 对：按 domain 分 Agent
class CustomerServiceAgent:
    tools = [get_order, get_refund, transfer_human]   # 3 个

class SalesAgent:
    tools = [get_catalog, create_quote, send_proposal]   # 3 个
```

## 4 大实战技巧

### 技巧 1：Tool 返回结构化 JSON

```python
# 错：返回字符串
def get_user(user_id: str) -> str:
    return f"用户 {user_id}，VIP"

# 对：返回 JSON 字符串（LLM 容易解析）
def get_user(user_id: str) -> str:
    return json.dumps({"id": user_id, "tier": "VIP", "name": "..."})
```

### 技巧 2：错误信息要可操作

```python
# 错
except Exception as e:
    return f"Error: {e}"   # LLM 不知道怎么改

# 对
except ValueError as e:
    return f"Validation error: {e}. Required format: YYYY-MM-DD."
except Exception as e:
    return f"Tool error: {type(e).__name__}. Try alternative approach or transfer to human."
```

### 技巧 3：长时间 Tool 加 timeout

```python
import signal


def with_timeout(func, args, timeout_seconds=30):
    def handler(signum, frame):
        raise TimeoutError("Tool timeout")

    signal.signal(signal.SIGALRM, handler)
    signal.alarm(timeout_seconds)
    try:
        return func(**args)
    finally:
        signal.alarm(0)


def safe_tool_call(name, args, tool_functions):
    try:
        return with_timeout(tool_functions[name], args, timeout_seconds=30)
    except TimeoutError:
        return f"Error: Tool '{name}' timeout after 30s"
```

### 技巧 4：Tool 嵌套（Tool 调 Tool）

```python
# 让 Agent 调一个 tool，内部自动调多个 sub-tool
def comprehensive_search(query: str) -> str:
    """综合搜索：先查 DB，再查 API，最后查 cache"""
    db_result = search_db(query)
    api_result = search_api(query)
    cache_result = search_cache(query)
    return combine_results(db_result, api_result, cache_result)
```

**LLM 调 1 个 tool，内部完成多步**——减少 LLM 决策次数。

## 跑不起来的常见坑

**坑 1：Tool 描述英文写，但 user 用中文问**

```python
# 错
{"name": "get_weather", "description": "Get weather for a city"}

# 用户问
"北京天气怎么样？"
# LLM 可能不调（没识别到「天气」对应「get_weather」）

# 对
{"name": "get_weather", "description": "查询指定城市的天气。用户问天气、气温、是否下雨时调用。"}
```

**坑 2：Tool 互相依赖没文档说明**

```python
# 错：LLM 不知道要先调 A 再调 B
tools = [
    {"name": "get_user", ...},
    {"name": "get_user_orders", ...},   # 需要 user_id，但没说从哪来
]

# 对：在 description 里写依赖
{"name": "get_user_orders",
 "description": "查询用户订单。需要 user_id（先调 get_user 拿到）。返回订单列表。"}
```

**坑 3：Tool 返回太大撑爆 context**

```python
def search_docs(query: str) -> str:
    # 错：返回 100 篇文章
    return "\n".join([f.read() for f in search_files(query)])  # 1M token

# 对：返回 top 3 摘要
def search_docs(query: str) -> str:
    results = search_files(query)[:3]
    return "\n".join([r.summary for r in results])
```

**坑 4：Tool 内部再调 LLM**

```python
# 错：tool 里又调 LLM
def summarize(text: str) -> str:
    return llm.call(f"summarize: {text}")  # 嵌套 LLM call
# 调试噩梦 + token 爆炸

# 对：让 LLM 自己总结，tool 不调 LLM
def get_summary_placeholder(text: str) -> str:
    return "[Tool returns raw text, LLM will summarize in next step]"
```

## 这章跑完之后你该会什么

- Tool Use 4 大要素 + 完整循环
- OpenAI / Claude 写法差异
- Pydantic 自动生成 schema
- 单 tool / 多 tool / parallel 选择
- 错误处理 + 重试策略
- 客服 Agent 完整实战（3 tool 链 + 5 轮循环）
- 4 大反模式 + 4 大实战技巧
- 4 大常见坑

## 下篇

[07. Prompt Caching](../07-prompt-caching/) — 降成本 10x 的方法 + 怎么写 prompt 最大化 cache 命中。
