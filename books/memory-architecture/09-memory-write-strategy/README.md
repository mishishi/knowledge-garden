# 09. Memory 写入策略：什么时候写、写什么

长期记忆系统的成本主要由**写入量**决定。乱写 → 存储爆炸 + 检索慢 + 成本飙升。**写什么、不写什么**，是设计的关键决策。

## 写入的 3 类事件

不是所有事件都值得长期保存。3 类值得写：

**a. 决策性事件**

agent 做了某个判断、选了某个方案、犯了某个错。这些是"agent 学习"的素材。

```python
# 例子：agent 选了某个 API 库
{
    "type": "decision",
    "content": "选了 axios 而非 fetch",
    "reasoning": "项目已有 axios 依赖，需要拦截器统一处理 401",
    "alternatives": ["fetch", "ky", "got"],
    "outcome": "已实现，运行正常"
}
```

**b. 偏好性事件**

用户表达了某种偏好、习惯、约束。这是"个性化"的素材。

```python
# 例子：用户偏好
{
    "type": "preference",
    "content": "用户不喝咖啡",
    "evidence": "用户在 3 次对话中明确表示",
    "scope": "user:u_123"
}
```

**c. 失败性事件**

agent 犯了错、用户纠正了。这是"从错误中学习"的素材。

```python
# 例子：agent 犯错
{
    "type": "failure",
    "content": "生成了下划线字段而非驼峰字段",
    "user_correction": "项目所有 API 返回必须驼峰",
    "root_cause": "AI 没看到项目的格式转换工具 utils/format.ts",
    "fix_applied": "调用 utils.format.snake_to_camel 包装"
}
```

## 不写什么

**不写闲聊**：用户说"今天天气不错"、agent 说"好的"——这些不写。

**不写中间过程**：agent 内部思考（"我先看看 A，然后 B，然后 C"）——除非这些思考对将来有用。

**不写重复内容**：5 分钟内重复问了同一问题——合并。

**不写敏感信息**：密码、token、身份证号——过滤或脱敏。

**不写无关上下文**：跟 agent 任务无关的对话。

## 何时写入

**策略 1：实时写入**

每条消息进来时立即评估是否要写。

```python
async def should_write(message, response, metadata) -> bool:
    # 决策性：agent 做了选择
    if metadata.get("decision_made"):
        return True
    
    # 偏好性：用户表达了偏好
    if detect_preference(message):
        return True
    
    # 失败性：用户纠正或报错
    if metadata.get("error") or metadata.get("user_correction"):
        return True
    
    # 任务完成
    if metadata.get("task_completed"):
        return True
    
    return False
```

优点：知识立即可用。缺点：每条消息都跑一次判断逻辑。

**策略 2：批量写入**

每隔 N 分钟或 N 条消息跑一次批量评估。

```python
async def batch_write(messages: list, responses: list):
    # 评估哪些值得写
    important = []
    for msg, resp in zip(messages, responses):
        if await should_write(msg, resp, {"importance_score": score_importance(msg, resp)}):
            important.append((msg, resp))
    
    # 批量嵌入 + 批量写
    contents = [m.content for m, r in important]
    embeddings = await embed_batch(contents)  # 批量调 embedding API，省 50% 成本
    await episodic_db.batch_insert(important, embeddings)
```

优点：成本低（批量 embedding 便宜）、吞吐高。缺点：知识延迟可用（用户说完到记忆生效有几分钟延迟）。

**策略 3：混合写入**

重要事件实时写，普通事件批量写。

```python
async def write_event_smart(event):
    importance = await score_importance(event)
    
    if importance > 0.8:
        # 实时写
        await episodic_db.insert(event)
    else:
        # 进队列，等批量写
        await write_queue.put(event)
```

**实战推荐**：**混合策略**。重要事件实时写（避免知识延迟），普通事件批量写（控制成本）。

## 重要度评分

怎么判断事件是否重要？4 个维度：

```python
async def score_importance(event) -> float:
    score = 0.0
    
    # 1. 用户明确表达（0-0.4）
    if contains_user_preference(event.content):
        score += 0.4
    if contains_user_correction(event.content):
        score += 0.4
    if contains_explicit_statement(event.content):  # "记住：..."
        score += 0.5
    
    # 2. 任务成败（0-0.3）
    if event.metadata.get("task_completed"):
        score += 0.3
    if event.metadata.get("task_failed"):
        score += 0.3
    
    # 3. 新颖性（0-0.2）
    similar_count = await count_similar_recent(event)
    if similar_count == 0:  # 全新内容
        score += 0.2
    elif similar_count < 3:  # 少量重复
        score += 0.1
    
    # 4. 实体提及（0-0.1）
    if mentions_new_entity(event.content):
        score += 0.1
    
    return min(score, 1.0)
```

