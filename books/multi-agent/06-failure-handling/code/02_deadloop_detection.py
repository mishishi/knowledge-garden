"""
06-failure-handling / 02_deadloop_detection.py

死循环检测演示：3 重保险（max_iterations + watchdog + cost budget）。

运行：
    export OPENAI_API_KEY=sk-xxx
    python 02_deadloop_detection.py
"""
import os

from openai import OpenAI

client = OpenAI()


# ============================================================
# 一个会死循环的 Agent（演示用，故意有 bug）
# ============================================================
def run_deadloop_prone_agent(user_message: str) -> str:
    """故意没加防御的版本：可能死循环"""
    messages = [{"role": "user", "content": user_message}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "useless_search",
                "description": "搜索关键词（永远返回'没找到'）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"],
                },
            },
        }
    ]

    # 没有 max_iterations 限制 → 可能死循环
    while True:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools,
        )
        msg = response.choices[0].message

        if msg.tool_calls:
            # LLM 每次都说"再搜一次看看" → 死循环
            messages.append(msg)
            messages.append({
                "role": "tool",
                "tool_call_id": msg.tool_calls[0].id,
                "content": "没找到",
            })
            continue

        return msg.content


# ============================================================
# 防御版：3 重保险
# ============================================================
def run_protected_agent(user_message: str) -> str:
    """加了 3 重保险的版本"""
    MAX_ITERATIONS = 10  # 保险 1
    WATCHDOG_THRESHOLD = 3  # 保险 2
    TOKEN_BUDGET = 30_000  # 保险 3

    messages = [{"role": "user", "content": user_message}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "useless_search",
                "description": "搜索关键词",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        }
    ]

    recent_tool_calls = []
    total_tokens = 0

    for round_idx in range(MAX_ITERATIONS):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools,
        )
        msg = response.choices[0].message

        # 更新 token 计数
        if response.usage:
            total_tokens += response.usage.total_tokens

        # 保险 3 检查
        if total_tokens > TOKEN_BUDGET:
            return f"[强制终止] 超过 token 预算 ({total_tokens} > {TOKEN_BUDGET})"

        if msg.tool_calls:
            tool_call_signature = msg.tool_calls[0].function.name + str(msg.tool_calls[0].function.arguments)

            # 保险 2 检查
            recent_tool_calls.append(tool_call_signature)
            if len(recent_tool_calls) > WATCHDOG_THRESHOLD:
                recent_tool_calls.pop(0)
            if len(set(recent_tool_calls)) == 1 and len(recent_tool_calls) == WATCHDOG_THRESHOLD:
                return f"[强制终止] 检测到重复调用同一个工具"

            messages.append(msg)
            messages.append({
                "role": "tool",
                "tool_call_id": msg.tool_calls[0].id,
                "content": "没找到",
            })
            continue

        return msg.content

    # 保险 1 触发
    return f"[强制终止] 超过最大循环次数 ({MAX_ITERATIONS})"


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "protected"

    if mode == "dangerous":
        print("=" * 60)
        print("危险版：无防御（Ctrl+C 手动终止）")
        print("=" * 60)
        try:
            result = run_deadloop_prone_agent("搜索 Multi-Agent")
            print(result)
        except KeyboardInterrupt:
            print("\n[手动终止]")

    elif mode == "protected":
        print("=" * 60)
        print("保护版：3 重保险")
        print("=" * 60)
        result = run_protected_agent("搜索 Multi-Agent")
        print(result)
        print("\nAgent 在第 3 次重复调用时被 watchdog 终止")