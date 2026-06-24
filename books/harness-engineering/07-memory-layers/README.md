# 07. Memory 分层：LLM 没记忆，Agent 需要

> LLM 每次对话都是孤立的——它不知道你昨天说过什么、上周做的项目、你的偏好。Agent 要"看起来记得"，必须靠 harness 主动管理 memory。这章拆 3 层 memory 模型 + procedural memory + vector DB 选型 + update / decay 策略。

## LLM 为什么没记忆

技术角度：每次 `messages.create()` 调用 LLM 看到的就是 messages 数组。LLM 服务端不知道这个 user 是谁、之前聊过啥。所有"对话连续性"都是 messages 数组模拟的——messages 一旦截断，LLM 就失忆。

业务角度：用户希望 agent 跨 session 记住关键信息。"我上周说我要做什么"、"我之前偏好用 Python"、"上次那个 bug 怎么修的"——这些是真实 agent 必须能回答的。

我自己的 agent 第一版完全没 memory——每次 session 都要用户重新介绍自己，重新说偏好，重新给背景。一个用户用 3 次就卸载了。**没 memory 的 agent 等于每次都是陌生人**。

## 认知科学的 3 层 memory 模型

我从认知科学借了 Atri/Shiffrin 1972 的多存储模型（虽然不严格照搬），把 agent memory 分 3 层：

**Working Memory（工作记忆）**：当前对话的 messages 数组。这就是 LLM "看到"的内容。容量有限（context window），生命周期短（对话结束就消失）。

**Episodic Memory（情节记忆）**：过去的具体事件。"用户 2026-01-15 让我修 X bug，我跑了 Y 命令解决了"——按时间存储，有具体上下文。

**Semantic Memory（语义记忆）**：抽象的事实和偏好。"用户偏好 Python"、"用户不喜欢 emoji"、"用户时区是 Asia/Shanghai"——去上下文的事实。

**Procedural Memory（程序记忆，我加的第 4 层）**：怎么做的记忆。"跑这种任务先 X 再 Y"、"调这个 API 先 auth 再 query"——动作序列，介于 semantic 和 skill 之间。

3 层（或 4 层）memory 各有不同 storage、retrieval、update 策略：

| 层 | Storage | Retrieval | Update |
|---|---|---|---|
| Working | messages 数组 | 全部进入 LLM context | 每轮追加 |
| Episodic | PostgreSQL / SQLite | by user_id + 时间范围 | append-only |
| Semantic | Vector DB + KV store | embedding similarity + exact match | merge + dedup |
| Procedural | Vector DB | embedding similarity | versioned + reviewed |

## Working Memory：context window 内的内容

前两章已经讲过 context management。这里补充一个细节：**working memory 不只是 messages，还包括 system prompt + tool schema**。

```python
def build_working_memory(user_id, current_messages):
    user_profile = semantic_memory.recall(user_id)  # 5-20 facts
    relevant_episodes = episodic_memory.search(user_id, current_messages[-1])  # top 3
    procedures = procedural_memory.search(current_messages[-1])  # top 2
    
    system_prompt = f"""你是个人助手。

用户档案（永远记住）：
{user_profile}

相关历史事件：
{chr(10).join(relevant_episodes)}

操作流程参考：
{chr(10).join(procedures)}
"""
    
    return [
        {"role": "system", "content": system_prompt},
        *current_messages,
    ]
```

Working memory 组装 = system（user profile + relevant episodes + procedures）+ 当前 messages。**system prompt 是 working memory 的"长期记忆通道"**——LLM 每个 step 都会重新看 system，所以 system 里的信息 100% 在 working memory 里。

## Episodic Memory：过去事件的 append-only log

```python
class EpisodicMemory:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY,
                user_id TEXT,
                timestamp TEXT,
                task TEXT,
                outcome TEXT,
                trajectory_id TEXT,
                metadata TEXT
            )
        """)
    
    def record(self, user_id, task, outcome, trajectory_id, metadata=None):
        self.conn.execute(
            "INSERT INTO episodes (user_id, timestamp, task, outcome, trajectory_id, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, datetime.now().isoformat(), task, outcome, trajectory_id, json.dumps(metadata or {}))
        )
        self.conn.commit()
    
    def search(self, user_id, query, limit=3, days=30):
        # 找最近 N 天的事件，按时间倒序
        rows = self.conn.execute("""
            SELECT task, outcome, timestamp FROM episodes
            WHERE user_id = ? AND timestamp > datetime('now', ?)
            ORDER BY timestamp DESC LIMIT ?
        """, (user_id, f"-{days} days", limit)).fetchall()
        return [f"[{ts}] {task} → {outcome}" for ts, task, outcome in rows]
```

Episodic memory 是 append-only——**只追加，不修改**。原因：事件已经发生，agent 不能"改写"历史。审计、回放、A/B test 都需要完整历史。

