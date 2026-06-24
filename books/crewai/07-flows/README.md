# 07. Flows：状态化的事件驱动编排

> Crew 适合「一组人干一件事」。但生产里你常需要：「先让 Crew A 跑，结果喂给 Crew B，再让 Crew C 收尾」。这时候 Crew 不够用，需要 Flow——v1.14 引入的状态化事件驱动层。

## 为什么需要 Flow

Crew 的局限：它是一次性"全员上、一起干、输出完事"。但真实生产场景里：

- **多 Crew 串行**：先研究 Crew 跑，结果喂给写作 Crew
- **状态共享**：跑过的中间结果要存起来，下一步用
- **条件分支**：根据上一步结果决定下一步走 A 还是 B
- **错误恢复**：跑一半崩了，重启能从断点继续
- **人机协同**：关键决策时让人拍板

**Flow** 就是 CrewAI 给这些场景的解决方案。v1.14 官方说法：「生产应用推荐用 Flow 包 Crew」。

## Flow 的核心概念

```
Flow（流程）
├── State（状态，跨步骤共享）
├── @start()（入口点）
├── @listen(method)（监听某个方法完成）
├── @router()（根据状态路由）
├── @human_feedback（让人介入）
├── 普通方法（业务流程）
└── 1..N 个 Crew（在步骤里调用）
```

类比成前端：Flow 就像 React 组件 + useState。State 跨步骤共享，方法 = render 函数，Crew = 子组件。

## 第一个 Flow：顺序版

我们把 ch01 的 ResearchCrew 包进 Flow，加个状态。

### Step 1：建项目

```bash
crewai create flow my_research_flow
cd my_research_flow
crewai flow add-crew research-crew
```

生成结构：

```
my_research_flow/
├── main.py                # Flow 入口
├── crews/
│   └── research_crew/
│       ├── research_crew.py
│       └── config/
│           ├── agents.yaml
│           └── tasks.yaml
└── tools/
    └── custom_tool.py
```

### Step 2：把 ch01 的 crew 移过来

`crews/research_crew/config/agents.yaml` 用 ch01 的内容（researcher + writer）。`tasks.yaml` 也用 ch01 的。

`crews/research_crew/research_crew.py` 用 ch01 的 `@CrewBase` 写法。

### Step 3：写 Flow state

`main.py`：

```python
#!/usr/bin/env python
from pydantic import BaseModel
from crewai.flow.flow import Flow, listen, start
from my_research_flow.crews.research_crew.research_crew import ResearchCrew


class ResearchState(BaseModel):
    """Flow 跨步骤共享的状态"""
    topic: str = ""
    research_facts: str = ""
    article: str = ""


class ResearchFlow(Flow[ResearchState]):
    """研究 + 写作的 Flow"""

    @start()
    def get_topic(self):
        """Flow 入口：获取研究主题"""
        # 实际项目里可以读 CLI 参数 / API request / 队列消息
        self.state.topic = "2026 年最值得学习的 AI 框架"
        print(f"主题: {self.state.topic}")

    @listen(get_topic)
    def run_research(self):
        """跑研究 Crew，结果存到 state"""
        print("开始研究...")
        result = ResearchCrew().crew().kickoff(inputs={"topic": self.state.topic})
        self.state.research_facts = result.raw
        print(f"研究完成: {self.state.research_facts[:100]}...")

    @listen(run_research)
    def write_article(self):
        """基于研究结果，写文章"""
        print("基于研究结果写文章...")
        # 这里可以调第二个 Crew（写作 Crew），为了简洁直接拼
        self.state.article = f"# {self.state.topic}\n\n基于研究：\n{self.state.research_facts}"
        print(f"文章: {self.state.article[:100]}...")

    @listen(write_article)
    def save_article(self):
        """存盘"""
        with open("output/article.md", "w", encoding="utf-8") as f:
            f.write(self.state.article)
        print("文章已保存到 output/article.md")


def kickoff():
    ResearchFlow().kickoff()


def plot():
    ResearchFlow().plot("research_flow")
    print("Flow 可视化已保存")


if __name__ == "__main__":
    kickoff()
```

### Step 4：跑

```bash
crewai run
```

或：

```bash
crewai flow kickoff
```

### Step 5：可视化 Flow

```bash
crewai flow plot
```

生成 `research_flow.html` —— 浏览器打开能看到 Flow 的结构图，节点 + 边 + 状态流转。

**这个可视化是 v1.14 Flow 的杀手锏**——debug 复杂 Flow 时一眼看出哪里走错。

## 关键 API 详解

