"""
08-observability-and-cost / 02_otel_demo.py

OpenTelemetry 集成：跨框架标准的 Trace 方案。

安装：
    pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp

运行：
    python 02_otel_demo.py
    （需要 OpenTelemetry Collector 在 localhost:4317 运行）
"""
import time

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)


# ============================================================
# 初始化 Tracer
# ============================================================
provider = TracerProvider(
    resource=Resource.create({"service.name": "multi-agent-demo"})
)

# Console 输出（开发环境）
provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

# 或者 OTLP 输出到 Collector
# from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
# provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint="localhost:4317")))

trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)


# ============================================================
# 模拟 Agent 调用
# ============================================================
def fake_llm_call(model: str, prompt: str) -> str:
    time.sleep(0.1)
    return f"LLM ({model}) 输出: {prompt[:30]}"


def fake_tool_call(tool: str, **kwargs) -> str:
    time.sleep(0.05)
    return f"{tool}({kwargs}) 返回"


if __name__ == "__main__":
    print("=" * 60)
    print("OpenTelemetry 演示：每个 span 都会输出")
    print("=" * 60)

    # Researcher
    with tracer.start_as_current_span("agent.researcher") as span:
        span.set_attribute("agent.name", "researcher")
        span.set_attribute("agent.role", "研究员")

        with tracer.start_as_current_span("llm.call") as span:
            span.set_attribute("llm.model", "gpt-4o-mini")
            span.set_attribute("llm.input_tokens", 1500)
            span.set_attribute("llm.output_tokens", 200)
            result = fake_llm_call("gpt-4o-mini", "调研")

        with tracer.start_as_current_span("tool.call") as span:
            span.set_attribute("tool.name", "search")
            span.set_attribute("tool.input", '{"query": "Multi-Agent"}')
            result = fake_tool_call("search", query="Multi-Agent")

    print("\nSpan 已上报到 Console（或 OTLP collector）")