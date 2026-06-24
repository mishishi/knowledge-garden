"""
06-failure-handling / 01_failure_classification.py

失败分类演示：构造 4 类失败的 mock，演示每种怎么检测。

运行：
    python 01_failure_classification.py
    （不需要 API key，全是 mock）
"""
import random
import time


# ============================================================
# Mock LLM 调用，可能触发各类失败
# ============================================================
def mock_llm_call(prompt: str, failure_rate: float = 0.3) -> dict:
    """模拟一个不稳定的 LLM 调用"""
    time.sleep(0.1)

    roll = random.random()
    if roll < failure_rate:
        failure_type = random.choice([
            "malformed_json",
            "timeout",
            "violate_constraint",
        ])
        return {"success": False, "failure_type": failure_type, "error": f"Mock failure: {failure_type}"}

    return {"success": True, "output": f"正常输出：{prompt[:30]}"}


# ============================================================
# 分类演示
# ============================================================
def classify_failure(error: dict) -> str:
    """根据错误信息分类"""
    if not error.get("success"):
        ft = error.get("failure_type", "unknown")
        if ft == "malformed_json":
            return "Agent 失败：LLM 输出 malformed JSON"
        elif ft == "timeout":
            return "Agent 失败：LLM 调用超时"
        elif ft == "violate_constraint":
            return "Agent 失败：违反 prompt 约束"
    return "未知失败"


if __name__ == "__main__":
    print("=" * 60)
    print("失败分类演示：跑 20 次，看各类失败出现频率")
    print("=" * 60)

    failure_counts = {}
    for i in range(20):
        result = mock_llm_call(f"prompt {i}")
        if not result["success"]:
            category = classify_failure(result)
            failure_counts[category] = failure_counts.get(category, 0) + 1

    print("\n=== 失败统计 ===")
    for category, count in failure_counts.items():
        print(f"  {category}: {count} 次")

    if not failure_counts:
        print("  没有失败（运气好）")

    print("\n=== 防御策略 ===")
    print("- malformed_json → 用 Pydantic 校验 + retry_with_backoff")
    print("- timeout → 加超时 + retry")
    print("- violate_constraint → 用结构化输出 + 验证")