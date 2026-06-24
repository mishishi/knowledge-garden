# 03. Agent 调优：让 agent 听指挥

> Prompt 写得再细，Agent 还是不听指挥？这一章把 v1.14 的所有 Agent-level 调参开关过一遍：`reasoning` / `max_reasoning_attempts` / `multimodal` / `knowledge_sources` / `inject_date` / `cache` / `max_rpm` / `max_iter` / `respect_context_window`。每个开关配「什么时候开、开了会怎样」的实测。

## 调参的核心矛盾

CrewAI 给了 30+ Agent 参数，但 90% 的场景你只需要调 4-5 个。这章不照着文档念，按使用频率分三档：

- **第一档（必调）**：`max_iter` / `cache` / `max_rpm`
- **第二档（按需）**：`reasoning` / `multimodal` / `knowledge_sources` / `inject_date`
- **第三档（高级）**：`respect_context_window` / 自定义模板 / `use_system_prompt`

## 第一档：必调的 3 个

### max_iter：循环上限

**问题**：Agent 默认 `max_iter=20`。Tool 调用一次没拿到想要的结果，它会再调第二次。LLM 觉得「再试一次说不定就对了」，结果烧了 50 块 token 还没完。

**实测**：ch01 那个 Researcher，开了 `max_iter=5` 之后跑 3 次就停，原来要跑 8-10 次。

```python
@agent
def researcher(self) -> Agent:
    return Agent(
        config=self.agents_config["researcher"],
        tools=[SerperDevTool()],
        max_iter=5,   # 5 次循环强制结束
    )
```

**怎么选值**：

- 简单查询（天气、单词翻译）：`max_iter=3`
- 单步研究（一次搜索 + 总结）：`max_iter=5`
- 多步研究（搜索 + 抓详情 + 综合）：`max_iter=10`
- 复杂推理（数学证明、规划）：`max_iter=20`

**不要设 0**（无限循环）。Multi-Agent 系列的 [06. 失败的艺术](../multi-agent/06-failure-handling/) 讲过 watchdog 配合，但 v1.14 的 `max_iter` 本身就够用。

### cache：Tool 结果缓存

**问题**：Agent 调同一个 Tool 两次（比如先查「LangChain」再查「LangChain 是什么」），第二次会重新调 API。重复烧钱。

**实测**：开了 `cache=True` 之后，重复 query 的 token 消耗降 30-50%。

```python
@agent
def researcher(self) -> Agent:
    return Agent(
        config=self.agents_config["researcher"],
        tools=[SerperDevTool()],
        cache=True,   # Tool 结果自动缓存
    )
```

**缓存到哪**：默认本地 SQLite（`~/.crewai/cache.db`）。**生产里建议换成 Redis**，但本地 demo 不用管。

**坑**：缓存 key 是「tool name + 参数 hash」。如果 Tool 返回里包含时间戳（每次返回都不同），缓存命中率会下降——选 Tool 时注意这点。

### max_rpm：限流

**问题**：OpenAI 免费账号有 3 RPM 限制。Agent 短时间内调 10 次 LLM，会被 429 限流。

```python
@agent
def researcher(self) -> Agent:
    return Agent(
        config=self.agents_config["researcher"],
        max_rpm=10,   # 每分钟最多 10 次请求
    )
```

**怎么选**：查你的 LLM provider 限流策略。OpenAI Tier 1 是 60 RPM，Anthropic 是 50 RPM，Ollama 本地无限制。

**坑**：`max_rpm` 是「全局限流」，不是「单 Agent 限流」。如果你 3 个 Agent 都设 `max_rpm=10`，跑起来是共享这个额度。

## 第二档：按需开的 4 个

### reasoning：让 Agent 动手前先规划

**v1.14 新加**。开了之后 Agent 在执行 Task 前会先生成一份「内部计划」，避免边做边想。

```python
@agent
def writer(self) -> Agent:
    return Agent(
        config=self.agents_config["writer"],
        reasoning=True,
        max_reasoning_attempts=2,   # 最多反思 2 次
    )
```

**实测对比**：

