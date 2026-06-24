# 第 6 章代码

## 文件结构

```
code/
├── 01_failure_classification.py    # 失败分类演示（Mock）
├── 02_deadloop_detection.py        # 死循环检测 3 重保险
├── 03_tool_retry.py                # 指数退避重试 + Fallback
├── 04_cascading_failure.py         # Circuit Breaker + Partial Failure
└── 05_human_in_loop.py             # Human-in-the-Loop（LangGraph interrupt）
```

## 依赖

```bash
pip install langgraph langchain-openai openai
```

## 运行

```bash
# 不需要 API key
python 01_failure_classification.py
python 03_tool_retry.py
python 04_cascading_failure.py

# 需要 API key
python 02_deadloop_detection.py protected   # 推荐
python 02_deadloop_detection.py dangerous  # 危险！可能死循环
python 05_human_in_loop.py
```

## 关键 takeaway

1. **死循环防御**：3 重保险（max_iterations + watchdog + cost budget）
2. **超时重试**：指数退避（1s → 2s → 4s）+ Fallback 策略
3. **级联失败**：Circuit Breaker + Partial Failure（不要 all-or-nothing）
4. **HITL**：高风险操作强制人类决策，LangGraph `interrupt` 实现