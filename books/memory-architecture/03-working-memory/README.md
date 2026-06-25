# 03. Working Memory：会话级上下文工程

Working memory（工作记忆）是 3 层记忆里最基础、但坑最多的一层。它就是 LLM 的 context window，但要在 100K-200K token 的限制下塞进尽可能多的有用信息。

这一章讲 3 个关键技术：**Compaction**（压缩）、**Pruning**（剪枝）、**Recitation**（复述）。

## Compaction（压缩）

**问题**：长会话到后面 context 越堆越多，最后 token 爆掉。最极端情况：对话 200 轮，每轮 2K token，总共 400K token，超过 Claude Opus 4.7 的 200K 上限。

**解决**：定期压缩旧对话。

**实现**：

```python
async def compact_context(messages: list[Message], max_tokens: int = 150_000):
    current_tokens = count_tokens(messages)
    
    if current_tokens <= max_tokens:
        return messages  # 不用压缩
    
    # 保留 system prompt + 最近 N 条
    system_msg = messages[0]
    recent_messages = messages[-10:]  # 保留最近 10 条
    
    # 中间部分压缩成摘要
    middle_messages = messages[1:-10]
    summary = await llm.invoke(
        model="claude-haiku-4.5",  # 用便宜模型
        system="把以下对话压缩成 500 字摘要，保留关键决策和事实",
        user=format_messages(middle_messages),
        max_tokens=2000,
    )
    
    return [
        system_msg,
        Message(role="system", content=f"[对话历史摘要] {summary}"),
        *recent_messages,
    ]
```

**触发时机**：

- 每次新消息进来后检查 token 数
- 超过 80% 容量时触发 compaction
- 每 20 轮强制 compaction 一次（防止 edge case）

**compaction 频率 vs 成本**：

| 频率 | 成本 | 信息损失 |
|------|------|---------|
| 每 50 轮 | 低 | 高 |
| 每 20 轮 | 中 | 中 |
| 每 5 轮 | 高 | 低 |

我推荐每 20 轮 + token 阈值双触发。

**compaction 的隐藏坑**：

- **摘要丢失细节**——用户说过"我不喝咖啡"，摘要可能丢失
- **混淆时序**——"上周"和"上个月"在摘要里可能模糊
- **决策可逆性**——agent 之前做的某个决策，摘要可能删掉背景

**修法**：compaction 摘要里强制包含 3 类信息：

1. 用户偏好 / 约束（"不喝咖啡"）
2. 关键决策（"我们决定用 PostgreSQL"）
3. 未完成任务（"待办：实现用户登录"）

用专门的 prompt 让 LLM 提炼这 3 类。

## Pruning（剪枝）

**问题**：长会话里很多消息其实没用，比如 "好的"、"收到"、"是的" 这些 ack 消息。保留它们浪费 token。

**解决**：剪掉低价值消息。

**实现**：

```python
def prune_messages(messages: list[Message]) -> list[Message]:
    pruned = []
    for msg in messages:
        # 跳过 ack 类短消息
        if len(msg.content) < 10 and msg.content in ["好的", "收到", "是的", "ok", "yes", "no"]:
            continue
        
        # 跳过重复的错误信息（保留最新一条）
        # 跳过已成功完成的工具调用结果
        if msg.role == "tool" and "error" in msg.metadata:
            # 保留，但缩短
            msg.content = truncate(msg.content, 500)
        
        pruned.append(msg)
    
    return pruned
```

**剪枝策略**：

- **ack 类消息**（"好的"）全删
- **错误信息**保留但缩短（500 token 内）
- **重复内容**保留最新一条
- **工具调用结果**保留但缩短到关键字段
- **代码块**如果很长，保留前后 100 token

**实战数据**：经过 prune 后，context token 通常能减少 30-50%。

## Recitation（复述）

**问题**：长 context 里 LLM 容易"忘记"系统 prompt 里的关键约束。我们测过：context 中段之后，LLM 对 system prompt 里"必须 JSON 输出"的遵守率从 92% 掉到 67%。

**解决**：定期把关键信息"复述"到 context 前面或后面。

**实现**：

```python
def inject_recitation(messages: list[Message]) -> list[Message]:
    # 提取关键约束
    key_constraints = [
        "1. 所有输出必须是 JSON",
        "2. 禁止密钥硬编码",
        "3. 用户不喝咖啡",
        "4. 项目命名规范是 camelCase",
    ]
    
    recitation = Message(
        role="system",
        content="[关键约束复述]\n" + "\n".join(key_constraints)
    )
    
    # 插到 system prompt 之后
    return [messages[0], recitation, *messages[1:]]
```

**触发时机**：

- 每次 compaction 后
- context 超过 50K token 时强制注入一次
- 重要任务（如代码生成）开始前注入

**实测效果**：复述后 LLM 对关键约束的遵守率从 67% 升回 88%。

## 三种技术组合

实际生产里 3 个技术组合用：

```python
async def maintain_working_memory(messages):
    # Step 1: Prune（最快、零成本）
    messages = prune_messages(messages)
    
    # Step 2: Compaction if needed
    if count_tokens(messages) > 150_000:
        messages = await compact_context(messages)
    
    # Step 3: Recitation if needed
    if count_tokens(messages) > 50_000:
        messages = inject_recitation(messages)
    
    return messages
```

## 实战经验数据

我跟踪过一个 agent 系统的 working memory 优化前后对比：

| 指标 | 优化前 | 优化后 |
|------|-------|-------|
| 平均会话长度 | 8 分钟 | 23 分钟 |
| 单次会话成本 | $0.30 | $0.18 |
| 用户中途放弃率 | 38% | 12% |
| 关键约束遵守率 | 67% | 88% |

**关键约束遵守率提升 21%** 这一项就值回所有优化成本——少返工就省大钱。

## 进阶：Hierarchical Working Memory

更高级的玩法是把 working memory 也分 2-3 层：

```
System Layer（永久）
   - System prompt
   - User profile
   - Project conventions
   ↓
Recitation Layer（每 N 轮刷新）
   - Key constraints
   - Recent decisions
   ↓
Active Layer（当前）
   - Recent 10-20 messages
   - Current task state
```

这种分层适合超长会话（>100 轮）或复杂多任务 agent。

下一章讲 Episodic Memory——怎么把原始事件高效存到向量数据库。