SQLite 够用（个人 agent）；多人多 session 切 PostgreSQL + JSONB metadata。

## Semantic Memory：抽象事实和偏好

```python
import chromadb

class SemanticMemory:
    def __init__(self, persist_dir):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection("user_facts")
    
    def remember(self, user_id, fact, category="general"):
        # 用 LLM 提炼 fact（从对话中提取）
        self.collection.add(
            documents=[fact],
            metadatas=[{"user_id": user_id, "category": category, "timestamp": datetime.now().isoformat()}],
            ids=[f"{user_id}_{category}_{uuid.uuid4().hex[:8]}"]
        )
    
    def recall(self, user_id, query_embedding=None, limit=10):
        results = self.collection.query(
            query_embeddings=[query_embedding] if query_embedding else None,
            where={"user_id": user_id},
            n_results=limit,
        )
        return results["documents"][0] if results["documents"] else []
```

Vector DB 选型——我用过 4 个：

**Chroma**（embedded，Python 原生）
- 优势：零部署、Python 一行启动、API 简单
- 劣势：单机、scale 不行（10 万+ doc 慢）
- 用在：hobby 项目、本地 agent、prototype

**Qdrant**（Rust 自带 server + Python client）
- 优势：性能好（10M+ doc 流畅）、filter 能力强、自带 server
- 劣势：要起 server（Docker / binary）、Python client 比 chroma 重
- 用在：production multi-user agent

**pgvector**（PostgreSQL 扩展）
- 优势：跟 PostgreSQL 数据合一（不用单独维护一个 vector store）、ACID
- 劣势：百万级 doc 后性能下降、需要调参
- 用在：已经有 PostgreSQL 的项目（多数 production）

**Pinecone**（托管云服务）
- 优势：全托管、scale 简单
- 劣势：vendor lock-in、要钱、数据不在自己这
- 我不用——个人项目没预算买这个

个人项目首选 Chroma（最简单）；production multi-user 选 Qdrant 或 pgvector。

## Procedural Memory：怎么做的记忆

这一层是大多数 agent 漏掉的——光记住"事实"不够，还要记住"工作流"。

我自己用 procedural memory 存两类内容：

**1. 重复出现的多步任务的工作流**

```python
# 用户经常让我："读 X 文件 → grep Y → 总结"
procedural_memory.remember(
    name="grep-summarize",
    steps=[
        "read_file(path=X)",
        "grep(pattern=Y, file=X)",
        "summarize(results)"
    ],
    when_to_use="when user asks to find and summarize something in a specific file"
)
```

下次用户问"找一下 main.py 里所有 TODO 总结一下"，LLM 收到 procedural memory 后直接照这个流程跑，不用重新想。

**2. 某个外部 API 的正确调用顺序**

```python
# GitHub API：必须先 auth 再 query，token 过期要 refresh
procedural_memory.remember(
    name="github-api-call",
    steps=[
        "check_token_validity()",
        "if expired: refresh_token()",
        "api_call(endpoint, headers={'Authorization': f'Bearer {token}'})",
        "handle_rate_limit(response.headers['X-RateLimit-Remaining'])"
    ],
    pitfalls=[
        "token expires every 1 hour",
        "rate limit: 5000 req/hour authenticated, 60 unauthenticated"
    ]
)
```

Procedural memory 比 semantic memory 复杂——它不只是 fact，是 step sequence + pitfalls。Storage 我用 Markdown 文件 + git 跟踪（"doc-as-code"），版本化 + 可 review。

```python
PROCEDURES_DIR = "./procedures/"

def load_procedure(name):
    path = os.path.join(PROCEDURES_DIR, f"{name}.md")
    return open(path).read()

def find_procedure(query, top_k=2):
    # 用 LLM 判断哪个 procedure 最相关
    procedures = list(Path(PROCEDURES_DIR).glob("*.md"))
    descriptions = [p.read_text()[:500] for p in procedures]
    # LLM 选最相关的
    best = llm_call(
        f"Which procedure (1-based) is most relevant for: {query}?",
        options=descriptions,
    )
    return load_procedure(procedures[int(best)-1].stem)
```

## Memory Update / Decay

**Semantic memory** 容易爆炸——用户每次说"我喜欢 X"都被记一条，3 个月后有 500 条。必须有 dedup + decay：

