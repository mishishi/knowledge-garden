# 第 5 章代码

## 文件结构

```
code/
├── 01_message_protocol.py    # 消息协议 3 种格式对比
├── 02_pass_by_value.py       # Pass-by-Value 传递模式
├── 03_broadcast.py           # Broadcast 广播模式（LangGraph Send）
└── 04_state_management.py    # 状态管理：单一大 State vs 分层 State
```

## 依赖

```bash
pip install langgraph langchain-openai crewai pydantic
```

## 运行

```bash
# 消息协议
python 01_message_protocol.py nl       # 自然语言（脆弱）
python 01_message_protocol.py json     # 结构化 JSON（中等）
python 01_message_protocol.py pydantic # Pydantic 模型（推荐）

# Pass-by-Value
python 02_pass_by_value.py with        # 有 context（推荐）
python 02_pass_by_value.py without     # 无 context（反模式）

# Broadcast
python 03_broadcast.py

# 状态管理
python 04_state_management.py
```

## 关键 takeaway

1. **消息协议**：用 Pydantic 模型做 schema，强制 LLM 输出结构化数据
2. **Pass-by-Value**：用 CrewAI `context=[previous_task]` 实现简单传递
3. **Broadcast**：用 LangGraph `Send` API 实现并行广播
4. **State 管理**：分层 State，按节点定义读写权限