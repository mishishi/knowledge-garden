# 02. 为什么需要 Multi-Agent

> 上章是单 Agent 查天气、Multi-Agent 写短文。这章具体拆解：单 Agent 在哪些场景下"撑不住"，Multi-Agent 怎么解。

## 场景 1：上下文爆炸

**任务**：让 Agent 读完一个代码仓库的 5 个文件，提取关键 API，然后改其中 1 个文件。

### 单 Agent 解法

```python
agent = Agent(
    role="代码工程师",
    goal="读取 5 个文件 → 提取 API → 修改指定文件",
    backstory=(
        "你是资深 Python 工程师。"
        "你会先 read_file 读 5 个文件，"
        "然后 summarize 提取关键 API，"
        "然后 edit_file 修改指定文件，"
        "然后 run_tests 跑测试..."
    ),
    tools=[read_file, summarize, edit_file, run_tests],
)
```

### 问题暴露

跑起来你会看到这些症状：

1. **Prompt 越写越长**：为了避免 Agent 漏步骤，backstory 写了 200 字
2. **Token 烧得离谱**：5 个文件 + 中间结果全堆在 messages 里
3. **LLM 迷路**：到第 4、5 步时，LLM 已经忘了最初的指令
4. **失败难定位**：第 3 步崩了，不知道是 LLM 忘了还是工具调用出错

### Multi-Agent 解法

```
FileReader（读取员）→ 读 5 个文件并提取 API 列表
       ↓
   CodeAnalyzer（分析员）→ 基于 API 列表分析修改方案
       ↓
   Coder（编码员）→ 执行修改 + 跑测试
```

每个 Agent 只做一件事，context 干净。

完整代码：[`code/scenario_1_multi_agent.py`](./code/scenario_1_multi_agent.py)

---

## 场景 2：角色冲突

**任务**：让 Agent 调研"2026 年最流行的 3 个 Python Web 框架"并写一篇推荐文章。

### 单 Agent 解法

```python
agent = Agent(
    role="全能写手",
    goal="调研 + 写作一气呵成",
    backstory=(
        "你既要是研究员，能深入调研每个框架的优缺点；"
        "又要是写作员，能写出 1000 字流畅的中文推荐文；"
        "还要是产品经理，能从用户视角给建议..."
    ),
)
```

### 问题暴露

跑起来你会看到：

1. **输出分裂**：一会儿在调研细节（"FastAPI 的依赖注入基于..."），一会儿在写营销文（"如果你想要一个快速上手的框架..."），前后语气不连贯
2. **深度不够**：既要又要，LLM 倾向于把每个角色都做得"半瓶水"
3. **Prompt 拧巴**：单一 system prompt 想同时驱动两个角色，互相打架

### Multi-Agent 解法

```
Researcher（研究员）→ 列出 3 个框架 + 每个框架 3 个关键事实（深度优先）
       ↓
   Writer（写作员）→ 基于事实写 1000 字推荐文（表达优先）
```

两个 Agent 各自的 prompt 只聚焦一件事。

完整代码：[`code/scenario_2_multi_agent.py`](./code/scenario_2_multi_agent.py)

---

## 场景 3：调试地狱

**任务**：上面"调研 + 写文章"的任务，单 Agent 输出错了。

### 单 Agent 调试

Agent 输出："推荐 Flask，因为它是 2026 年最流行的 Python 框架。"

哪里出错了？可能性：

- ❓ 是 LLM 凭印象编的（没真的调研）
- ❓ 是 LLM 调研的数据源不对
- ❓ 是 LLM 写作时引用错了事实
- ❓ 是 prompt 没强调"必须基于调研事实写作"

**你只有一个对话历史，没法隔离测试**。

### Multi-Agent 调试

同样错输出，现在能定位：

```
[Researcher 输出] 3 个框架：Flask / Django / FastAPI
                   Flask 事实：简单易学、ORM 支持弱、生态成熟
                   FastAPI 事实：异步支持、类型注解、性能好
                   Django 事实：全功能、企业首选

[Writer 输入] （上面 Research 的输出）
[Writer 输出] 推荐 Flask，因为它是 2026 年最流行的 Python 框架。  ← 错了，但事实没错
```

立刻定位：**问题在 Writer**——它没基于事实写，而是凭印象胡扯。

**Multi-Agent 让你能 step into 每一步**，单 Agent 只能看到一整坨。

---

## 决策树：什么时候上 Multi-Agent

```
你的任务是什么？
│
├─ 单目标、单一决策（如"查天气"、"翻译一句话"）
│   └─ 单 Agent（甚至直接调 LLM）
│
├─ 多目标、需要协作（如"调研 + 写作"、"读代码 + 改代码 + 测试"）
│   └─ Multi-Agent
│
├─ 需要并行加速（如"同时调 5 个 API 汇总结果"）
│   └─ Multi-Agent（用 Graph 模式并行执行）
│
├─ 一个 Agent 调试太痛苦（不知道哪一步出错）
│   └─ Multi-Agent（拆角色后好调试）
│
└─ 你只是想用 LLM 做点问答
    └─ 直接调 LLM，不要套 Agent
```

---

## Multi-Agent 的复杂度代价

上 Multi-Agent 不是免费的。代价清单：

| 代价 | 具体表现 |
|------|---------|
| **Token 翻倍** | 每个 Agent 的 system prompt + 中间结果都消耗 token |
| **延迟增加** | N 个 Agent 顺序执行 = N 倍延迟（并行能缓解） |
| **状态共享复杂** | Agent 之间怎么传数据？什么时候共享内存？ |
| **错误传播** | 一个 Agent 失败，下游全挂 |
| **调试更复杂** | 不再是一个对话历史，是多个 Agent 的执行轨迹 |
| **测试更难** | 输出非确定，传统的单元测试不够用 |

**结论**：Multi-Agent 是工具，不是目标。任务复杂度到了，再上。

---

## 生产化提示

本章的代码是教学 demo，离生产还差：

- 工具调用要加超时和重试
- Agent 之间传数据要 schema 化（不要传自然语言 blob）
- 失败要 circuit breaker（一个 Agent 失败不能拖垮整个）
- 监控每个 Agent 的 token 消耗和延迟

监控细节见 [第 8 章 可观测性与成本](../08-observability-and-cost/)，完整 Checklist 见 [第 10 章 生产化 Checklist](../10-production-checklist/)。