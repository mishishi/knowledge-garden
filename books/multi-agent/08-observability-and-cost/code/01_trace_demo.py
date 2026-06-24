"""
08-observability-and-cost / 01_trace_demo.py

自建轻量 Trace：5 行代码起步，不依赖云服务。

运行：
    python 01_trace_demo.py
"""
import json
import time
from contextlib import contextmanager


class SimpleTracer:
    """最小化的 Trace 实现"""

    def __init__(self):
        self.spans = []

    @contextmanager
    def span(self, name: str, **attrs):
        """记录一段 span"""
        span = {"name": name, "start": time.time(), "attrs": attrs}
        try:
            yield span
        finally:
            span["duration_ms"] = round((time.time() - span["start"]) * 1000, 2)
            self.spans.append(span)
            print(f"  [Trace] {name}: {span['duration_ms']}ms {attrs}")

    def dump(self) -> str:
        return json.dumps(self.spans, indent=2, ensure_ascii=False)


# ============================================================
# 演示：模拟一次 Multi-Agent 调用
# ============================================================
tracer = SimpleTracer()


def fake_llm_call(prompt: str) -> str:
    """Mock LLM 调用"""
    time.sleep(0.1)
    return f"LLM 输出: {prompt[:30]}"


def fake_tool_call(tool_name: str, **kwargs) -> str:
    """Mock 工具调用"""
    time.sleep(0.05)
    return f"{tool_name} 返回: {kwargs}"


if __name__ == "__main__":
    print("=" * 60)
    print("Trace 演示：模拟一次 Multi-Agent 调用")
    print("=" * 60)

    # Researcher 调研
    with tracer.span("agent.researcher", topic="Multi-Agent"):
        with tracer.span("llm.call", model="gpt-4o-mini"):
            result1 = fake_llm_call("调研 Multi-Agent")

    # Writer 写作
    with tracer.span("agent.writer"):
        with tracer.span("llm.call", model="gpt-4o-mini"):
            result2 = fake_llm_call("基于调研写文章")

    # Reviewer 评审
    with tracer.span("agent.reviewer"):
        with tracer.span("llm.call", model="gpt-4o"):
            result3 = fake_llm_call("评审文章")

    print("\n=== Trace 数据（JSON） ===")
    print(tracer.dump())