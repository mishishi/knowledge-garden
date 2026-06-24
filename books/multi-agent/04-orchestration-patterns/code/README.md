# 第 4 章代码

## 文件结构

```
code/
├── 01_pipeline.py        # Pipeline（CrewAI 实现）
├── 02_supervisor.py      # Supervisor（LangGraph 实现）
├── 03_group_chat.py      # GroupChat（AutoGen 实现）
├── 04_swarm.py           # Swarm（OpenAI Swarm 实现）
└── 05_graph.py           # Graph（LangGraph 实现）
```

## 额外依赖

本章用到 4 个框架，按需安装：

```bash
# 基础
pip install openai crewai

# LangGraph（02_supervisor, 05_graph）
pip install langgraph langchain-openai

# AutoGen（03_group_chat）
pip install autogen-agentchat~=0.4

# OpenAI Swarm（04_swarm）
pip install git+https://github.com/openai/swarm.git
```

完整 requirements 在 [`requirements.txt`](./requirements.txt)。

## 运行

每个文件独立运行：

```bash
python 01_pipeline.py
python 02_supervisor.py
python 03_group_chat.py
python 04_swarm.py
python 05_graph.py
```

## 预期行为对比

| 模式 | 行为 | 速度 |
|------|------|------|
| Pipeline | 4 步顺序执行 | 4x LLM 调用 |
| Supervisor | Supervisor 来回调度 3-4 次 | 6-8x LLM 调用 |
| GroupChat | 3 个 Agent 轮流发言到终止 | 6-9x LLM 调用 |
| Swarm | Agent 之间主动交接 | 3x LLM 调用 |
| Graph | 3 路并行 + 1 次汇总 | 4x LLM 调用（但 3 个并行 ≈ 1x 时间） |

## 框架推荐

| 模式 | 推荐框架 | 原因 |
|------|---------|------|
| Pipeline | CrewAI | 简单，5 行代码 |
| Supervisor | LangGraph | `add_conditional_edges` 一行搞定 |
| GroupChat | AutoGen | 成熟，原生支持 |
| Swarm | OpenAI Swarm | 极简，handoffs 一行配置 |
| Graph | LangGraph | 图本来就是它的核心 |

跨框架比较见 [第 7 章](../07-framework-comparison/)。