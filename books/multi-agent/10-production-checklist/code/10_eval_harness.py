"""
10-production-checklist / 10_eval_harness.py

评估函数：用 LLM 评估 Agent 输出的质量。

运行：
    export OPENAI_API_KEY=sk-xxx
    python 10_eval_harness.py
"""
import os

from openai import OpenAI

client = OpenAI()


def evaluate_quality(output: str, criteria: str) -> dict:
    """用 LLM 评估输出质量"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "你是质量评估员。根据标准评估输出，返回 JSON {score: 0-1, reason: '...'}",
            },
            {
                "role": "user",
                "content": f"标准: {criteria}\n\n输出: {output}",
            },
        ],
    )
    # 简化：只解析分数
    import re
    content = response.choices[0].message.content
    match = re.search(r"(\d+\.?\d*)", content)
    score = float(match.group(1)) if match else 0.0
    if score > 1:
        score = score / 100  # 百分比转小数
    return {"score": score, "raw": content}


# ============================================================
# 测试用例
# ============================================================
TEST_CASES = [
    {
        "name": "研究员输出测试",
        "output": "Multi-Agent 是多个 LLM 协作的系统。它包含 Role、Goal、Tool、Memory、Handoff 5 个核心抽象。",
        "criteria": "必须包含 5 个核心抽象的关键词：Role, Goal, Tool, Memory, Handoff",
        "expected_score": 1.0,
    },
    {
        "name": "写作员输出测试",
        "output": "Multi-Agent 系统很好用。",
        "criteria": "必须是 100 字左右的中文短文，包含具体例子",
        "expected_score": 0.2,
    },
]


# ============================================================
# Mock LLM（测试时不用真 LLM）
# ============================================================
class MockLLM:
    """Mock LLM 用于单元测试"""

    def invoke(self, messages):
        # 返回固定响应
        class MockResponse:
            class Choice:
                class Message:
                    content = "Mock 响应"
                message = Message()
            choices = [Choice()]
        return MockResponse()


# ============================================================
# 演示
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("评估函数演示")
    print("=" * 60)

    for case in TEST_CASES:
        print(f"\n--- {case['name']} ---")
        print(f"输出: {case['output']}")
        print(f"标准: {case['criteria']}")

        result = evaluate_quality(case["output"], case["criteria"])
        print(f"评分: {result['score']}")
        print(f"理由: {result['raw'][:200]}")

        passed = "✓" if result["score"] >= 0.5 else "✗"
        print(f"通过: {passed}")

    print("\n=== Mock LLM 演示（不需 API key）===")
    mock = MockLLM()
    response = mock.invoke([])
    print(f"Mock 输出: {response.choices[0].message.content}")