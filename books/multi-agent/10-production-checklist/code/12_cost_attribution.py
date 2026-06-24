"""
10-production-checklist / 12_cost_attribution.py

成本归因：按用户 / 功能 / 模型聚合成本。

运行：
    python 12_cost_attribution.py
"""
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class CostRecord:
    session_id: str
    user_id: str
    feature: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    timestamp: float


# 价格表
PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICING.get(model, {"input": 0, "output": 0})
    return (input_tokens / 1e6) * p["input"] + (output_tokens / 1e6) * p["output"]


# ============================================================
# 内存版 Cost Tracker（生产用数据库）
# ============================================================
class CostAttributionTracker:
    def __init__(self):
        self.records: list[CostRecord] = []

    def record(self, session_id: str, user_id: str, feature: str, model: str, input_tokens: int, output_tokens: int):
        cost = calculate_cost(model, input_tokens, output_tokens)
        record = CostRecord(
            session_id=session_id,
            user_id=user_id,
            feature=feature,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            timestamp=time.time(),
        )
        self.records.append(record)
        return cost

    def report_by_user(self) -> dict:
        report = defaultdict(float)
        for r in self.records:
            report[r.user_id] += r.cost
        return dict(report)

    def report_by_feature(self) -> dict:
        report = defaultdict(float)
        for r in self.records:
            report[r.feature] += r.cost
        return dict(report)

    def report_by_model(self) -> dict:
        report = defaultdict(float)
        for r in self.records:
            report[r.model] += r.cost
        return dict(report)


import time


# ============================================================
# 演示
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("成本归因演示")
    print("=" * 60)

    tracker = CostAttributionTracker()

    # 模拟一周的请求
    test_data = [
        ("s1", "alice", "code_review", "gpt-4o-mini", 2000, 500),
        ("s2", "alice", "code_review", "gpt-4o-mini", 3000, 800),
        ("s3", "bob", "research", "gpt-4o", 5000, 1500),
        ("s4", "bob", "research", "gpt-4o", 4000, 1000),
        ("s5", "carol", "code_review", "gpt-4o-mini", 2500, 600),
        ("s6", "alice", "chat", "gpt-4o-mini", 1000, 300),
    ]

    for session_id, user_id, feature, model, in_tok, out_tok in test_data:
        cost = tracker.record(session_id, user_id, feature, model, in_tok, out_tok)

    print("\n=== 按用户聚合 ===")
    for user, cost in sorted(tracker.report_by_user().items(), key=lambda x: -x[1]):
        print(f"  {user}: ${cost:.4f}")

    print("\n=== 按功能聚合 ===")
    for feature, cost in sorted(tracker.report_by_feature().items(), key=lambda x: -x[1]):
        print(f"  {feature}: ${cost:.4f}")

    print("\n=== 按模型聚合 ===")
    for model, cost in sorted(tracker.report_by_model().items(), key=lambda x: -x[1]):
        print(f"  {model}: ${cost:.4f}")

    print("\n=== 决策支持 ===")
    print("  alice 是 code_review 的重度用户")
    print("  research 功能用 gpt-4o 成本最高（$0.04）→ 考虑用 gpt-4o-mini 替代")
    print("  → 优化后预计节省 60% 成本")