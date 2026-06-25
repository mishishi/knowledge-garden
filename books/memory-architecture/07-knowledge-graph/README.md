# 07. 知识图谱：关系推理

向量数据库擅长**相似度检索**，但**关系推理**很弱——它知道"咖啡"和"茶"语义相似，不知道"用户 A 喜欢茶、不喜欢咖啡"这种关系。

知识图谱（Knowledge Graph）补这个缺口。它把世界建模成**实体 + 关系**，支持图遍历推理。

## 为什么 agent 需要知识图谱

**场景 1：关系推理**

向量检索找"类似咖啡的饮料"，可能找出茶、奶茶、可乐。知识图谱能告诉你："用户 A 不喜欢咖啡，但喜欢清淡的茶类饮料"——这是关系推理，不是相似度。

**场景 2：实体链接**

用户说"上次那个项目"，agent 需要知道"上次"指哪个项目、"那个项目"是哪个。知识图谱存储"用户 A → 上次做过的项目 → Project X"，agent 能直接查到。

**场景 3：知识一致性**

同一概念在不同事件里被以不同方式表达（"违约率" / "不良贷款率" / "default rate"），知识图谱能识别它们是同一概念，统一存储。

**场景 4：组织级知识**

"用户 A 是 Tech Lead，管 3 个工程师，负责风险分析模块"——这是组织关系，向量库存不下，知识图谱擅长。

## 主流知识图谱选型

### Neo4j

最成熟的图数据库。

```cypher
CREATE (u:User {id: "u_123", name: "Alice"})
CREATE (p:Project {id: "p_456", name: "风控系统"})
CREATE (c:Company {id: "c_acme", name: "ACME Inc"})
CREATE (u)-[:WORKS_AT {since: "2024-01"}]->(c)
CREATE (u)-[:OWNS]->(p)
CREATE (u)-[:DISLIKES]->(Coffee:Concept {name: "coffee"})
CREATE (u)-[:LIKES]->(Tea:Concept {name: "tea", flavor: "清淡"})
```

**优点**：成熟、Cypher 查询语言强大、生态丰富。

**缺点**：商业 license 限制（>1 亿节点要 enterprise license）。

### Memgraph

开源版 Neo4j 替代品。Cypher 兼容。

**优点**：开源、性能比 Neo4j 略好、支持流式图算法。

**缺点**：生态比 Neo4j 小。

### Nebula Graph

国产开源图数据库，字节 / 美团 / 小红书都在用。

**优点**：超大规模（千亿节点）、水平扩展。

**缺点**：运维复杂、Cypher 不完全兼容。

### 轻量方案：PostgreSQL + JSONB

如果图规模 < 100 万节点，PostgreSQL 也能模拟知识图谱：

```sql
CREATE TABLE kg_nodes (
    node_id TEXT PRIMARY KEY,
    type TEXT,
    properties JSONB
);

CREATE TABLE kg_edges (
    source_id TEXT,
    target_id TEXT,
    relation TEXT,
    properties JSONB,
    PRIMARY KEY (source_id, target_id, relation)
);

CREATE INDEX ON kg_edges (source_id);
CREATE INDEX ON kg_edges (target_id);
```

**适合**：小规模、懒得运维图数据库的项目。

## 知识图谱在 agent 里的 5 类应用

**应用 1：用户画像**

```
(User:Alice)
  -[LIKES]-> (Beverage:Tea)
  -[DISLIKES]-> (Beverage:Coffee)
  -[WORKS_AT]-> (Company:ACME)
  -[OWNS]-> (Project:RiskSystem)
  -[PREFERS]-> (Format:Table)
```

agent 检索时能直接拿到 Alice 的所有偏好。

**应用 2：项目知识**

```
(Project:RiskSystem)
  -[USES]-> (Tech:PostgreSQL)
  -[USES]-> (Tech:NestJS)
  -[HAS_CONVENTION]-> (Naming:CamelCase)
  -[HAS_RULE]-> (Rule:NoPII)
```

新 agent 加入项目时，直接读这张图就能知道项目所有约定。

**应用 3：实体链接**

用户说"上次那个项目"，agent 查图：

```cypher
MATCH (u:User {id: "u_123"})-[:OWNS]->(p:Project)
RETURN p ORDER BY p.last_accessed DESC LIMIT 1
```

**应用 4：能力统计**

```
(Agent:RiskAnalyst)
  -[HAS_CAPABILITY]-> (Tool:PostgresQuery)
  -[HAS_STAT]-> (ErrorRate:0.12)
  -[HAS_STAT]-> (AvgLatency:2300ms)
```

agent 自我评估"我擅长什么 / 我不擅长什么"。

**应用 5：组织关系**

```
(User:Alice)-[:REPORTS_TO]->(User:Bob)
(User:Bob)-[:OWNS]->(Team:RiskTeam)
(User:Charlie)-[:MEMBER_OF]->(Team:RiskTeam)
```

