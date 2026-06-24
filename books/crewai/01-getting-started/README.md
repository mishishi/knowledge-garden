# 01. 上手：跑通第一个 Crew

> 30 分钟跑通一个最小可用的 Crew。从安装到 `crew.kickoff()` 拿到结果，不假设你用过 CrewAI 老版本。

## 为什么要学 CrewAI

如果你读过 [Multi-Agent in Practice](../multi-agent/01-your-first-agent/)，那套「研究员 + 写作员」的 demo 其实是用 CrewAI 跑的。Multi-Agent 系列讲的是「概念 + 框架对比」，这系列专门拆 CrewAI——v1.14 后官方推荐的写法是 YAML 配置 + `@CrewBase` 装饰器，跟老 v0.x 链式代码差很多。

如果你没读 Multi-Agent 系列也没关系，CrewAI 是个独立的 Multi-Agent 框架，可以单用。

## 安装

```bash
pip install crewai crewai-tools
```

`crewai` 是核心框架，`crewai-tools` 是官方工具集（搜索、RAG、文件读取等）。装完先验证一下：

```bash
crewai --version
# crewai version 1.14.x
```

如果你要接 Claude / Gemini / 本地 Ollama，再装对应 SDK：

```bash
# 用 Anthropic Claude
pip install crewai[anthropic]

# 用本地 Ollama（要先跑 ollama serve）
pip install crewai[ollama]
```

## 一个最小 Crew

我们要做的事：让一个 Agent 查「2026 年最值得学的 3 个 AI 框架」并输出结果。

### 第 1 步：建项目结构

CrewAI v1.14 官方推荐的项目结构（`crewai create` 生成的）：

```
my_first_crew/
├── pyproject.toml
├── .env                  # 放 API key
├── README.md
└── src/
    └── my_first_crew/
        ├── __init__.py
        ├── main.py       # 入口
        └── crews/
            └── research_crew/
                ├── research_crew.py   # @CrewBase 装饰器
                └── config/
                    ├── agents.yaml    # Agent 定义
                    └── tasks.yaml     # Task 定义
```

手搓也行，但用 `crewai create` 生成的脚手架更省事：

```bash
crewai create crew my_first_crew
cd my_first_crew
```

这会生成上面的目录结构。

### 第 2 步：写 agents.yaml

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
  llm: openai/gpt-4o-mini   # 或 anthropic/claude-3-5-sonnet 等
```

关键字段：
- `role`：Agent 的「身份标签」，影响语气和视角
- `goal`：`{topic}` 会被 `kickoff(inputs={...})` 替换
- `backstory`：给 LLM 看的详细背景，决定行为倾向
- `llm`：模型名。v1.14 之后格式是 `provider/model`

### 第 3 步：写 tasks.yaml

`src/my_first_crew/crews/research_crew/config/tasks.yaml`：

```yaml
research_task:
  description: >
    调研主题 {topic}。
    用 2026 年的视角，列出 3 个最值得关注的 AI 框架，
    每个框架给出：名称、为什么值得学、典型使用场景。
  expected_output: >
    一份 markdown 格式的清单，包含 3 个框架，
    每个框架有标题和 2-3 句说明。
  agent: researcher
  output_file: output/report.md   # 结果写到文件
```

关键字段：
- `description`：给 LLM 看的任务描述
- `expected_output`：期望输出格式。LLM 会照这个对齐输出
- `agent`：绑定到上面定义的 `researcher`
- `output_file`：自动写到磁盘

### 第 4 步：写 crew class

`src/my_first_crew/crews/research_crew/research_crew.py`：

```python
from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool
from typing import List


@CrewBase
class ResearchCrew:
    """Research crew used to scout AI frameworks."""

    agents: List[BaseAgent]
    tasks: List[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"],
            verbose=True,
            tools=[SerperDevTool()],   # 联网搜索工具
        )

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_task"],
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
```

`@CrewBase` 把这个类注册成 CrewAI 的「Crew 工厂」。`@agent` 和 `@task` 装饰器把方法名（`researcher` / `research_task`）和 YAML 里的 key 绑起来——YAML 里的 key 必须跟方法名一致，否则会报 KeyError。

### 第 5 步：写 main.py

`src/my_first_crew/main.py`：

```python
from my_first_crew.crews.research_crew.research_crew import ResearchCrew


