# 01. 你的第一个 Agent

> 本章用 30 分钟带你写出能调用工具的 Agent。从零开始，不假设你会 LLM 编程。

## 什么是 Agent？

3 个词讲清楚：

- **LLM**：大脑。能读懂你的问题，能写出回答。
- **Tool**：双手。能做实际的事——查数据库、调 API、读文件、发邮件。
- **Loop**：决策循环。LLM 决定"要不要调工具 → 调哪个 → 调完再决定下一步"。

**Agent = LLM + Tools + Loop**。

只调 LLM = 聊天机器人。能调工具 = Agent。

## 一个具体的场景

你想做一个"出行规划 Agent"，用户问"明天东京天气怎么样"：

| | LLM 直接回答 | Agent 回答 |
|---|---|---|
| 输入 | "明天东京天气怎么样？" | "明天东京天气怎么样？" |
| LLM 思考 | （凭训练数据编一个答案） | "我需要查询天气" → 调用工具 |
| 输出 | "明天东京 22°C 晴"（**编的，可能是错的**） | "明天东京 22°C 晴"（**真实数据**） |

**关键差别**：Agent 能拿到真实世界的数据，不是 LLM 在"猜"。

## 代码：单 Agent 示例

完整代码在 [`code/single_agent.py`](./code/single_agent.py)。这里拆开讲。

### 第 1 步：告诉 LLM 它能用什么工具

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的当前天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名"}
                },
                "required": ["city"]
            }
        }
    }
]
```

这一段 JSON 是 OpenAI 的 [Function Calling](https://platform.openai.com/docs/guides/function-calling) 协议——你告诉 LLM "你可以调一个叫 `get_weather` 的函数，它接受 `city` 参数"。LLM 不真执行函数，它只决定"要不要调 + 传什么参数"。

### 第 2 步：实现工具函数

```python
def get_weather(city: str) -> str:
    mock_data = {"tokyo": "东京: 22°C, 晴, 湿度 60%", ...}
    return mock_data.get(city.lower(), f"{city}: 暂无数据")
```

这里用 mock 数据演示，生产环境换成真实 API（OpenWeatherMap、和风天气等）。

### 第 3 步：跑 Agent 循环

```python
def run_agent(user_message: str) -> str:
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools,
        )
        msg = response.choices[0].message

        if msg.tool_calls:
            # LLM 想调工具 → 执行工具 → 把结果加进对话 → 继续循环
            messages.append(msg)
            for tool_call in msg.tool_calls:
                result = get_weather(...)
                messages.append({...})
            continue

        # LLM 直接回答 → 结束
        return msg.content
```

这就是 Agent 的核心循环：**LLM 决策 → 工具执行 → 结果反馈 → LLM 再决策**。直到 LLM 不再调用工具，输出最终答案。

### 跑起来

```bash
cd code
pip install -r requirements.txt
export OPENAI_API_KEY=sk-xxx
python single_agent.py
```

你应该看到类似输出：

```
[用户] 东京今天天气怎么样？
[Agent 思考] 需要调用 1 个工具
[Agent 调用] get_weather({'city': 'Tokyo'})
[工具返回] 东京: 22°C, 晴, 湿度 60%
[Agent 回答] 东京今天 22°C，晴朗，湿度 60%，适合出门。
```

## 单 Agent 的局限

任务升级：让 Agent 写一篇关于 "Multi-Agent 系统" 的短文。

单 Agent 解法：

```python
agent = Agent(
    role="全能写手",
    goal="调研 + 写作一气呵成",
    backstory="你既是研究员又是写作员..."  # ← 开始别扭
)
task = Task(
    description="先调研 3 个事实，然后写一篇 100 字短文",
    expected_output="一篇短文",
)
```

问题暴露：

1. **角色混乱**：一个 Agent 既要调研又要写作，prompt 越写越拧巴
2. **上下文混乱**：调研过程的中间结果和最终文章混在一个对话历史里
3. **难以调试**：写崩了不知道是"调研没调好"还是"写作没发挥好"
4. **复用性差**：换个主题，prompt 整个要重写

## 解法：Multi-Agent

把任务拆成两个角色：

```
Researcher（研究员） → 调研 3 条事实
        ↓
    Writer（写作员） → 基于事实写短文
