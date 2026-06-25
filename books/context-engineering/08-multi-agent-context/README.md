# 08. 多 Agent 上下文管理

2025 年我帮一个出海产品做多 agent 架构。系统有 4 个 agent：研究 agent（搜信息）、写作 agent（生成内容）、审核 agent（检查质量）、发布 agent（推到平台）。

**最常出的 bug**：
1. 研究 agent 找到了 5 篇相关文章，但**没把来源 URL 传给写作 agent**——写作 agent 编了一个看起来对但完全是 hallucinate 的来源
2. 写作 agent 写了 2000 字，但**没把"目标受众"信息传给审核 agent**——审核 agent 不知道这是给谁的，质量判断错位
3. 审核 agent 反馈"重写第 2 段"，**没说明"哪里"和"为什么"**——写作 agent 改了 3 段无关的地方

**3 个 bug 都是 context 在多 agent 之间传递时丢失或没传。**

这一章讲**多 agent 系统的 context 怎么管理**——不只是"传什么"，是"怎么传、怎么校验、怎么追溯"。

## 3 种消息传递模式

**1. 黑板模式（Blackboard Pattern）**

所有 agent 共享一个"黑板"——一个共享的数据结构。每个 agent 写黑板的某个槽，读自己需要的槽。

```python
class Blackboard:
    user_query: str
    research_findings: list = []
    draft_content: str = ""
    review_feedback: list = []
    final_content: str = ""
    status: str = "init"  # init | researched | drafted | reviewed | published
```

每个 agent 看到整个黑板，但只操作自己负责的字段。**优点是简单**，每个 agent 都能看到"全局状态"。**缺点是黑板膨胀，agent attention 分散**。

**2. 消息总线模式（Message Bus）**

Agent 之间通过结构化消息通信。**消息只传给相关的 agent，不传无关 agent**。

```python
message_bus.send(
    from_agent="research",
    to_agent="writing",
    type="research_results",
    payload={"sources": [...], "summary": "..."}
)
```

**优点是隔离好，每个 agent context 干净**。**缺点是协调成本高，主协调 agent 要明确"传谁、传什么"**。

**3. 共享内存 + 工具模式（Shared Memory + Tools）**

Agent 之间通过"共享存储" + "工具调用"通信。本质上是**消息总线 + 持久化**。

```python
@mcp.tool()
def save_finding(agent_id: str, key: str, value: dict) -> bool:
    """保存研究发现到共享存储。"""
    
@mcp.tool()
def get_finding(agent_id: str, key: str) -> dict:
    """从共享存储读取研究发现。"""
```

**优点是消息持久化（agent 故障后可恢复）+ 隔离好**。**缺点是 agent 要知道"有哪些 key 可以读写"，需要 schema 文档**。

**2026 年我的默认选择**：消息总线 + 关键状态写到共享内存。**简单场景用黑板，复杂场景用总线。**

## Handoff 的 4 个关键字段

无论用哪种模式，**agent 之间传递的"消息"应该有标准格式**。我自己用的 4 字段协议：

```python
{
    "task_id": "task_12345",  # 任务唯一标识
    "from_agent": "research",  # 来源 agent
    "to_agent": "writing",     # 目标 agent
    "goal": "根据研究发现写一篇 1000 字文章",  # 子任务目标
    "context": {  # 必要的上下文（最少信息原则）
        "user_query": "AI 行业的最新趋势",
        "target_audience": "技术决策者",
        "tone": "professional but accessible"
    },
    "inputs": {  # 输入数据
        "research_findings": [
            {"source": "...", "key_point": "..."},
            ...
        ]
    },
    "output_schema": {  # 期望输出
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "content": {"type": "string"},
            "sources_cited": {"type": "array"}
        }
    },
    "constraints": [  # 约束
        "不要编造来源",
        "字数 800-1200",
        "包含 3 个关键趋势"
    ]
}
```

**关键字段**：
- `goal`：让目标 agent 知道"做什么"
- `context`：只传必要的背景，不传完整对话
- `output_schema`：强制目标 agent 按格式输出
- `constraints`：边界条件（必填、合规、风格）

## Context 传递的"金发姑娘原则"

不是越多越好，不是越少越好。**"刚好够"是金发姑娘原则**。

我自己的判断标准：
- **目标 agent 能"理解任务"** — 不能太少
- **目标 agent 不会"被背景污染"** — 不能太多
- **必要的引用/ID 全传** — 不能漏
- **不必要的对话历史/其他 agent 想法不传** — 不能滥

**实操**：每个 handoff 的 context 控制在 1-5K token。**超过 5K 通常意味着传了太多"不必要的"**。

## 消息的可追溯性

