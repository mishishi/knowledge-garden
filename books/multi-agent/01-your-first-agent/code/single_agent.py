"""
01-your-first-agent / single_agent.py

一个能调用工具的 Agent。给它一个查询天气的问题，
它会自己决定要不要调用 get_weather 工具，然后基于工具结果回答。

运行：
    pip install -r requirements.txt
    export OPENAI_API_KEY=sk-xxx
    python single_agent.py

可替换为任何 OpenAI-compatible 接口（DeepSeek / 通义千问 / 自部署 vLLM）：
    export OPENAI_API_KEY=xxx
    export OPENAI_BASE_URL=https://api.deepseek.com/v1
"""
import json
import os

from openai import OpenAI

# ============================================================
# 1. 初始化客户端
# ============================================================
# 自动从环境变量读 OPENAI_API_KEY 和 OPENAI_BASE_URL（可选）
client = OpenAI()


# ============================================================
# 2. 定义工具
# ============================================================
# 这一段 JSON 描述"LLM 能调用什么工具"。LLM 读到这段后，
# 会自己决定要不要调、调哪个、传什么参数——它不真执行函数。
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的当前天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名，比如 'Tokyo' 或 'Beijing'",
                    }
                },
                "required": ["city"],
            },
        },
    }
]


# ============================================================
# 3. 工具实现
# ============================================================
# 这里用 mock 数据演示。生产环境换成真实 API，比如：
#   - OpenWeatherMap: https://openweathermap.org/api
#   - 和风天气: https://dev.qweather.com
def get_weather(city: str) -> str:
    """查询指定城市的当前天气（Mock）。"""
    mock_data = {
        "tokyo": "东京: 22°C, 晴, 湿度 60%, 风速 3m/s",
        "beijing": "北京: 18°C, 多云, 湿度 45%, 风速 4m/s",
        "shanghai": "上海: 20°C, 阴, 湿度 70%, 风速 5m/s",
        "new york": "New York: 15°C, 雨, 湿度 80%, 风速 6m/s",
        "london": "London: 12°C, 雾, 湿度 85%, 风速 2m/s",
    }
    key = city.lower().strip()
    if key in mock_data:
        return mock_data[key]
    return f"{city}: 暂无数据（Mock 数据库只有 tokyo/beijing/shanghai/new york/london）"


# ============================================================
# 4. Agent 主体：决策循环
# ============================================================
def run_agent(user_message: str, model: str = "gpt-4o-mini") -> str:
    """
    Agent 核心循环：
        LLM 决策 →（如果要调工具）执行工具 → 把结果反馈给 LLM → 循环
        直到 LLM 不再调工具，输出最终答案。

    这就是单 Agent 的全部——没有更复杂的机制了。
    """
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个天气助手。用户问天气时，调用 get_weather 工具获取准确数据，"
                "不要凭印象编造。如果工具没返回数据，老实说'没查到'。"
            ),
        },
        {"role": "user", "content": user_message},
    ]

    print(f"\n{'=' * 60}")
    print(f"[用户] {user_message}")

    # 循环：LLM 每轮可以调 0~N 个工具。我们最多跑 5 轮防死循环。
    for round_idx in range(5):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
        )
        msg = response.choices[0].message

        # 情况 1：LLM 想调工具
        if msg.tool_calls:
            print(f"\n[第 {round_idx + 1} 轮] Agent 决定调 {len(msg.tool_calls)} 个工具")
            # 必须把 LLM 的"决定"加进对话历史——这是 OpenAI API 的协议要求
            messages.append(msg)

            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)

                if fn_name == "get_weather":
                    print(f"  → 调用 {fn_name}({fn_args})")
                    result = get_weather(fn_args["city"])
                    print(f"  ← 返回: {result}")
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result,
                        }
                    )
                else:
                    # 理论上不会发生——LLM 只会调我们声明的工具
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": f"错误：未知工具 {fn_name}",
                        }
                    )

            # 继续下一轮：让 LLM 基于工具结果决定下一步
            continue

        # 情况 2：LLM 直接给出最终答案
        print(f"\n[Agent 回答] {msg.content}")
        return msg.content

    # 5 轮还没结束——很可能死循环了
    return "[警告] Agent 跑了 5 轮还没结束，强制终止。请检查 prompt 或工具定义。"


# ============================================================
# 5. Demo
# ============================================================
if __name__ == "__main__":
    # Demo 1：需要调工具的查询
    run_agent("东京今天天气怎么样？")

    # Demo 2：换一座城市
    run_agent("北京呢？顺便告诉我上海。")

    # Demo 3：不需要调工具的问题——Agent 应该不调工具，直接回答
    run_agent("你好，请用一句话介绍你自己。")

    # Demo 4：调用一个 mock 库里没有的城市
    run_agent("火星天气怎么样？")