```

每个 Agent 只做一件事，prompt 干净，调试简单。

## 代码：Multi-Agent 示例

完整代码在 [`code/multi_agent.py`](./code/multi_agent.py)。这里用 [CrewAI](https://crewai.com)——一个让 Multi-Agent 写起来像写单 Agent 一样简单的框架。

```python
from crewai import Agent, Task, Crew

researcher = Agent(
    role="研究员",
    goal="调研 {topic} 的 3 个关键事实",
    backstory="你是一个专业研究员，擅长快速找到关键事实。",
    allow_delegation=False,
)

writer = Agent(
    role="写作员",
    goal="基于研究员的事实，写一段 100 字以内的短文",
    backstory="你是一个技术写作员，文笔清晰。",
    allow_delegation=False,
)

research_task = Task(
    description="调研主题：{topic}。输出 3 条关键事实。",
    expected_output="3 条事实的列表",
    agent=researcher,
)

write_task = Task(
    description="根据事实写 100 字以内短文。",
    expected_output="一段 100 字以内的短文",
    agent=writer,
    context=[research_task],  # 关键：依赖前一个任务的输出
)

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    verbose=True,
)

result = crew.kickoff(inputs={"topic": "Multi-Agent AI 系统"})
print(result)
```

跑起来：

```bash
cd code
python multi_agent.py
```

你应该看到 CrewAI 自动编排两个 Agent 顺序执行：

```
[研究员开始] 调研 Multi-Agent AI 系统的 3 个关键事实
[研究员输出] 1. Multi-Agent ... 2. ... 3. ...
[写作员开始] 基于事实写 100 字以内短文
[写作员输出] Multi-Agent AI 系统是...
```

## 单 Agent vs Multi-Agent：什么时候用哪个

| 场景 | 建议 |
|------|------|
| 单目标、单一决策（如查天气） | **单 Agent**，别过度设计 |
| 多目标、需要协作（如调研 + 写作） | **Multi-Agent** |
| 任务可以被清晰拆分成独立子任务 | **Multi-Agent** |
| 需要并行加速（同时调多个 API） | **Multi-Agent** |
| 一个 Agent 调试太痛苦 | **Multi-Agent**（拆角色后好调试） |
| 你只是想用 LLM 做点简单问答 | **直接调 LLM**，不需要 Agent |

**核心原则**：能用单 Agent 解决就别上 Multi-Agent。Multi-Agent 增加复杂度（角色设计、状态共享、错误处理），复杂度只在能换来清晰度的时候才值得。

## 本章小结

- **Agent = LLM + Tools + Loop**：核心是一个循环，直到 LLM 决定不再调工具
- **Function Calling**：告诉 LLM 它能用什么工具，LLM 只"决定"，执行由你来做
- **Multi-Agent**：把"既要又要"的单 Agent 拆成多个角色单一的 Agent
- **决策原则**：复杂度过载才上 Multi-Agent，单 Agent 能搞定就别拆

## 下篇预告

第 2 篇 [为什么需要 Multi-Agent](../02-why-multi-agent/) 会用 3 个真实场景，具体展示单 Agent 撑不住的瞬间，以及 Multi-Agent 如何解。看完你会建立一个判断标准：什么任务"该上" Multi-Agent。

## 生产化提示

本章的代码是教学版，离生产还差：

- 工具要换成真实 API（带重试、超时、降级）
- LLM 调用要有限流、并发控制
- 错误处理：工具失败怎么办？LLM 返回 malformed JSON 怎么办？
- 日志：记录每次决策和工具调用，便于调试

这些会在第 8 篇 [可观测性与成本](../08-observability-and-cost/) 和第 10 篇 [生产化 Checklist](../10-production-checklist/) 展开。