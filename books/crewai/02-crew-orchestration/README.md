# 02. Crew 编排：Process 选型与协作

> 上章是单 Agent 单 Task 的最小 Crew。这章加第二个 Agent，把它从「一人干活」升级成「两人流水线」，再讨论 Sequential / Hierarchical / Async 三种 Process 怎么选。

## 目标：从 1 人到 2 人

ch01 那个 Researcher Agent 只做「查 3 个 AI 框架」一件事。生产里这远远不够——查完还得写、还得校、还得改。我们加一个 Writer，让它把研究结果写成短文。

最后会变成这样：

```
Researcher → 3 条事实 → Writer → 100 字短文
```

这是 Multi-Agent 里最经典的 **Pipeline** 模式。Multi-Agent 系列 [04. 编排模式全景](../multi-agent/04-orchestration-patterns/) 讲过理论，这章只讲 CrewAI 里怎么实现。

## 给 ch01 的 Crew 加 Writer

### 第 1 步：改 `agents.yaml` 加一个 writer

`src/my_first_crew/crews/research_crew/config/agents.yaml`：

```yaml
researcher:
  role: >
    AI 框架研究员
  goal: >
    找出 {topic} 领域最值得关注的 3 个框架，每个框架配 2-3 句说明
  backstory: >
    你是一个技术分析师，擅长从一堆炒作里筛出真正值得关注的东西。
    你给出的判断必须有事实支撑，不确定的会明确说"不确定"。
  llm: openai/gpt-4o-mini

writer:
  role: >
    科技文章写手
  goal: >
    基于研究员给的事实，写一段 100 字以内的中文短文
  backstory: >
    你是一个技术写作员，文笔清晰。你写的内容必须严格基于事实，
    不允许添加研究员没给的信息。引用的事实要标注是哪个框架的。
  llm: openai/gpt-4o-mini
```

注意 writer 的 `backstory` 明确写了「必须严格基于事实，不允许添加」。这是关键约束——LLM 默认会「编」。后面 ch06 讲怎么用 Pydantic 模型再锁一层。

### 第 2 步：改 `tasks.yaml` 加 writing task 并连 context

`src/my_first_crew/crews/research_crew/config/tasks.yaml`：

```yaml
research_task:
  description: >
    调研主题 {topic}。
    列出 3 个最值得关注的 AI 框架，每个框架给出名称和 2-3 句说明。
  expected_output: >
    一份 markdown 格式的清单，包含 3 个框架的「名称 + 说明」。
  agent: researcher
  output_file: output/facts.md

writing_task:
  description: >
    基于上面研究员给的事实，写一段 100 字以内的中文短文。
    严格基于事实，不要添加新框架或新事实。
  expected_output: >
    一段 100 字以内的中文短文，markdown 格式，不带标题。
  agent: writer
  context:
    - research_task   # ← 关键：依赖上一个 Task 的输出
  output_file: output/article.md
```

**关键参数：`context`**。`writing_task` 加了 `context: [research_task]`，CrewAI 会自动把 `research_task` 的输出喂给 `writing_task`。这是 v1.14 后 Task 间传数据的标准方式。

如果忘了写 `context`，writer 拿不到 researcher 的输出，会凭印象编。**这是新手最常犯的错。**

### 第 3 步：改 `research_crew.py` 加 writer

`src/my_first_crew/crews/research_crew/research_crew.py`：

```python
from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool
from typing import List


@CrewBase
class ResearchCrew:
    """Research + writing crew."""

    agents: List[BaseAgent]
    tasks: List[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"],
            verbose=True,
            tools=[SerperDevTool()],
            max_iter=5,
        )

    @agent
    def writer(self) -> Agent:
        return Agent(
            config=self.agents_config["writer"],
            verbose=True,
        )

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_task"],
        )

    @task
    def writing_task(self) -> Task:
        return Task(
            config=self.tasks_config["writing_task"],
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,   # ← 顺序：researcher 先，writer 后
            verbose=True,
        )
```

`@agent` 方法名（`researcher`、`writer`）必须跟 YAML 里的 key 完全一致。YAML 里加 `writer:`，Python 这边也要加 `def writer(self)`。

### 第 4 步：跑

```bash
crewai run
```

你会看到 `output/facts.md` 和 `output/article.md` 两个文件。`article.md` 是 100 字短文，引用了 `facts.md` 里的内容。

## Process 选型：sequential vs hierarchical vs async

`Process` 参数决定 Agent 怎么协作。v1.14 有 3 个值：

### Process.sequential（最常用）

Agent 顺序执行，一个完了才跑下一个。**默认选择**。

适用场景：

- 任务可以拆成清晰的前后步骤（Pipeline）
- 步骤之间有数据依赖（A 的输出是 B 的输入）
- 你不想花时间想「调度逻辑」

```python
Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.sequential,   # 默认就是 sequential，可以不写
)
```

### Process.hierarchical

加一个隐藏的 **Manager Agent**（你不用显式定义），它用更强的模型（默认 `manager_llm`）做任务分配和协调。

适用场景：

- 任务路由复杂（不同情况该派给谁不确定）
- 你想让 LLM 决定下一步给谁，不是写死顺序

```python
Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.hierarchical,
    manager_llm="openai/gpt-4o",   # 用更强的模型当 manager
)
```

**坑**：hierarchical 会让 manager 调 N 次 LLM（每步决策都问一次），token 成本比 sequential 高 30-50%。**大多数场景下 sequential 就够**。Multi-Agent 系列的 [04. 编排模式全景](../multi-agent/04-orchestration-patterns/) 讲过 supervisor 的代价。

### Process.hierarchical 实际跑出来的样子