### @start()

Flow 的入口。可以有多个（多入口），但通常一个。

```python
@start()
def init(self):
    self.state.topic = "AI 框架"
```

### @listen(method_name)

监听某个方法完成。**`method_name` 是字符串**（不是引用）：

```python
@listen(get_topic)        # 监听 get_topic 方法
@listen("get_topic")      # 字符串形式也行
@listen([get_topic, run_research])  # 监听多个（等所有都完成才跑）
```

**触发规则**：

- 监听 `method_name`：method 完成后跑
- 监听 `[a, b]`：a 和 b 都完成后才跑（AND）
- 监听 `or_(a, b)`：a 或 b 任一完成就跑（OR）

### @router()

根据 State 决定走哪条分支。**返回字符串**，被 `@listen` 用作 routing key：

```python
from crewai.flow.flow import Flow, listen, start, router


class DecisionFlow(Flow[State]):
    @start()
    def check_input(self):
        self.state.is_long = len(self.state.input) > 1000

    @router(check_input)
    def decide_path(self):
        if self.state.is_long:
            return "long_path"
        return "short_path"

    @listen("long_path")
    def handle_long(self):
        # 长文本处理
        ...

    @listen("short_path")
    def handle_short(self):
        # 短文本处理
        ...
```

`@router` 跟 `@listen` 配合——router 返回什么字符串，下游就监听对应字符串。

### 普通方法

不用装饰器的方法是私有 helper：

```python
class MyFlow(Flow[State]):
    @start()
    def step1(self):
        self._helper()
        self.state.x = 1

    def _helper(self):
        print("internal helper")
```

### 直接调 LLM

Flow 里不一定要走 Crew——可以直接调 LLM 拿结构化输出：

```python
import json
from crewai import LLM
from pydantic import BaseModel, Field
from typing import List


class Section(BaseModel):
    title: str
    description: str


class GuideOutline(BaseModel):
    title: str
    sections: List[Section]


class GuideFlow(Flow[State]):
    @start()
    def make_outline(self):
        llm = LLM(model="openai/gpt-4o-mini", response_format=GuideOutline)
        messages = [
            {"role": "user", "content": f"为主题 {self.state.topic} 生成 3 段大纲"},
        ]
        response = llm.call(messages=messages)
        self.state.outline = GuideOutline(**json.loads(response))
```

**直接调 LLM 比 Crew 快 10 倍**——不需要 Agent 决策循环。Flow 里混用「直接 LLM」和「Crew」是常见模式。

## State：状态管理

State 是 `BaseModel` 子类，**所有跨步骤共享的变量放这里**：

```python
from pydantic import BaseModel
from typing import List, Optional


class MyState(BaseModel):
    topic: str = ""
    research: str = ""
    outline: Optional[List[str]] = None
    final: str = ""
    error: str = ""
    retry_count: int = 0
```

`self.state.xxx` 读写。**Pydantic 校验所有赋值**——写错类型会立刻报错。

### State 持久化

`@persist()` 装饰器把 State 存到 SQLite（默认），崩溃重启能从断点继续：

```python
from crewai.flow.persistence import persist


@persist()
class MyFlow(Flow[MyState]):
    @start()
    def step1(self):
        self.state.x = 1   # 自动存到 SQLite
        crash_here()       # 假设这里崩了

    @listen(step1)
    def step2(self):
        # 重启后，self.state.x 还是 1
        ...
```

跑：

```bash
crewai flow kickoff --resume
```

`--resume` 从断点继续。

**生产推荐**：换 Postgres 替代 SQLite，支持跨机器：

```python
from crewai.flow.persistence import persist

@persist(
    storage_type="postgres",
    connection_string="postgresql://user:pass@localhost/flowdb",
)
class MyFlow(Flow[MyState]):
    ...
```

## Human-in-the-Loop：关键决策让人来

`@human_feedback` 装饰器在 Flow 某一步卡住，让人拍板：

```python
from crewai.flow.human_feedback import human_feedback


class ReviewFlow(Flow[State]):
    @start()
    def generate_draft(self):
        # LLM 生成草稿
        self.state.draft = "..."

    @human_feedback(generate_draft)
    def review(self):
        """暂停，等人类审批"""
        return self.state.draft   # 这个值会被 human 修改后返回

    @listen(review)
    def publish(self):
        # self.state.draft 已经是人审过的版本
        publish_to_blog(self.state.draft)
```

跑起来 Flow 会打印：

```
[Flow] 生成草稿...
[Flow] 等人类反馈...
[Human Review Required]
=================
{草稿内容}
=================
(y)es / (n)o / (e)dit: 
```

