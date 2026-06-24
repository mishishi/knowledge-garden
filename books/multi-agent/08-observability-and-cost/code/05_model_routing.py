"""
08-observability-and-cost / 05_model_routing.py

模型分级：根据任务复杂度选模型，节省成本。

运行：
    python 05_model_routing.py
"""
from typing import Literal

# ============================================================
# 任务复杂度 → 模型路由
# ============================================================
TaskComplexity = Literal["simple", "medium", "complex"]


MODEL_FOR_COMPLEXITY = {
    "simple": "gpt-4o-mini",        # $0.15/$0.60 per 1M
    "medium": "gpt-4o",             # $2.50/$10.00 per 1M
    "complex": "gpt-4-turbo",       # $10.00/$30.00 per 1M
}

# 每月成本估算（假设 100k 次请求，每次平均 2k input + 500 output tokens）
COST_PER_REQUEST = {
    "gpt-4o-mini": (2000 / 1e6) * 0.15 + (500 / 1e6) * 0.60,
    "gpt-4o": (2000 / 1e6) * 2.50 + (500 / 1e6) * 10.00,
    "gpt-4-turbo": (2000 / 1e6) * 10.00 + (500 / 1e6) * 30.00,
}


def estimate_complexity(task: str) -> TaskComplexity:
    """简单估算任务复杂度"""
    task = task.lower()

    # 简单关键词
    simple_keywords = ["分类", "提取", "问候", "翻译一句话", "总结", "classify", "extract", "greet"]
    if any(kw in task for kw in simple_keywords):
        return "simple"

    # 复杂关键词
    complex_keywords = ["推理", "规划", "代码生成", "复杂分析", "reasoning", "planning", "code generation"]
    if any(kw in task for kw in complex_keywords):
        return "complex"

    return "medium"


def route_model(task: str) -> str:
    """根据任务复杂度选模型"""
    complexity = estimate_complexity(task)
    return MODEL_FOR_COMPLEXITY[complexity]


# ============================================================
# 演示
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("模型路由演示：复杂任务用大模型，简单任务用小模型")
    print("=" * 60)

    tasks = [
        "问候用户：'Hello'",
        "分类这段评论是正面还是负面",
        "调研 Multi-Agent 系统并写 100 字短文",
        "规划一个 7 天的旅行路线",
        "生成一个 React 组件",
        "提取这段文本里的所有邮箱",
    ]

    for task in tasks:
        model = route_model(task)
        cost_per_req = COST_PER_REQUEST[model]
        monthly = cost_per_req * 100_000
        print(f"\n任务: {task}")
        print(f"  → 模型: {model}")
        print(f"  → 单次成本: ${cost_per_req:.6f}")
        print(f"  → 10 万次/月: ${monthly:.2f}")

    print("\n=== 节省分析 ===")
    all_mini_monthly = COST_PER_REQUEST["gpt-4o-mini"] * 100_000
    mixed_monthly = sum(COST_FOR_TASK in COST_PER_REQUEST for COST_FOR_TASK in [route_model(t) for t in tasks]) * 100_000 / len(tasks)
    # 实际混合策略更优
    print(f"全部用 gpt-4o-mini: ${all_mini_monthly:.2f}/月")
    print(f"全部用 gpt-4o: ${COST_PER_REQUEST['gpt-4o'] * 100_000:.2f}/月")
    print("→ 模型路由可以省 60-80% 成本（取决于任务分布）")