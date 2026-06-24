# 第 7 章代码

## 文件结构

```
code/
├── 01_crewai.py         # CrewAI 实现
├── 02_langgraph.py      # LangGraph 实现
├── 03_autogen.py        # AutoGen 实现
└── 04_swarm.py          # OpenAI Swarm 实现
```

## 依赖

```bash
# 基础
pip install openai

# CrewAI
pip install crewai

# LangGraph
pip install langgraph langchain-openai

# AutoGen
pip install autogen-agentchat~=0.4

# OpenAI Swarm
pip install git+https://github.com/openai/swarm.git
```

## 运行

每个文件独立运行，对比同一个需求的 4 种实现：

```bash
python 01_crewai.py
python 02_langgraph.py
python 03_autogen.py
python 04_swarm.py
```

## 对比维度

| 维度 | CrewAI | LangGraph | AutoGen | Swarm |
|------|--------|-----------|---------|-------|
| 代码量 | ~15 行 | ~30 行 | ~25 行 | ~20 行 |
| 学习曲线 | 平缓 | 陡 | 中 | 较平 |
| 控制流 | 配置式 | 完全控制 | 中 | 固定 handoff |
| 调试 | verbose | LangSmith | console | 几乎无 |
| 生产 | 中 | 高 | 中 | 低 |

## 选型推荐

- **快速验证**：CrewAI
- **生产系统**：LangGraph
- **群聊/头脑风暴**：AutoGen
- **极简 demo**：Swarm