- 关掉 `reasoning`：Writer 拿事实直接写，第一版错（漏了关键事实）
- 打开 `reasoning`：`max_reasoning_attempts=2`：Writer 先列出「这篇文章要覆盖 3 个事实，每个 30 字」，再写
- 结果：开 reasoning 之后输出质量明显提升，但 token 多 20%

**什么时候开**：

- 复杂任务（写作、分析、规划）：开
- 简单任务（查天气、查单词）：关（reasoning 浪费 token）
- 高 token 预算 + 质量优先：开 + `max_reasoning_attempts=2`
- 低 token 预算 + 速度优先：关

**坑**：`max_reasoning_attempts=None`（默认值）会让 Agent 无限反思。**必须显式设个上限**（2-3 足够）。

### multimodal：让 Agent 能看图

**v1.14 加**。默认 Agent 只看文字。开了 multimodal，Agent 能处理截图、PDF 第一页、OCR 结果。

```python
@agent
def code_reviewer(self) -> Agent:
    return Agent(
        config=self.agents_config["code_reviewer"],
        multimodal=True,   # 能看图
        tools=[ScreenshotTool()],
    )
```

**实测场景**：

- 截图问题排查：用户上传错误截图，Agent 直接分析
- 文档审阅：上传 PDF，Agent 看图后给反馈
- UI bug 报告：前端 agent 看截图提建议

**坑**：multimodal 模型的 token 计费不一样（图像按 tile 计费）。传 1 张 4K 截图可能 5000+ token。

### knowledge_sources：给 Agent 挂专属知识库

**v1.14 一等公民**。跟 Tool 不一样——Knowledge 是「事实数据」，Tool 是「动作」。第 5 章细讲。

```python
from crewai.knowledge.source.text_file_knowledge_source import TextFileKnowledgeSource

product_doc = TextFileKnowledgeSource(file_paths=["product_manual.md"])

@agent
def support_agent(self) -> Agent:
    return Agent(
        config=self.agents_config["support_agent"],
        knowledge_sources=[product_doc],
    )
```

**对比 Memory**：

- `memory=True`：跨 session 记忆（用过的信息会保留）
- `knowledge_sources=[...]`：静态知识库（产品文档、公司规范）

memory 是「对话历史」，knowledge 是「参考资料」。

### inject_date：避免「我知识截止 2023 年」

**实测痛点**：你让 Agent 写「2026 年 Q1 的市场报告」，它回答「我的知识截止 2023 年 Q1」。

```python
@agent
def analyst(self) -> Agent:
    return Agent(
        config=self.agents_config["analyst"],
        inject_date=True,   # 自动在 prompt 注入当前日期
        date_format="%Y-%m-%d",   # 默认格式
    )
```

效果：Agent 拿到 prompt 里多了「Today's date is 2026-06-24」这种上下文。

**什么时候开**：

- 任务涉及时间敏感内容（市场分析、新闻摘要）：开
- 任务跟时间无关（数学、代码生成）：关

## 第三档：高级调参

### respect_context_window：上下文超限怎么办

**问题**：Agent 跑着跑着，message history 超过 LLM 上下文窗口（比如 GPT-4o 是 128K tokens）。LLM 拒收。

`respect_context_window=True`（**默认 True**）：自动摘要历史消息，腾出空间。

`respect_context_window=False`：硬截断，超限直接报错。

```python
@agent
def long_conversation_agent(self) -> Agent:
    return Agent(
        config=self.agents_config["long_conversation_agent"],
        respect_context_window=True,   # 默认就是这个，显式写清楚意图
    )
```

**实测**：开了 True 之后，session 跑 50 轮不会爆。代价是早期消息被摘要，可能丢细节。

**什么时候关**：

- 任务对早期信息敏感（法律文档分析、合同审阅）：关 + 用更大的模型（200K context）
- 任务对早期信息不敏感（闲聊、迭代优化）：保持 True

### 自定义 prompt 模板

CrewAI 默认有 4 个模板：`system_template` / `prompt_template` / `response_template` / `tool_template`。覆盖它们能精细控制行为。

