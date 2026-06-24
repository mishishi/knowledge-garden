# 01. 上手：跑通第一个 Crew

> 30 分钟跑通一个最小可用的 Crew。从安装到 `crew.kickoff()` 拿到结果，不假设你用过 CrewAI 老版本。

## 为什么要学 CrewAI

我自己的 multi-agent 项目 60% 用 CrewAI——上手快（30 分钟跑通第一个）、角色驱动（业务明确）、生态成熟（v1.14 已经 stable）。如果你想从框架入手学 multi-agent，CrewAI 是阻力最小的入口。

v1.14 后官方推荐的写法是 YAML 配置 + `@CrewBase` 装饰器，跟老 v0.x 链式代码差很多。这系列按 v1.14 讲，老版本不兼容。

## 安装

```bash
pip install crewai crewai-tools
```

`crewai` 是核心框架，`crewai-tools` 是官方工具集（搜索、RAG、文件读取等）。装完先验证：

```bash
crewai --version
# crewai version 1.14.x
```

接不同模型：

```bash
# Anthropic Claude
pip install crewai[anthropic]

# OpenAI GPT
pip install 'crewai[openai]'

# 本地 Ollama（要先跑 ollama serve）
pip install crewai[ollama]

# Google Gemini
pip install crewai[google-genai]
```

注意 `crewai-tools` 不是 extras——必须单独装，extras 只装对应模型的 SDK。

## 一个最小 Crew

让一个 Agent 查「2026 年最值得学的 3 个 AI 框架」并输出结果。这个例子用 v1.14 的 `@CrewBase` + YAML 配置（官方推荐写法）。

### 项目结构

```
my_first_crew/
├── pyproject.toml
├── knowledge/
│   └── user_preference.txt
└── src/
    └── my_first_crew/
        ├── __init__.py
        ├── main.py
        ├── crew.py
        └── config/
            ├── agents.yaml
            └── tasks.yaml
```

可以用 `crewai create my_first_crew` 脚手架生成这个结构。

### agents.yaml：定义 Agent

```yaml
# src/my_first_crew/config/agents.yaml
researcher:
  role: >
    AI 框架研究员
  goal: >
    研究 2026 年最值得学的 3 个 AI 框架
  backstory: >
    你是资深 AI 工程师，10 年经验，关注 LLM agent / multi-agent /
    RAG 等方向。每周读 Hacker News 跟 arxiv 新论文。
  llm: claude-sonnet-4-20250514  # 指定模型
  tools:
    - SerperDevTool()  # Google 搜索
```

`role` / `goal` / `backstory` 是 v1.14 三件套——LLM 读这三个字段决定 agent 行为。`tools` 列表是该 agent 能用的 tool。

### tasks.yaml：定义 Task

```yaml
# src/my_first_crew/config/tasks.yaml
research_task:
  description: >
    搜索并总结 2026 年最值得学的 3 个 AI 框架。
    每个框架说明：核心能力、典型场景、值得学的理由。
  expected_output: >
    3 个框架列表，每个 50-100 字。
  agent: researcher
  output_file: output/report.md  # 输出到文件
```

`expected_output` 是 v1.14 必填——告诉 agent 输出应该长什么样。LLM 会按这个格式写。

### crew.py：装配 Agent + Task

```python
# src/my_first_crew/crew.py
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool

@CrewBase
class MyFirstCrew():
    """My First Crew"""

    @agent
    def researcher(self) -> Agent:
        return Agent(config=self.agents_config['researcher'],
                     tools=[SerperDevTool()],
                     verbose=True)

    @task
    def research_task(self) -> Task:
        return Task(config=self.tasks_config['research_task'])

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,  # 顺序执行
            verbose=True,
        )
```

`@CrewBase` 装饰器把 class 标记为 Crew 定义。`@agent` / `@task` / `@crew` 三个装饰器分别定义 agent / task / crew 的方法。`Process.sequential` 是最简单的执行模式——按 task 列表顺序跑。

### main.py：入口

```python
# src/my_first_crew/main.py
from my_first_crew.crew import MyFirstCrew

def run():
    inputs = {
        'topic': '2026 年最值得学的 3 个 AI 框架',
    }
    MyFirstCrew().crew().kickoff(inputs=inputs)

if __name__ == "__main__":
    run()
```

`kickoff(inputs=...)` 启动 crew，传 dict 给 task template（`{topic}` 这种占位符会被替换）。

### 跑

```bash
crewai run
```

或 `python src/my_first_crew/main.py`。第一次跑会调 Anthropic API 烧点钱，几十秒出结果。

## 我第一次跑 Crew 的几个坑

**坑 1：`crewai-tools` 没装**——`pip install crewai` 不自动装 `crewai-tools`，单独装。

**坑 2：API key 没设**——需要 `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` 环境变量。我自己用 `python-dotenv` 从 `.env` 读：

```python
# .env
ANTHROPIC_API_KEY=sk-ant-xxx
SERPER_API_KEY=xxx  # Google 搜索 API key
```

**坑 3：`expected_output` 太模糊**——只写「输出 3 个框架」，LLM 输出格式不一。必须明确「每个 50-100 字」「按这个格式：核心能力 / 典型场景 / 值得学的理由」。

**坑 4：tool 太多**——一个 agent 给 10 个 tool，LLM 选错率 30%。v1.14 之前没限制，v1.14 加了 tool 选择 budget。

## 上手后能做什么

跑通最小 Crew 后，下一步按你需求选：

- **加更多 agent**——多 agent 串行 / 并行（process=Process.hierarchical 是 manager 派活模式）
- **加自定义 Tool**——参考 [第 04 章 Tools 与 MCP](../04-tools-and-mcp/)
- **加 Memory / Knowledge**——参考 [第 05 章 Memory + Knowledge](../05-memory-and-knowledge/)
- **加 Flow 包 Crew**——参考 [第 07 章 Flows](../07-flows/)

我自己的路径：先 Crew 跑通业务（1 周）→ 加 Tool（2 周）→ 加 Memory（1 周）→ 复杂任务上 Flow（2 周）。整个过程 2 个月内 production 上线一个 multi-agent。

[02. Crew 编排](../02-crew-orchestration/) 拆解 v1.14 的 agent / task / crew / process 四个核心抽象——怎么定义角色、怎么串任务、Process 的 3 种模式。
