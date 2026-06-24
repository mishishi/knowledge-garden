# 07. 框架横向对比

> 第 4 章我们看了 5 种编排模式，本章做一件更实际的事：**用同一需求对比 4 个主流 Multi-Agent 框架的代码风格、调试难度、生产成熟度**。看完你应该能根据自己的场景选框架。

## 4 个主流框架

```
CrewAI        角色驱动，最简单，上手快
AutoGen       对话驱动，群聊模式最强
LangGraph     图驱动，生产级，灵活但陡
OpenAI Swarm  极简，handoffs 一行配置
```

---

## 同一个需求，4 种实现

**需求**：调研 Multi-Agent 系统，写一篇 100 字短文，评审。

### CrewAI 实现

```python
from crewai import Agent, Task, Crew

researcher = Agent(role="研究员", goal="...", backstory="...", allow_delegation=False)
writer = Agent(role="写作员", goal="...", backstory="...", allow_delegation=False)
reviewer = Agent(role="评审员", goal="...", backstory="...", allow_delegation=False)

t1 = Task(description="调研", agent=researcher, expected_output="3 条事实")
t2 = Task(description="写作", agent=writer, expected_output="100 字", context=[t1])
t3 = Task(description="评审", agent=reviewer, expected_output="评审意见", context=[t2])

crew = Crew(agents=[researcher, writer, reviewer], tasks=[t1, t2, t3], verbose=True)
result = crew.kickoff(inputs={"topic": "Multi-Agent"})
```

**特点**：

- ✅ 代码最少（10 行）
- ✅ 配置式定义（role / goal / backstory）
- ❌ 控制流藏在框架里，复杂流程不灵活
- ❌ 调试只能看 verbose 输出

完整代码：[`code/01_crewai.py`](./code/01_crewai.py)

---

### LangGraph 实现

```python
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    topic: str
    facts: str
    draft: str
    review: str

def research_node(state): ...
def write_node(state): ...
def review_node(state): ...

workflow = StateGraph(State)
workflow.add_node("research", research_node)
workflow.add_node("write", write_node)
workflow.add_node("review", review_node)

workflow.add_edge(START, "research")
workflow.add_edge("research", "write")
workflow.add_edge("write", "review")
workflow.add_edge("review", END)

app = workflow.compile()
result = app.invoke({"topic": "Multi-Agent"})
```

**特点**：

- ✅ 完全控制流程（节点 + 边）
- ✅ 内置 state、checkpointer、interrupt
- ✅ LangSmith 可视化
- ❌ 代码量最大（30+ 行）
- ❌ 学习曲线陡

完整代码：[`code/02_langgraph.py`](./code/02_langgraph.py)

---

### AutoGen 实现

```python
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat

researcher = AssistantAgent(name="researcher", model_client="gpt-4o-mini", system_message="...")
writer = AssistantAgent(name="writer", model_client="gpt-4o-mini", system_message="...")
reviewer = AssistantAgent(name="reviewer", model_client="gpt-4o-mini", system_message="...")

team = RoundRobinGroupChat(participants=[researcher, writer, reviewer])

result = await team.run(task="调研 Multi-Agent 并写 100 字短文")
```

**特点**：

- ✅ 群聊模式最强（GroupChat 是 AutoGen 原生）
- ✅ 异步原生
- ❌ 顺序流程不如 CrewAI 直观
- ❌ API 变化快（0.2 → 0.4 大量 breaking change）

完整代码：[`code/03_autogen.py`](./code/03_autogen.py)

---

### OpenAI Swarm 实现

```python
from swarm import Agent, Swarm

def handoff_to_writer(): return writer
def handoff_to_reviewer(): return reviewer

researcher = Agent(
    name="researcher",
    instructions="调研后调用 handoff_to_writer",
    functions=[handoff_to_writer],
)
writer = Agent(name="writer", instructions="写完后调用 handoff_to_reviewer", functions=[handoff_to_reviewer])
reviewer = Agent(name="reviewer", instructions="评审")

client = Swarm()
response = client.run(agent=researcher, messages=[{"role": "user", "content": "..."}])
```

**特点**：

- ✅ 极简（核心代码 < 50 行）
- ✅ handoffs 概念清晰
- ❌ 功能最少（无状态管理、可视化、HITL）
- ❌ 还在快速迭代，不建议生产

完整代码：[`code/04_swarm.py`](./code/04_swarm.py)

---

## 4 个框架对比表