```
[Manager] 决定下一步：派给 Researcher 调研
[Researcher] 调 SerperDevTool 查资料
[Manager] 决定下一步：派给 Writer 写文章
[Writer] 基于事实写短文
[Manager] 决定：任务完成，结束
```

Manager 不干活，只做调度。每次决策都吃 token。

### 没有 Process.async

`async` 不是 Process 的值，是 **Task** 的属性：

```yaml
research_task_v1:
  description: 调研主题 1
  agent: researcher
  async_execution: true   # ← 这个 Task 异步跑

research_task_v2:
  description: 调研主题 2
  agent: researcher
  async_execution: true   # ← 这个也异步

writing_task:
  description: 基于两个调研结果写文章
  agent: writer
  context:
    - research_task_v1
    - research_task_v2   # 等两个都完成才跑
```

两个 research 任务**并行**跑，writer 等两个都完才动。**这个用法很常见**——同时调研多个主题，省一半时间。

但有个坑：v1.14 里 `async_execution` 必须配合 `kickoff_async()` 才有真并行效果。`kickoff()` 调同步版本来跑 async task，会**串行**执行（行为不直观）。写法：

```python
import asyncio

async def run():
    result = await ResearchCrew().crew().kickoff_async(inputs={...})
    print(result.raw)

asyncio.run(run())
```

## allow_delegation：让 Agent 互相派活

默认 Agent 不能让别人帮自己干活（`allow_delegation=False`）。开了之后，Agent 可以决定「这事该 Researcher 做」，自动派单。

```python
@agent
def writer(self) -> Agent:
    return Agent(
        config=self.agents_config["writer"],
        verbose=True,
        allow_delegation=True,   # ← Writer 可以把任务派给 Researcher
    )
```

**坑 1**：开了之后 token 翻倍。LLM 每步都要决定「自己做还是派给别人」，多一次思考。

**坑 2**：Agent 经常派错活。LLM 不懂团队分工，写「派给 Researcher」可能把「写文章」也派回去，导致循环。

**建议**：生产里默认关。只有你**明确**知道任务有动态路由需求时再开。

## 多人 Crew 的常见拓扑

把 2 人扩展到 3-4 人，常用这 4 种拓扑：

### Pipeline（最简单）

```
A → B → C
```

每步只依赖上一步的输出。`context=[previous_task]`。

适用：内容流水线、代码 review、文档生成。

### Diamond（菱形）

```
      B
    /   \
  A       D
    \   /
      C
```

B 和 C 并行跑（A 的输出同时给 B 和 C），D 汇总 B+C 的输出。`async_execution=True` + `context=[A_task, B_task, C_task]`。

适用：调研 + 写作（同时调研多主题，最后汇总写一篇文章）。

### Star（中心）

```
B → A → C
    ↓
    D
```

A 是中心节点，B/C/D 都给 A 输出，A 汇总再分发。Hierarchical Process 模拟这种。

适用：需要中心节点做整体协调。

### Graph（任意）

`@router()` + 条件分支。ch07 Flow 讲。

## 跑不起来的常见坑

**坑 1：Writer 写的内容跟 Researcher 的事实无关**

忘了 `context=[research_task]`。Writer 不知道 Researcher 查了什么，凭印象写。

**坑 2：顺序错乱，Writer 先跑 Researcher 后跑**

`process=Process.sequential` 顺序是按 `tasks=[...]` 列表顺序来的。如果你把 `writing_task` 写在前，它会先跑。**YAML 里 task 顺序就是执行顺序**。

**坑 3：Task 用了同一个变量名**

```yaml
research_task:
  description: 调研 {topic}  # topic 是 kickoff(inputs={...}) 传入的

writing_task:
  description: 基于事实写文章  # ← 没用到 {topic}，但如果忘了引用上文的输出，会编
```

`{topic}` 这种占位符只对当前 task 的 `description` 生效。task 之间的数据传递靠 `context`。

**坑 4：Hierarchical 跑完 manager_llm 报错**

`manager_llm` 必须配。如果用 Anthropic / Ollama，确保 API key / 端口对。常见错误：

```
openai.AuthenticationError: No API key provided.
```

但你明明配了 OpenAI key——因为 manager_llm 默认是 OpenAI。配 Anthropic 时要么显式 `manager_llm="anthropic/claude-3-5-sonnet"`，要么设环境变量 `OPENAI_MODEL_NAME`（但这只对 OpenAI 系列有效）。

**坑 5：async task 没真并行**

用了 `async_execution: true` 但调了 `kickoff()`（同步版）。要么改成 `kickoff_async()`，要么直接用 sequential。

## 怎么选 Process

| 场景 | 推荐 Process | 原因 |
|------|------------|------|
| 任务有清晰前后步骤 | sequential | 简单、可预测 |
| 调研多主题，最后合并 | sequential + async_execution | 节省时间 |
| 任务路由复杂、动态决策 | hierarchical | 让 LLM 调度 |
| 同一个输入给多个 Agent | sequential（各自 context） | 不需要并行 |
| 高 token 预算 + 复杂路由 | Flow（ch07）| 比 hierarchical 更可控 |

**经验法则**：先 sequential，撑不住再上 hierarchical 或 Flow。Hierarchical 调试比 sequential 难——manager 是隐藏的，verbose 输出的不是你写的 prompt。

## 这章跑完之后你该会什么

- 把 ch01 的单 Agent Crew 升级成 2-3 人小组
- 配 `context` 让 Task 间传数据
- 选对 Process（绝大多数时候是 sequential）
- 理解 `allow_delegation` 代价
- 知道 async_execution + kickoff_async 的正确组合

## 下篇

[03. Agent 调优：让 agent 听指挥](../03-agent-tuning/) — 同一段 Prompt 不同模型跑出来天差地别，reasoning / knowledge_sources / multimodal / inject_date 这些开关怎么调。
