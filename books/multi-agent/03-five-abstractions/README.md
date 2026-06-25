# 03. 5 个核心抽象

> 上章是「研究员 + 写作员」两个 Agent 的直觉。这章把直觉提炼成 5 个抽象：Role / Goal / Tool / Memory / Handoff。CrewAI、LangGraph、AutoGen 跑不掉这几个词。

## 为什么需要抽象

第 2 章的 Multi-Agent 是这样的：

```python
researcher = Agent(role="研究员", goal="...", backstory="...", tools=[])
writer = Agent(role="写作员", goal="...", backstory="...", tools=[])
```

看起来很简单，但是当你真正开始设计一个 Multi-Agent 系统时会问出这些问题：

- 这个 Agent 应该叫什么名字？做什么的？边界在哪？→ **Role**
- 它要达成什么目标？怎么算「达成」？→ **Goal**
- 它能用什么工具？怎么定义工具？→ **Tool**
- 它能记住什么？短期？长期？其他 Agent 的？→ **Memory**
- 任务怎么从 A 传到 B？什么时候传？传什么？→ **Handoff**

这 5 个问题，构成了 Multi-Agent 设计的全部决策空间。

## 抽象 1：Role（角色）

**Role = Agent 是谁**。决定它的视角、语气、行为边界。

CrewAI 写法——`role` 是短标签，`backstory` 是给 LLM 看的详细背景，两者共同决定 LLM 的「人格」：

```python
researcher = Agent(
    role="研究员",          # ← 角色名
    goal="...",             # 目标（抽象 2）
    backstory="你是一个...",  # 角色背景描述
)
```

LangGraph 写法——没有显式的 Role 概念，把 Role 隐含在节点函数里：

```python
def researcher_node(state: State) -> State:
    # 整个函数就是 researcher 的"角色"
    llm = ChatOpenAI(model="gpt-4o-mini")
    prompt = "你是专业研究员..."  # ← Role 写在这里
    response = llm.invoke([SystemMessage(content=prompt), ...])
    return {"messages": [response]}
```

**区别**：CrewAI 的 Role 是数据，LangGraph 的 Role 是代码结构。

Role 设计原则：

1. **单一职责**——一个 Role 只做一件事。「全能 Agent」几乎一定是反模式。
2. **能力匹配**——Role 的能力边界要和 Goal 对得上（研究员不应该被期望写代码）。
3. **正交性**——多个 Role 之间尽量不重叠，重叠会导致混乱（两个 Agent 都觉得自己应该做）。

## 抽象 2：Goal（目标）

**Goal = Agent 要达成什么**。决定它的工作方向和完成判定。

Goal 的两种颗粒度——粗粒度模糊但灵活，细粒度清晰可验证。**细粒度总是更好**——可验证意味着可调试。

```python
# 粗粒度：模糊，但灵活
goal="写一篇好文章"

# 细粒度：清晰，可验证
goal="基于 3 条事实，写一段 100 字以内的中文短文，引用所有事实"
```

**expected_output：把 Goal 变成可验证**：

```python
task = Task(
    description="...",       # 怎么做的提示
    expected_output="...",   # 验收标准
    agent=researcher,
)
```

`expected_output` 是 Goal 的**工程化**：LLM 知道自己要交付什么，你也知道怎么验收。

3 个 Goal 设计反模式：

- **太宽**：`goal="帮助用户"` 啥都能算「帮助」，没法验证。
- **太窄**：`goal="输出第 47 个字符是 '你' 的字符串"` 太死板没有意义。
- **矛盾**：`goal="用 100 字以内的篇幅完整介绍 Multi-Agent 的 5 个核心抽象的所有细节"` ——100 字根本讲不完 5 个抽象，目标互相矛盾。

## 抽象 3：Tool（工具）

**Tool = Agent 能做什么**。决定它的能力上限。

工具的 3 个层次：