| 维度 | CrewAI | LangGraph | AutoGen | Swarm |
|------|--------|-----------|---------|-------|
| 代码量 | ⭐⭐⭐⭐⭐ 最少 | ⭐⭐ 最多 | ⭐⭐⭐ 中等 | ⭐⭐⭐⭐ 少 |
| 学习曲线 | ⭐⭐⭐⭐⭐ 平缓 | ⭐⭐ 陡 | ⭐⭐⭐ 中 | ⭐⭐⭐⭐ 较平 |
| 控制流灵活度 | ⭐⭐ 配置式 | ⭐⭐⭐⭐⭐ 完全控制 | ⭐⭐⭐ 中 | ⭐⭐ 固定 handoff |
| 调试难度 | ⭐⭐ 难（verbose） | ⭐⭐⭐⭐ 易（LangSmith） | ⭐⭐⭐ 中 | ⭐⭐ 难 |
| 生产成熟度 | ⭐⭐⭐ 中 | ⭐⭐⭐⭐⭐ 高 | ⭐⭐⭐ 中 | ⭐⭐ 低 |
| 文档质量 | ⭐⭐⭐⭐ 好 | ⭐⭐⭐⭐⭐ 极好 | ⭐⭐⭐ 中 | ⭐⭐ 差 |
| 社区活跃度 | ⭐⭐⭐⭐ 活跃 | ⭐⭐⭐⭐ 活跃 | ⭐⭐⭐ 中 | ⭐⭐ 低 |
| HITL 支持 | ⭐⭐ 弱 | ⭐⭐⭐⭐⭐ 原生 | ⭐⭐⭐ 中 | ⭐ 不支持 |
| 状态管理 | ⭐⭐ 弱 | ⭐⭐⭐⭐⭐ TypedDict | ⭐⭐⭐ 中 | ⭐ 不支持 |
| 可视化 | ⭐⭐ 弱 | ⭐⭐⭐⭐⭐ Studio | ⭐⭐⭐ Studio | ⭐ 不支持 |

---

## 调试难度对比

CrewAI：跑 `verbose=True`，看打印的对话历史。**缺点**：不能 step into Agent 内部，不能断点。

LangGraph：用 LangSmith 看 trace，每个节点的输入输出都能 inspect。**优点**：可视化 + 时间线 + token 统计。

AutoGen：有 console 输出，但 trace 不如 LangSmith 直观。

Swarm：几乎没调试工具，只能 print。

**结论**：调试体验 LangGraph > AutoGen > CrewAI > Swarm。

---

## 生产成熟度对比

| 框架 | 是否有 trace 工具 | 是否有部署方案 | 是否有 enterprise 支持 |
|------|------------------|---------------|----------------------|
| CrewAI | 第三方集成 | CrewAI Enterprise | ✅ |
| LangGraph | ✅ LangSmith | ✅ LangGraph Cloud | ✅ |
| AutoGen | 部分 | AutoGen Studio | ⚠️ Microsoft Research |
| Swarm | ❌ | ❌ | ❌ |

**结论**：生产环境推荐 LangGraph 或 CrewAI。Swarm 仅适合 demo。

---

## 选型决策树

```
你的场景是什么？
│
├─ 简单的角色化任务（调研 + 写作 + 评审）
│   └─ CrewAI（5 分钟上手）
│
├─ 复杂生产系统（需要状态管理、HITL、可视化）
│   └─ LangGraph（首选）
│
├─ 多 Agent 自由讨论 / 头脑风暴
│   └─ AutoGen（GroupChat 模式）
│
├─ 极简 demo / 实验性项目
│   └─ Swarm（最简）
│
└─ 我不知道选啥
    └─ CrewAI（默认安全选择）
```

---

## 迁移成本

框架之间能迁移吗？

| 从 → 到 | 迁移成本 | 说明 |
|---------|---------|------|
| CrewAI → LangGraph | 中 | 需要把 Agent/Task 改成 Node/Edge |
| LangGraph → CrewAI | 中 | 需要把节点函数改成 Agent/Task |
| AutoGen → LangGraph | 中 | 需要把 AssistantAgent 改成节点函数 |
| Swarm → 其他 | 低 | Swarm 极简，重写不难 |

**建议**：先用 CrewAI 验证业务逻辑，再迁移到 LangGraph 做生产化。

---

## 本章小结

- 4 个框架：**CrewAI / LangGraph / AutoGen / Swarm**
- 默认推荐：**CrewAI**（上手快）+ **LangGraph**（生产强）
- 调试体验：**LangGraph > AutoGen > CrewAI > Swarm**
- 选型原则：先用简单的验证业务，生产再上 LangGraph

## 下篇

[08. 可观测性与成本](../08-observability-and-cost/) —— 选了框架后，怎么知道它在干什么、烧了多少钱。

## 生产化提示

框架的工程化：

- **不要只用框架**：业务逻辑写在节点函数 / Task 里，不要藏在 framework 配置
- **加监控层**：不论用哪个框架，都要把 trace / metric 抽到统一 observability 平台
- **测试用 mock**：避免每个测试都调 LLM，用 mock 的 LLM client
- **版本锁**：框架迭代快，`requirements.txt` 锁版本