agent 处理组织级任务时知道"该 escalate 给谁"。

## 图谱构建

从 episodic events 自动构建图谱：

```python
async def extract_graph_from_events(events: list[EpisodicEvent]) -> tuple[list[Node], list[Edge]]:
    prompt = f"""
    从以下事件中提取实体和关系。
    
    实体类型：
    - User（用户）
    - Project（项目）
    - Tool（工具）
    - Concept（概念 / 偏好）
    - Agent（agent 类型）
    
    关系类型：
    - LIKES, DISLIKES（偏好）
    - WORKS_AT, OWNS, REPORTS_TO（组织）
    - USES（项目用工具）
    - HAS_CONVENTION, HAS_RULE（项目规则）
    - HAS_CAPABILITY, HAS_STAT（agent 能力）
    
    输出 JSON：{ "nodes": [...], "edges": [...] }
    """
    
    response = await llm.invoke(
        model="claude-opus-4.7",
        system=prompt,
        user=format_events(events),
        response_format={"type": "json_object"},
    )
    
    return parse_graph(response)
```

写入：

```python
async def write_graph(nodes, edges):
    async with driver.session() as session:
        for node in nodes:
            await session.run(
                "MERGE (n:%s {id: $id}) SET n += $props",
                node.type, id=node.id, props=node.properties,
            )
        for edge in edges:
            await session.run(
                "MATCH (a {id: $a}), (b {id: $b}) "
                "MERGE (a)-[r:%s]->(b) SET r += $props",
                edge.relation, a=edge.source_id, b=edge.target_id,
                props=edge.properties,
            )
```

## 图查询实战

**查询 1：用户所有偏好**

```cypher
MATCH (u:User {id: $user_id})-[r:LIKES|DISLIKES]->(c:Concept)
RETURN c.name AS concept, type(r) AS preference, r.confidence AS confidence
```

**查询 2：项目所有技术栈**

```cypher
MATCH (p:Project {id: $project_id})-[:USES]->(t)
RETURN labels(t)[0] AS type, t.name AS name
```

**查询 3：推荐（基于图推理）**

```cypher
// 找和用户喜欢相同概念的其他用户，他们也喜欢什么
MATCH (u:User {id: $user_id})-[:LIKES]->(c:Concept)<-[:LIKES]-(other:User)
MATCH (other)-[:LIKES]->(rec:Concept)
WHERE NOT (u)-[:LIKES|DISLIKES]->(rec)
RETURN rec.name AS recommendation, count(*) AS score
ORDER BY score DESC LIMIT 10
```

**查询 4：冲突检测**

```cypher
// 用户既 LIKES 又 DISLIKES 同一概念 → 冲突
MATCH (u:User {id: $user_id})-[r1:LIKES]->(c:Concept)
MATCH (u)-[r2:DISLIKES]->(c)
RETURN c.name, r1.updated_at AS likes_at, r2.updated_at AS dislikes_at
```

## 性能数据

**Neo4j 100 万节点 + 500 万边**：

- 单跳查询：< 5ms
- 3 跳查询：< 50ms
- 5 跳查询：< 500ms

**Memgraph 同规模**：性能略好 10-20%。

**PostgreSQL JSONB 模拟图（100 万节点）**：

- 单跳查询：< 20ms
- 多跳查询：500ms+（要多次 join）

如果图规模 > 100 万节点，**强烈建议用真正的图数据库**，不要用 PG 模拟。

## 向量 + 图谱：混合架构

向量库做相似度检索，图谱做关系推理，两者配合：

```
[用户问题]
   ↓
[向量库检索] → 找到相似的 episodic events
   ↓
[图谱推理] → 基于这些事件关联的用户 / 项目 / 偏好
   ↓
[综合答案]
```

**真实案例**：

用户问"上次那个项目用什么数据库"

1. 向量检索找到 5 个类似问题
2. 图谱推理：用户 A 上次做的项目 = Project X（基于 access time 排序）
3. 图谱推理：Project X 使用的技术 = PostgreSQL
4. 综合答案："PostgreSQL，配置见 xxx"

## 实战代码骨架

```python
class GraphMemory:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    async def extract_and_write(self, events):
        nodes, edges = await extract_graph_from_events(events)
        async with self.driver.session() as session:
            for node in nodes:
                await session.execute_write(write_node, node)
            for edge in edges:
                await session.execute_write(write_edge, edge)
    
    async def recall_user_preferences(self, user_id):
        async with self.driver.session() as session:
            result = await session.execute_read(
                query_user_preferences,
                user_id=user_id,
            )
            return [record.data() for record in result]
    
    async def recommend(self, user_id, top_k=10):
        async with self.driver.session() as session:
            result = await session.execute_read(
                query_recommend,
                user_id=user_id, top_k=top_k,
            )
            return [record.data() for record in result]
```

下一章讲混合检索——向量 + 图谱 + 关键词三件套怎么组合。