"""
08-observability-and-cost / 04_token_budget.py

Token 预算强制：单 session 不能超过预算。

运行：
    export OPENAI_API_KEY=sk-xxx
    python 04_token_budget.py
"""
import os

from openai import OpenAI

client = OpenAI()


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

    def remaining(self) -> int:
        return self.max - self.used


def run_with_budget(user_message: str, budget_tokens: int = 5000) -> str:
    """带预算的 Agent 调用"""
    budget = TokenBudget(max_tokens=budget_tokens)
    messages = [{"role": "user", "content": user_message}]

    print(f"\n[开始] 预算: {budget_tokens} tokens")

    for round_idx in range(10):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        tokens_used = response.usage.total_tokens if response.usage else 0

        print(f"  第 {round_idx + 1} 轮: 用 {tokens_used} tokens (累计 {budget.used + tokens_used}/{budget_tokens})")

        if not budget.consume(tokens_used):
            return f"[预算耗尽] 第 {round_idx + 1} 轮终止"

        return response.choices[0].message.content

    return "[循环结束]"


if __name__ == "__main__":
    print("=" * 60)
    print("Token 预算演示")
    print("=" * 60)

    # 小预算：够用
    print("\n--- 场景 1: 5000 tokens 预算 ---")
    result = run_with_budget("用一句话介绍 Multi-Agent", budget_tokens=5000)
    print(f"结果: {result}")

    # 大预算：够用
    print("\n--- 场景 2: 10000 tokens 预算 ---")
    result = run_with_budget("调研 Multi-Agent 并写 100 字短文", budget_tokens=10000)
    print(f"结果: {result}")