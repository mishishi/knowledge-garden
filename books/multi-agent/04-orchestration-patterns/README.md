# 04. 编排模式全景

> 上章是 5 个核心抽象。这章把它们组合：5 种编排模式 — Pipeline / Supervisor / GroupChat / Swarm / Graph。掌握这 5 种模式就掌握了 Multi-Agent 系统的"流程图设计语言"。

## 5 种模式一览

```
Pipeline       A → B → C          最简单，顺序执行
Supervisor     中央调度决定下一步   最灵活，单点决策
GroupChat      多 Agent 自由讨论    适合头脑风暴
Swarm          Agent 之间动态交接   去中心化
Graph          任意拓扑            最通用
```

每种模式都有自己的**适用场景**和**实现框架**。下面逐一展开。

---

## 模式 1：Pipeline（流水线）

**结构**：

```
A → B → C → D
```

每个 Agent 完成后，输出传给下一个 Agent。

**适用场景**：

- 任务能清晰拆分成顺序步骤
- 每一步的输出是下一步的输入
- 不需要回退或分支

**实现**：

- **CrewAI**：`context=[previous_task]`
- **LangGraph**：节点串成 chain，`add_edge(a, b)`

**Trade-off**：

- ✅ 简单、清晰、易调试
- ✅ token 可预测
- ❌ 不灵活，一处失败全挂
- ❌ 不支持并行

完整代码：[`code/01_pipeline.py`](./code/01_pipeline.py)

---

## 模式 2：Supervisor（监督者）

**结构**：

```
              ┌─→ Worker A
Supervisor ──┼─→ Worker B
              └─→ Worker C
        ↑
        └── 决定下一步交给谁
```

一个中央调度 Agent 决定下一步把任务交给哪个 Worker。

**适用场景**：

- 任务流程不确定，需要动态决策
- 有多个 Worker，每个擅长不同的事
- 调度逻辑本身比较复杂（不能写死 if/else）

**实现**：

- **LangGraph**：内置 `langgraph.prebuilt.create_supervisor`
- **CrewAI**：用 manager Agent 实现（但不如 LangGraph 直观）

**Trade-off**：

- ✅ 灵活，能应对复杂流程
- ✅ 调度逻辑集中在一个地方
- ❌ Supervisor 是单点故障
- ❌ Supervisor 自己消耗 token

完整代码：[`code/02_supervisor.py`](./code/02_supervisor.py)

---

## 模式 3：GroupChat（群聊）

**结构**：

```
A ←→ B
↑    ↓
C ←→ D
```

多个 Agent 自由讨论，谁都可以发言，通常有一个 Speaker Selection 机制决定下一个发言者。

**适用场景**：

- 头脑风暴、方案评审
- 没有固定的"先后顺序"，需要多视角碰撞
- 任务需要"辩论"来收敛

**实现**：

- **AutoGen**：原生 GroupChat
- **LangGraph**：用循环边模拟

**Trade-off**：

- ✅ 多视角碰撞，常有惊喜输出
- ✅ 适合开放式问题
- ❌ 不可预测，可能陷入"无限讨论"
- ❌ token 烧得快
- ❌ 不适合"必须有正确答案"的任务

完整代码：[`code/03_group_chat.py`](./code/03_group_chat.py)

---

## 模式 4：Swarm（蜂群）

**结构**：

```
A → B → A → C → D
```

Agent 之间动态交接，没有中央调度。每个 Agent 可以决定"下一个该谁做"。

**适用场景**：

- 任务路由需要根据上下文动态决定
- 没有"调度员"角色，Agent 之间平等
- OpenAI Swarm 是这个模式的代表

**实现**：

- **OpenAI Swarm**：`Agent(handoffs=[other_agent])`
- **CrewAI**：用 `allow_delegation=True` 模拟

**Trade-off**：

- ✅ 真正的去中心化
- ✅ 灵活，Agent 自己决定下一步
- ❌ 难调试（控制流分散）
- ❌ 不适合复杂决策（每个 Agent 视野有限）

完整代码：[`code/04_swarm.py`](./code/04_swarm.py)

---

## 模式 5：Graph（图）

**结构**：

```
     ┌─→ B ─┐
A ──┤      ├─→ D
     └─→ C ─┘
```

任意拓扑——节点是 Agent，边是 Handoff。能实现前面 4 种模式的任意组合。

**适用场景**：

- 复杂流程，需要并行 + 条件 + 循环
- 生产级 Multi-Agent 系统（LangGraph 的设计目标）

**实现**：

- **LangGraph**：核心就是 Graph
- `add_node`、`add_edge`、`add_conditional_edges`、`Send` API

**Trade-off**：

- ✅ 最通用，能表达任意流程
- ✅ 自带状态管理、可视化、人机协同
- ❌ 学习曲线陡
- ❌ 过度工程的反模式（用 Graph 实现简单 Pipeline）

完整代码：[`code/05_graph.py`](./code/05_graph.py)

---

## 5 种模式对比

| 模式 | 灵活度 | 复杂度 | 适用场景 | 推荐框架 |
|------|--------|--------|---------|---------|
| Pipeline | 低 | 低 | 顺序任务 | CrewAI |
| Supervisor | 中 | 中 | 动态路由 | LangGraph |
| GroupChat | 高 | 中 | 头脑风暴 | AutoGen |
| Swarm | 高 | 中 | 去中心化 | OpenAI Swarm |
| Graph | 最高 | 高 | 生产系统 | LangGraph |

---

## 选型决策树

```
你的任务是什么？
│
├─ 顺序步骤（如"调研 → 写作 → 校对"）
│   └─ Pipeline（CrewAI 最简单）
│
├─ 动态路由（不同情况走不同路径）
│   └─ Supervisor（LangGraph 最清晰）
│
├─ 多视角讨论（如"3 个 Agent 评审方案"）
│   └─ GroupChat（AutoGen 最成熟）
│
├─ 去中心化（Agent 自己决定下一步）
│   └─ Swarm（OpenAI Swarm）
│
└─ 复杂生产系统（并行 + 条件 + 循环 + 状态）
    └─ Graph（LangGraph）
```

---

## 本章小结

- 5 种编排模式：**Pipeline / Supervisor / GroupChat / Swarm / Graph**
- 选型原则：从简单模式开始，复杂流程才上 Graph
- 实现框架：CrewAI 适合简单场景，LangGraph 适合生产
- 决策树：顺序选 Pipeline，动态选 Supervisor，讨论选 GroupChat，生产选 Graph

## 下篇

[05. 通信与状态](../05-state-and-communication/) — 深入 Agent 之间怎么传数据、共享状态。

## 生产化提示

5 种模式的工程化：

- **Pipeline**：加超时，每个节点失败有 fallback
- **Supervisor**：Supervisor 本身的 prompt 要严格（否则它会乱调度）
- **GroupChat**：限制最大轮数（防无限讨论），加 cost budget
- **Swarm**：所有 handoff 要有日志（难调试，必须有 trace）
- **Graph**：用 LangGraph Studio 可视化，分层（subgraph 复用）