多 agent 系统的最大调试难题是"哪个 agent 的哪个决策错了"。

**3 个必做的"追溯机制"**：

**1. 任务 ID 全程贯穿**：每个任务有唯一 ID，所有 agent 收到的消息都带这个 ID。**调试时按 ID 拉出整条链路**。

**2. 关键决策记日志**：agent 的"重要判断"（"我决定用 X 而不是 Y，因为..."）写到结构化日志。**不是 LLM 输出什么就存什么，是存"决策过程"**。

**3. 消息快照**：每个 agent 收到的消息 + 发出的消息都存快照。**调试时能复现"当时 agent 看到了什么"**。

我自己 2026 年的标准工具栈：**LangSmith / LangFuse / Helicone** 做消息追踪。**必装**。

## 错误恢复

多 agent 系统里 agent 可能失败：
- 工具调用失败
- 输出格式不对（不符合 output_schema）
- 决策错（基于错的信息）
- 超时

**3 个错误恢复模式**：

**1. 重试 + 退避**：简单的工具失败重试 3 次（指数退避）。适合 transient failure（网络超时、临时 503）。

**2. 回滚 + 重做**：agent 输出不符合 schema → 回滚到上一步 + 重新执行。**适合"格式不对"这种结构化错误**。

**3. 升级 + 人工**：连续 3 次失败 → 抛给人工 + 暂停后续 agent。**适合"模型判断错"这种语义错误**。

**重要原则**：错误恢复要让 agent 知道"我之前失败了"——否则它会重复同样的错误。**失败信息要进下一轮 agent 的 context**。

## 多 Agent 协同的 3 个反模式

**1. 主 agent 啥都不干，纯粹转发。** "协调者" agent 只把消息从 A 转到 B 啥也不处理 — 这是浪费 token。**协调者应该做"决策"（哪个 agent 处理、用什么 input）而不是"传递"**。

**2. Agent 互相写对方的 context。** "agent A 直接改 agent B 的 system prompt"——**绝对不要这么做**。这破坏了隔离。**Agent 之间的通信应该通过明确的消息传递，不是直接改对方的 context**。

**3. Agent 串行没有 checkpoint。** "agent A → B → C → D 一条线跑到底"——任何一步失败整个流程挂。**关键节点必须有"checkpoint + 重试"**。

## 实战：内容生产系统的多 Agent 设计

那个内容生产系统，我最终的设计：

```text
[用户] 
   ↓
[主协调 agent]
   ↓ (任务分派)
   ↓----------↓-----------↓
[研究]      [写作]      [审核]
   ↓----------↓-----------↓
   ↓ (返回 4 字段结构化消息)
[主协调]
   ↓ (汇总 + 决策)
[发布 agent]
   ↓
[用户]
```

**每个 agent 的 4 字段 handoff**（实际跑的代码片段）：

```python
handoff_to_writing = {
    "task_id": task_id,
    "from_agent": "research",
    "to_agent": "writing",
    "goal": "写一篇关于 AI 行业最新趋势的 1000 字文章",
    "context": {
        "user_query": original_query,
        "target_audience": "技术决策者",
        "tone": "professional but accessible",
        "key_points": ["agentic workflows", "cost optimization", "evaluation"]
    },
    "inputs": {
        "research_findings": [
            {"source": "Anthropic blog", "key_point": "Claude 4 launched", "date": "2026-05"},
            {"source": "Google research", "key_point": "long context", "date": "2026-04"},
            ...
        ]
    },
    "output_schema": {
        "title": "string",
        "content": "string (800-1200 字)",
        "sources_cited": "array of {url, citation}"
    },
    "constraints": [
        "只引用 inputs 里的来源，不添加新来源",
        "包含 3 个 key_points",
        "中文输出"
    ]
}
```

**这个 handoff 让写作 agent 不需要"看完整研究过程"——只看 4 字段就够了**。**对比之前 12K context 的 handoff，新设计 3-4K**。

**端到端准确率 78% → 94%，单次成本降 60%。**

## 2 个 2026 年趋势

**1. Agent 协议标准化（A2A / ACP）。** Google 推 Agent2Agent 协议、IBM 推 Agent Communication Protocol。**2026 年下半年会看到多 agent 框架开始支持这些标准，让不同框架的 agent 能互相通信**。这跟 MCP 类似——MCP 是工具协议，A2A 是 agent 协议。

**2. Agent Marketplace。** 类似 MCP Server 生态，2026 年开始出现"成品 agent"市场——你可以直接买一个 "Research Agent" 接进自己的系统。**这跟 2010 年代的 iOS App 革命类似**。

下一章讲 Agentic RAG——agent 自己决定查什么、查几次、查多深的"自主检索"。
