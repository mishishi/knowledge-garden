# 第 8 章代码

## 文件结构

```
code/
├── 01_trace_demo.py        # 自建轻量 Trace
├── 02_otel_demo.py         # OpenTelemetry 集成
├── 03_cost_tracker.py      # 成本追踪（不需 API key）
├── 04_token_budget.py      # Token 预算强制
└── 05_model_routing.py     # 模型分级（不需 API key）
```

## 依赖

```bash
pip install openai opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
```

## 运行

```bash
# 不需要 API key
python 01_trace_demo.py
python 03_cost_tracker.py
python 05_model_routing.py

# 需要 API key
python 02_otel_demo.py        # 需要 OTLP collector
python 04_token_budget.py
```

## 关键 takeaway

1. **可观测性**：Trace + Metric + Log 三件套，至少要有 Trace
2. **Trace 工具**：LangSmith（最方便）/ OTel（跨框架）/ 自建（最轻）
3. **成本控制**：预算强制 + 模型分级 + 缓存 + 提前终止
4. **关键指标**：单 session 成本、循环次数、错误率、P95 延迟