def run():
    inputs = {
        "topic": "2026 年最值得学习的 AI 框架",
    }
    ResearchCrew().crew().kickoff(inputs=inputs)


if __name__ == "__main__":
    run()
```

### 第 6 步：配 API key

`.env`：

```
OPENAI_API_KEY=sk-xxx
SERPER_API_KEY=xxx   # Serper 搜索工具的 key，去 serper.dev 申请
```

`SERPER_API_KEY` 在 [serper.dev](https://serper.dev/) 注册就有免费额度（每月 2500 次查询）。`SerperDevTool` 是个 Google Search API 的轻量替代。

### 第 7 步：跑起来

```bash
crewai install      # 装依赖
crewai run          # 跑 main.py
```

或者直接：

```bash
python -m my_first_crew.main
```

你应该看到类似输出：

```
[Agent: AI 框架研究员]
[Tool Call] SerperDevTool(query="2026 AI frameworks")
[Tool Result] [...]  # 搜索结果
[Agent Output] 1. LangGraph - ...  2. CrewAI - ...  3. AutoGen - ...
```

`output/report.md` 里能看到最终的 markdown 报告。

## 跑不起来的常见坑

**坑 1：`ModuleNotFoundError: No module named 'my_first_crew'`**

CrewAI 用 src layout，import 路径是从 src/ 算起。`crewai install` 会自动 `pip install -e .`，不跑这步就找不到包。

**坑 2：`KeyError: 'researcher'`**

YAML 里的 key（`researcher`、`research_task`）必须跟 `@agent` / `@task` 方法名**完全一致**。拼写错了或者方法名改了都会报。

**坑 3：`openai.AuthenticationError`**

`.env` 里没设 `OPENAI_API_KEY`，或者设了但没加载。确认 `.env` 在项目根目录，且 `crewai install` 跑过。

**坑 4：搜索工具返回空结果**

`SERPER_API_KEY` 没配或额度用完。先去 [serper.dev](https://serper.dev/) 看 dashboard 余额。

**坑 5：Agent 一直循环不结束**

`verbose=True` 你会看到 Agent 反复调 Serper。每次拿到结果都"再查一下"。给 Agent 加 `max_iter=5` 限制：

```python
@agent
def researcher(self) -> Agent:
    return Agent(
        config=self.agents_config["researcher"],
        verbose=True,
        tools=[SerperDevTool()],
        max_iter=5,   # 最多 5 次循环
    )
```

循环防护细节第 3 章讲。

## YAML 还是 Python：v1.14 的取舍

老版本 CrewAI 教程（v0.x）都是纯 Python：`Agent(role=..., goal=...)`。v1.14 官方推 YAML 配置。两种写法都能跑，区别：

| 维度 | YAML 配置 | Python 代码 |
|------|----------|------------|
| Prompt 跟代码分离 | ✅ 改 prompt 不动代码 | ❌ 改 prompt 要重新部署 |
| 类型检查 | ❌ YAML 不做 schema 校验 | ✅ IDE 能补全 |
| 动态配置 | ❌ 写死的字符串 | ✅ 可以根据运行时参数 |
| 团队协作 | ✅ 非工程师也能改 prompt | ❌ 必须懂 Python |
| 调试 | ⚠️ YAML 报错不直观 | ✅ 直接 IDE 单步 |

**推荐**：Prompt 部分（role / goal / backstory / description）放 YAML，方便调。结构部分（tools / llm / max_iter）放 Python，方便用 IDE。

混用是常态，别纠结。

## 跑完之后能做什么

跑通上面这个 demo 后，你已经能：

- 跑一个单 Agent 单 Task 的最小 Crew
- 用 YAML 管理 Prompt
- 联网搜索（SerperDevTool）

下一章加第二个 Agent 进去，变成 2 人小组：研究员 + 写作员。研究员查完，写作员拿结果写文章。

## 下篇

[02. Crew 编排：Process 选型与协作](../02-crew-orchestration/) — 加第二个 Agent，看 Sequential / Hierarchical / Async 怎么选。