实测：阈值 0.5 + 混合策略，单 agent 系统每天写 ~200 条 episodic events，平均 1 用户 50 条 / 天。

## 容量管理

长期记忆必须控制总量，否则存储爆炸。

**3 个管理策略**：

**a. 时间窗口 + 重要性**

普通事件保留 90 天，重要事件永久。

```python
async def cleanup_old_events():
    cutoff = datetime.now() - timedelta(days=90)
    await episodic_db.delete_where(
        timestamp < cutoff,
        importance < 0.7,  # 重要事件保留
    )
```

**b. 容量上限**

每用户最多保留 N 条事件，超出时按重要性删除。

```python
async def enforce_per_user_limit(user_id, max_events=10000):
    count = await episodic_db.count(user_id=user_id)
    if count > max_events:
        # 按 importance + recency 排序，删除尾部
        to_delete = count - max_events
        await episodic_db.delete_oldest_unimportant(user_id, to_delete)
```

**c. 自动归档**

超过 1 年的事件移到冷存储（S3 / Glacier），向量库只保留热数据。

```python
async def archive_old_events():
    cutoff = datetime.now() - timedelta(days=365)
    old_events = await episodic_db.fetch(timestamp__lt=cutoff)
    
    # 导出到 S3
    await s3.upload(f"events/{user_id}/{year}.json.gz", old_events)
    
    # 从热库删除
    await episodic_db.delete(timestamp__lt=cutoff)
```

## 写入的工程坑

**坑 1：重复写入**

用户说"我不喝咖啡"，agent 立刻写一条事件；用户 5 分钟后又说一遍"我不喝咖啡"，agent 又写一条。**同一条偏好写 10 次**，检索时返回一堆重复。

**修法**：写入前查重（基于 embedding 相似度）。

```python
async def write_with_dedup(event):
    similar = await episodic_db.search(
        vector=event.embedding,
        filter={"user_id": event.user_id, "type": event.type},
        top_k=3,
    )
    
    if similar and similar[0].similarity > 0.92:
        # 已有非常相似的事件，不重复写
        return
    
    await episodic_db.insert(event)
```

**坑 2：写入阻塞主流程**

每次用户消息都同步写 episodic memory，写入慢时整个 agent 卡住。

**修法**：异步写 + 队列。

```python
async def on_user_message(message):
    response = await agent.process(message)  # 主流程
    
    # 异步写，不阻塞响应
    asyncio.create_task(maybe_write_to_memory(message, response))
```

**坑 3：写入失败丢数据**

写入 episodic memory 时 DB 抖动失败，事件丢失。

**修法**：先写本地队列，再异步落 DB。

```python
async def write_with_retry(event):
    # 先写本地 WAL（write-ahead log）
    await wal.append(event)
    
    # 异步落 DB
    asyncio.create_task(flush_to_db(event))
```

## 实战数据

我跟踪过自己 agent 系统的写入策略优化前后：

| 指标 | 优化前（全写）| 优化后（混合 + 重要度） |
|------|--------------|---------------------|
| 单用户日均事件量 | 850 | 120 |
| 单用户总事件量（1 年）| 31 万 | 4.4 万 |
| 月存储成本 | $50/万用户 | $8/万用户 |
| 检索准确率 | 78% | 82% |
| 检索延迟 P95 | 150ms | 45ms |

**写入量减少 86%，检索延迟反而降低 70%**——少写垃圾数据反而让检索更准更快。

## 实战 checklist

```
Memory 写入 checklist：
[ ] 3 类事件（决策 / 偏好 / 失败）写 episodic
[ ] 闲聊 / 中间过程 / 敏感信息不写
[ ] 重要事件实时写，普通事件批量写
[ ] 写入前查重（embedding 相似度 > 0.92 不重写）
[ ] 异步写入（不阻塞主流程）
[ ] 时间窗口清理（普通事件保留 90 天）
[ ] 容量上限（单用户 ≤ 10000 条）
[ ] 自动归档（> 1 年事件归档冷存储）
[ ] WAL + 重试（防止写入失败丢数据）
```

9 项。0 项不通过不能上线。

下一章（最后一章）讲真实生产系统——把所有层组合起来看一个端到端的长期记忆系统怎么搭。