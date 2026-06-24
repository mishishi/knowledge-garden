"""
06-failure-handling / 04_cascading_failure.py

级联失败防御：Circuit Breaker + Partial Failure。

运行：
    python 04_cascading_failure.py
"""
import random
import time


# ============================================================
# Circuit Breaker 实现
# ============================================================
class CircuitBreaker:
    """断路器：失败次数过多时自动断开"""

    def __init__(self, name: str, failure_threshold=3, reset_timeout=5):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed / open / half-open

    def call(self, func, *args, **kwargs):
        # 检查是否可以尝试
        if self.state == "open":
            if time.time() - self.last_failure_time > self.reset_timeout:
                print(f"  [{self.name}] 断路器半开，尝试恢复...")
                self.state = "half-open"
            else:
                raise Exception(f"[{self.name}] 断路器已断开，跳过调用")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        self.failures = 0
        if self.state == "half-open":
            print(f"  [{self.name}] 恢复成功，关闭断路器")
        self.state = "closed"

    def _on_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            print(f"  [{self.name}] 失败次数 {self.failures}，打开断路器")
            self.state = "open"


# ============================================================
# 一个不可靠的下游服务
# ============================================================
def unreliable_service(data: str) -> str:
    """60% 失败率的下游服务"""
    if random.random() < 0.6:
        raise ConnectionError(f"下游服务 {data} 调用失败")
    return f"成功处理: {data}"


# ============================================================
# Partial Failure Pipeline
# ============================================================
def multi_step_pipeline(data: dict) -> dict:
    """多步 pipeline：每步失败不中断后续"""
    results = {}

    steps = {
        "step1": lambda: unreliable_service(data.get("input1", "")),
        "step2": lambda: unreliable_service(data.get("input2", "")),
        "step3": lambda: unreliable_service(data.get("input3", "")),
    }

    for step_name, step_func in steps.items():
        try:
            results[step_name] = step_func()
        except Exception as e:
            results[step_name] = {"error": str(e), "skipped": True}

    return results


# ============================================================
# 演示
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("演示 1: Circuit Breaker")
    print("=" * 60)

    breaker = CircuitBreaker("my-service", failure_threshold=3, reset_timeout=3)

    for i in range(8):
        try:
            result = breaker.call(unreliable_service, f"req-{i}")
            print(f"  请求 {i}: ✓ {result}")
        except Exception as e:
            print(f"  请求 {i}: ✗ {e}")
        time.sleep(0.5)

    print("\n" + "=" * 60)
    print("演示 2: Partial Failure Pipeline")
    print("=" * 60)

    for i in range(3):
        print(f"\n  Pipeline {i + 1}:")
        result = multi_step_pipeline({"input1": "a", "input2": "b", "input3": "c"})
        for step, outcome in result.items():
            if isinstance(outcome, dict) and outcome.get("skipped"):
                print(f"    {step}: ✗ 跳过 ({outcome['error']})")
            else:
                print(f"    {step}: ✓ {outcome}")