```
Level 1：内置工具
└─ CrewAI 的 SerperDevTool、LangChain 的 DuckDuckGoSearchRun

Level 2：自定义工具（你写的 Python 函数）
└─ @tool 装饰器 / BaseTool 子类

Level 3：MCP / 外部服务
└─ 通过 Model Context Protocol 调用外部服务
```

自定义工具示例——关键是 **docstring 要写清楚**，LLM 是靠 docstring 决定要不要调用、调什么参数的：

```python
from crewai.tools import tool

@tool("Get Weather")
def get_weather(city: str) -> str:
    """查询指定城市的天气。"""
    return f"{city}: 22°C"
```

Tool 设计 3 原则：

1. **粒度合适**——工具太粗（「做所有事」）等于没工具；太细（「加一个字符」）LLM 会被淹没。
2. **错误信息要清晰**——工具失败时返回的信息要告诉 LLM 怎么修（不要只抛异常）。
3. **幂等性**——同一个输入应该返回同样的输出（避免 LLM 重试时拿到不同结果）。

## 抽象 4：Memory（记忆）

**Memory = Agent 知道什么**。决定它的「上下文视野」。

3 种记忆：

- **短期记忆**（Short-term）——当前对话历史，LLM 默认就有。
- **长期记忆**（Long-term）——跨会话保留的信息，比如「这个用户上次问了什么」。
- **共享记忆**（Shared）——多个 Agent 之间共享的状态，比如「Researcher 的输出给 Writer 用」。

CrewAI 的 Memory 实现——`memory=True` 启用长期记忆（向量数据库），默认会读 conversation_buffer + entity_memory + short_term：

```python
agent = Agent(
    role="...",
    memory=True,  # ← 启用长期记忆
)
```

LangGraph 的 Memory 实现——用 `State` 对象传递记忆：

```python
from typing import TypedDict

class State(TypedDict):
    messages: list  # 短期记忆
    facts: list     # 共享记忆（事实列表）
    user_profile: dict  # 长期记忆

# 节点之间通过 state 传递
def researcher_node(state: State) -> State:
    state["facts"].append("...")
    return state
```

## 抽象 5：Handoff（交接）

**Handoff = Agent 之间怎么传递任务**。决定整个系统的「流程图」。

3 种 Handoff 模式：

**模式 A：顺序交接（Pipeline）**——`A → B → C`，最简单，每个 Agent 完成后传给下一个。

```python
task_b = Task(..., context=[task_a])  # B 等 A 完成
```

**模式 B：条件交接（Conditional）**——需要 router 节点判断走哪个分支。

```
     ┌─ 满足 X → B
A ──┤
     └─ 满足 Y → C
```

**模式 C：并行交接（Parallel / Broadcast）**——一个 Agent 的输出同时给多个 Agent。

```
     ┌─ B
A ───┼─ C   (同时执行)
     └─ D
```

CrewAI vs LangGraph 的 Handoff 对比：

| 模式 | CrewAI | LangGraph |
|---|---|---|
| 顺序 | `context=[task_a]` | 节点串成 chain |
| 条件 | 内置 router 不直观 | `add_conditional_edges()` |
| 并行 | `async_execution=True` | `Send` API |

## 5 个抽象的依赖关系

```
Tool ──┐
       ├──> Goal（能做什么、要做什么）
Role ──┘
       │
       └──> Handoff（任务流转）

Memory ──> 贯穿所有 Agent
```

设计顺序：

1. 先定 **Role**（谁）
2. 再定 **Goal**（做什么）
3. 然后选 **Tool**（怎么做）
4. 考虑 **Memory**（要记什么）
5. 最后设计 **Handoff**（怎么串起来）

## 生产化提示

5 个抽象的工程化：

- **Role**——用配置文件管理（不要 hardcode 在代码里）
- **Goal**——每个 Goal 配一个评估函数（自动判断是否达成）
- **Tool**——统一错误返回格式、加超时、加重试
- **Memory**——短期用 Redis，长期用向量数据库，共享用 LangGraph State
- **Handoff**——可视化编排（用 LangGraph Studio / CrewAI Studio）