输入 `e` 可以编辑草稿，再继续。**适合**：内容发布、合同审核、PR 合并等关键决策。

**生产场景**：human_feedback 改发飞书/Slack/邮件通知 + 异步等待审批回复。v1.14 的 AMP 平台有 Flow HITL Management 功能。

## Conversational Flow：多轮对话

聊天场景常用。`@handle_turn` 装饰器每条消息跑一次：

```python
from crewai.flow.conversational import Flow, handle_turn, ChatSession


class ChatFlow(Flow[State]):
    @handle_turn
    def respond(self, message: str, session: ChatSession):
        # 拿到用户消息，调用 Agent
        response = self.support_agent.kickoff(message)
        session.add_assistant_message(response.raw)
        return response.raw
```

跑：

```python
session = ChatSession()
while True:
    user_input = input("You: ")
    if user_input == "quit":
        break
    response = ChatFlow().kickoff(message=user_input, session=session)
    print(f"Bot: {response}")
```

`ChatSession` 维护历史。**适合**：客服机器人、个人助手。

## Flow vs Crew 决策

| 场景 | 用 Crew | 用 Flow |
|------|---------|---------|
| 单次多人协作 | ✅ | 过度设计 |
| 多 Crew 串行 | 难 | ✅ |
| 状态跨步骤 | Crew 内 TaskContext 够用 | ✅（State + persist） |
| 条件分支 | 难 | ✅（router） |
| 错误恢复 | 重跑整个 | ✅（persist + resume） |
| 人机协同 | 不支持 | ✅（human_feedback） |
| 多轮对话 | 不支持 | ✅（handle_turn） |
| 直接调 LLM | 不支持 | ✅（@start 里 LLM.call） |

**经验法则**：单次多 Agent 任务用 Crew；需要状态/分支/恢复/对话的用 Flow。Flow 可以**包含** Crew，但反过来不行。

## 实战模式：研究 + 写作 + 评审 + 发布

```python
class PublishingFlow(Flow[State]):
    @start()
    def get_topic(self):
        self.state.topic = "..."

    @listen(get_topic)
    def research(self):
        result = ResearchCrew().crew().kickoff(inputs={"topic": self.state.topic})
        self.state.facts = result.raw

    @listen(research)
    def outline(self):
        # 直接 LLM 拿结构化大纲
        self.state.outline = self._make_outline(self.state.facts)

    @listen(outline)
    def write(self):
        # 调用写作 Crew，每个 section 跑一次
        for section in self.state.outline.sections:
            content = WriterCrew().crew().kickoff(inputs={...})
            self.state.draft += content.raw

    @router(write)
    def decide_review(self):
        if self.state.draft:
            return "needs_review"
        return "skip"

    @listen("needs_review")
    @human_feedback(write)
    def human_review(self):
        return self.state.draft

    @listen(human_review)
    def publish(self):
        publish_to_blog(self.state.draft)
```

这个 Flow：研究 → 大纲 → 写作 → 人工审核 → 发布。**5 步串起来，每步可以独立跑 / 独立失败 / 独立恢复**。

## 跑不起来的常见坑

**坑 1：`@listen` 写错引用**

```python
@listen(get_topic())   # ← 错：调用了函数，应该传引用
@listen(get_topic)     # ← 对
```

**坑 2：State 字段没初始化**

```python
class State(BaseModel):
    x: int   # 必填，没默认值

state = State()   # ← 报错
```

修复：

```python
class State(BaseModel):
    x: int = 0   # 默认值
```

**坑 3：Persist 的 SQLite 路径冲突**

跑 `--resume` 找不到上次的状态。检查 `flow_storage.db` 在哪。

**坑 4：Human feedback 在生产环境挂起**

`@human_feedback` 默认是命令行交互，生产会卡住。改用 AMP 平台 + 飞书通知。

**坑 5：Flow 可视化失败**

`flow.plot()` 报错。原因是 `@listen` 引用了不存在的方法名。检查方法名拼写。

## 这章跑完之后你该会什么

- 理解 Flow 的 5 个核心概念（State / @start / @listen / @router / persist）
- 把 ch01 的 Crew 包进 Flow
- 用 @router 做条件分支
- 用 @persist + --resume 做错误恢复
- 用 @human_feedback 做人工审批
- 知道 Flow vs Crew 怎么选

## 下篇

[08. Skills 与生产化基础](../08-skills-and-prod/) — v1.14 引入的 Skills 系统，给 Agent 像装 npm 包一样注入领域知识。
