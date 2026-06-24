"""
08-observability-and-cost / 03_cost_tracker.py

成本追踪：每次 LLM 调用统计 token + 计算成本。

运行：
    python 03_cost_tracker.py
"""
from dataclasses import dataclass, field
from typing import Literal


# ============================================================
# 价格表（2026 年 6 月，单位：美元 / 1M tokens）
# ============================================================
PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
}


@dataclass
class CostTracker:
    """成本追踪器"""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    calls_by_model: dict = field(default_factory=dict)

    def record(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """记录一次调用的成本"""
        if model not in PRICING:
            print(f"  ⚠️ 未知模型 {model}，成本按 0 计算")
            return 0.0

        input_cost = input_tokens / 1_000_000 * PRICING[model]["input"]
        output_cost = output_tokens / 1_000_000 * PRICING[model]["output"]
        cost = input_cost + output_cost

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += cost

        if model not in self.calls_by_model:
            self.calls_by_model[model] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0}
        self.calls_by_model[model]["calls"] += 1
        self.calls_by_model[model]["input_tokens"] += input_tokens
        self.calls_by_model[model]["output_tokens"] += output_tokens
        self.calls_by_model[model]["cost"] += cost

        return cost

    def report(self) -> str:
        """生成成本报告"""
        lines = ["=== 成本报告 ==="]
        lines.append(f"总 Input Tokens: {self.total_input_tokens:,}")
        lines.append(f"总 Output Tokens: {self.total_output_tokens:,}")
        lines.append(f"总成本: ${self.total_cost:.4f}")
        lines.append("")
        lines.append("按模型细分:")
        for model, stats in self.calls_by_model.items():
            lines.append(f"  {model}:")
            lines.append(f"    调用次数: {stats['calls']}")
            lines.append(f"    Tokens: {stats['input_tokens']:,} input + {stats['output_tokens']:,} output")
            lines.append(f"    成本: ${stats['cost']:.4f}")
        return "\n".join(lines)


# ============================================================
# 演示：模拟一次 Multi-Agent 调用的成本
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("成本追踪演示")
    print("=" * 60)

    tracker = CostTracker()

    # Researcher: gpt-4o-mini
    cost = tracker.record("gpt-4o-mini", input_tokens=1500, output_tokens=300)
    print(f"Researcher: ${cost:.6f}")

    # Writer: gpt-4o-mini
    cost = tracker.record("gpt-4o-mini", input_tokens=2000, output_tokens=500)
    print(f"Writer: ${cost:.6f}")

    # Reviewer: gpt-4o
    cost = tracker.record("gpt-4o", input_tokens=3000, output_tokens=800)
    print(f"Reviewer: ${cost:.6f}")

    # 模拟一个月（10 万次请求）
    print("\n=== 月度预测（按 10 万次请求计算）===")
    monthly = tracker.total_cost * 100_000
    print(f"  成本: ${monthly:.2f}")
    print(f"  → 如果用 deepseek 替代: ${monthly * 0.05:.2f}（节省 95%）")

    print("\n" + tracker.report())