```python
@agent
def strict_writer(self) -> Agent:
    return Agent(
        config=self.agents_config["strict_writer"],
        system_template="""<|start_header_id|>system<|end_header_id|>

{{ .System }}<|eot_id|>""",
        prompt_template="""<|start_header_id|>user<|end_header_id|>

{{ .Prompt }}<|eot_id|>""",
        response_template="""<|start_header_id|>assistant<|end_header_id|>

{{ .Response }}<|eot_id|>""",
    )
```

**什么时候用**：

- 跨 LLM 兼容性：不同模型要不同的特殊 token（Llama 用 `<|start_header_id|>`，Mistral 用 `<s>`）
- A/B 测试：想精确控制 prompt 变量怎么填
- 提示词工程师：调出最优 prompt

**新手不要碰**。v1.14 默认模板已经覆盖 95% 场景。

### use_system_prompt：老模型兜底

```python
@agent
def legacy_agent(self) -> Agent:
    return Agent(
        config=self.agents_config["legacy_agent"],
        use_system_prompt=False,   # 不发 system message
    )
```

**什么时候用**：

- 老模型不支持 system message（Llama 2 早期版本、部分本地模型）
- 你想用 user message 模拟 system 行为

**99% 场景下保持 True**（默认）。

## 调参速查表

| 参数 | 类型 | 默认 | 调优场景 | 经验值 |
|------|------|------|---------|--------|
| `max_iter` | int | 20 | 防死循环 | 3-10 |
| `cache` | bool | True | 省 token | True（生产） |
| `max_rpm` | int | None | 防限流 | provider 限额 / 2 |
| `reasoning` | bool | False | 复杂任务 | True + attempts=2 |
| `multimodal` | bool | False | 处理图像 | 看场景 |
| `knowledge_sources` | list | [] | 静态知识 | 跟 Tool 不重叠 |
| `inject_date` | bool | False | 时间敏感任务 | True |
| `respect_context_window` | bool | True | 长 session | True（默认） |
| `max_reasoning_attempts` | int | None | reasoning 配套 | 2-3 |
| `use_system_prompt` | bool | True | 老模型 | False（仅 legacy） |
| 自定义模板 | str | 默认 | 跨模型兼容 | 新手别碰 |

## 调参的反模式

**反模式 1：把所有开关都开**

```python
Agent(
    config=...,
    reasoning=True,
    multimodal=True,
    inject_date=True,
    cache=True,
    max_iter=20,
    max_rpm=None,
    knowledge_sources=[...],
)
```

每个开关都吃 token。开了 reasoning + multimodal + knowledge + inject_date，单次 LLM 调用 token 翻 3-4 倍。**按需开**。

**反模式 2：max_iter 设 0（无限）**

「我想让 Agent 一直跑到满意为止」——这会烧光 token 预算。Always 设个上限（20 是硬上限，不要更高）。

**反模式 3：max_rpm 设 None 依赖 provider 兜底**

OpenAI 限流是 429 error 抛回来，Agent 会反复重试。**提前设 `max_rpm` 防止雪崩**。

**反模式 4：reasoning=True + 简单任务**

「查天气」这种任务不需要 reasoning。开 reasoning 反而让 LLM 反复规划，浪费时间。

## 实际调参流程

**第 1 步**：先跑 baseline（全部默认值）。记下输出质量 + token 消耗。

**第 2 步**：如果死循环，调 `max_iter=5`。

**第 3 步**：如果重复调 Tool，开 `cache=True`。

**第 4 步**：如果限流 429，调 `max_rpm`。

**第 5 步**：如果输出质量差，开 `reasoning=True` + `max_reasoning_attempts=2`。

**第 6 步**：如果任务时间敏感，开 `inject_date=True`。

**第 7 步**：如果需要看图，开 `multimodal=True`。

每步改一个参数，看效果。不要一次改 5 个。

## 这章跑完之后你该会什么

- 知道 30+ 参数里 4-5 个关键的
- 按需开关：复杂任务开 reasoning，简单任务关
- 防死循环 + 防限流的标配（max_iter + max_rpm + cache）
- 调参的优先级流程

## 下篇

[04. Tools 与 MCP：给 agent 接手和脚](../04-tools-and-mcp/) — 内置工具选型 + 自定义 Tool + MCP server 接入。