```python
def update_semantic_memory(user_id, new_fact):
    existing = semantic_memory.recall(user_id, embedding_of(new_fact), limit=5)
    
    # 检查是否重复
    for fact in existing:
        similarity = cosine_similarity(embedding_of(new_fact), embedding_of(fact))
        if similarity > 0.9:  # 几乎一样
            # 更新 timestamp，不重复加
            semantic_memory.touch(fact.id)
            return
    
    # 检查是否矛盾
    for fact in existing:
        if contradicts(new_fact, fact):
            # 用 LLM 判断哪个更新
            merged = llm_call(f"Merge these facts: {new_fact} vs {fact}")
            semantic_memory.replace(fact.id, merged)
            return
    
    # 新事实
    semantic_memory.remember(user_id, new_fact)

def decay_semantic_memory(user_id):
    """每 30 天跑一次, 删除 90 天没 touch 的 fact"""
    facts = semantic_memory.get_all(user_id)
    for fact in facts:
        last_touched = parse(fact.metadata["timestamp"])
        if (datetime.now() - last_touched).days > 90:
            semantic_memory.delete(fact.id)
```

**Episodic memory** 通常不 decay——历史事件是审计依据。但有 storage 成本时（> 100k episodes）按"重要性"压缩：

```python
def compress_old_episodes(user_id, days_threshold=180):
    """180 天前的 episodes 按 LLM 总结压缩"""
    old_episodes = episodic_memory.get(user_id, older_than_days=days_threshold)
    if len(old_episodes) < 50:
        return  # 不够多不压缩
    
    summary = llm_call(f"Summarize these {len(old_episodes)} events: {old_episodes}")
    episodic_memory.record(
        user_id=user_id,
        task=f"[{days_threshold}-day summary]",
        outcome=summary,
        trajectory_id="compression"
    )
    episodic_memory.delete_batch([e.id for e in old_episodes])
```

**Procedural memory** 几乎不 decay——但要 version control + 偶尔 review。我每季度看一次所有 procedure，删除过时的（比如某个 API 改版后 procedure 失效）。

## 一个完整 memory read 的例子

用户问："我上周让你查的那个 bug 找到根因了吗？"

Agent 思考路径：

```python
async def handle_query(user_id, user_query):
    # 1. Recall episodic memory：上周关于这个 bug 的事件
    relevant_episodes = episodic_memory.search(
        user_id, 
        query="bug 根因",
        days=14,
        limit=5,
    )
    # 输出: [
    #   "[2026-01-15] 修 X 文件的 Y 函数 bug → 找到 root cause: Z",
    #   "[2026-01-13] 用户报告 bug: X 文件 Y 函数报错"
    # ]
    
    # 2. Recall semantic memory：用户偏好 + 项目背景
    user_profile = semantic_memory.recall(user_id, limit=10)
    # 输出: ["用户偏好 Python", "项目用 FastAPI", ...]
    
    # 3. Recall procedural memory：有没有相关 procedure
    procedures = procedural_memory.find_procedure(user_query, top_k=2)
    
    # 4. 组装 working memory
    working = build_working_memory(
        user_profile=user_profile,
        relevant_episodes=relevant_episodes,
        procedures=procedures,
        current_messages=[{"role": "user", "content": user_query}],
    )
    
    # 5. 调 LLM
    response = llm.call(messages=working)
    return response
```

## Memory 跨用户的隔离

**永远按 user_id 隔离**——你的 agent 不应该让用户 A 看到用户 B 的 memory。每次 query 时强制 filter `user_id=A`：

```python
def recall_safe(user_id, query):
    # 永远带 user_id filter
    return memory.recall(
        where={"user_id": user_id},  # 必须的 filter
        query=query,
    )
```

我自己一次 bug 让 user_id 没传，结果 agent 把所有用户的偏好混着答——用户 A 看到"你住在北京"，用户 B 也看到"你住在北京"。修复后强制 schema + 测试覆盖。

## 这章踩过的关键坑

**Semantic memory 不 dedup**——"用户偏好 Python"、"用户喜欢用 Python"、"用户主语言是 Python"重复存了几十条。修：embedding similarity > 0.9 视为重复，只 touch 不新增。

**Episodic memory 当 semantic 用**——把"用户偏好"存到 episodic，结果按时间找出来的是 6 个月前的旧偏好。修：明确分两层，episodic 只存事件。

**Memory 无 decay**——3 个月后 memory 表爆 10 万行。修：semantic 90 天未 touch 自动删除；episodic 180 天后 LLM 压缩成 summary。

**Memory 更新没 review**——LLM 自动抽取 fact 经常抽错（"用户说他在用 macOS" 被记成"用户偏好 macOS"）。修：critical facts 写到 memory 前让用户确认（"我记住这条，你确认吗？"）。

**Procedural memory 跟代码脱节**——procedure 文件说调 GitHub API，但实际代码调的是 GitLab API。修：procedure 文件放在 git repo 里，每次 CI 跑"procedure 跟实际调用一致"检查。

下一章 [08. Failure Recovery](../08-failure-recovery/) 拆 harness 第五块基石——retry / rollback / checkpoint / human-in-loop 的失败恢复策略。
