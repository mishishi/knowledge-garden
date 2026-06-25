# 10. 真实场景 4 案例

> 前面 9 章拆了 4 元素 / Few-shot / CoT / Role / Structured / Tool / Cache / Injection / Eval。这章把 4 个真实场景的完整 prompt 拆开——每个都能直接 copy 改改用。

## 案例 1：客服 RAG 检索增强回答

电商客服需要基于产品手册 + 历史工单回答用户问题。输入：产品手册 ~5000 token（PDF 提取）、历史工单 ~3000 token（top 5 相似）、用户问题 ~100 token。

**System prompt：**

```python
SYSTEM = """
你是 Acme 电商平台资深客服，5 年售后经验。

【角色定位】
- 友好但不卑微（用「您」不用「你」）
- 先共情再解决（"理解您的心情..."）
- 基于【产品手册】和【历史工单】回答，不能编造信息

【业务知识】
- 平台：Acme 电商
- 主要品类：电子产品、家居用品
- 退换货政策：7 天无理由 / 15 天质量问题
- 物流：顺丰 / 中通，下单后 1-3 天发货

【输出格式】
- 称呼：「您好」
- 结构：问题分析 + 解决方案 + 补充说明
- 长度：150-300 字
- 不用 markdown 标题（连续段落）
- 结束：「如有其他问题随时联系」

【边界】
- 不能承诺具体退款金额
- 不能给医疗 / 法律建议
- 不在产品手册 / 历史工单范围的问题拒绝
- 涉及账号安全立刻转人工

【回答流程】
1. 先看【历史工单】，找相似 case 怎么处理的
2. 再看【产品手册】，确认业务规则
3. 结合用户问题，给出具体方案
4. 如超出范围：礼貌拒绝

【输出】
"""
```

**User prompt**——先检索历史工单 + 手册，再拼 prompt：

```python
def build_user_prompt(query: str) -> str:
    similar_tickets = vector_search(query, top_k=5, source="tickets")
    manual_chunks = vector_search(query, top_k=3, source="manual")
    return f"""
【用户问题】
{query}

【历史工单】（top 5 相似 case）
{format_tickets(similar_tickets)}

【产品手册】相关章节
{format_manual(manual_chunks)}
"""
```

**Few-shot 例子**——3 个 case 覆盖正常问题、产品使用、范围外问题：

```python
FEW_SHOT = """
例子 1：
用户：'我想退订单 ABC123，产品有质量问题。'
客服：'您好，理解您遇到质量问题带来的不便。我帮您查一下订单 ABC123 的状态，订单是 6 月 20 日下的单，还在 7 天无理由期内。我帮您发起退款申请，工单号会在 24 小时内通过短信发送给您。退款会在 3-5 个工作日原路返回。'

例子 2：
用户：'你们这个产品怎么用？'
客服：'您好，根据产品手册第 12 页，这个产品有以下使用步骤：1. 充电 2 小时；2. 长按电源键 3 秒开机；3. 手机扫描机身二维码下载 App；4. App 里添加设备即可使用。'

例子 3：
用户：'你们公司股票会涨吗？'
客服：'抱歉，这个问题不在我能回答的范围内，建议您咨询专业投资顾问。'
"""
```

**完整调用**——user_prompt + few_shot 拼一起丢给 LLM：

```python
def customer_service_query(user_query: str) -> str:
    user_prompt = build_user_prompt(user_query) + "\n\n" + FEW_SHOT
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content
```

**评估指标**：准确率 85%+（基于历史工单对比）、格式合规 95%+（称呼 / 长度 / 连续段落）、用户满意度 80%+。

## 案例 2：Text-to-SQL 自然语言生成查询

业务人员用自然语言问数据问题，生成 SQL 查数据库。

**System prompt：**

```python
SYSTEM = """
你是数据分析师，专精 SQL。

【任务】
把业务问题转成 SQL 查询。

【schema】
{schema}    # 动态注入数据库 schema

【输出格式】
```sql
<SQL 查询>
```

【规则】
1. 只能查 SELECT，不能 INSERT/UPDATE/DELETE
2. 用 schema 里实际存在的表和字段
3. JOIN 明确写明 ON 条件
4. 复杂查询加 LIMIT 防止全表扫描
5. 时间字段明确格式（DATE_TRUNC / INTERVAL）

【例子】
问题：'上月销售额前 10 的产品'
SQL：
```sql
SELECT p.name, SUM(o.amount) as total
FROM products p
JOIN orders o ON p.id = o.product_id
WHERE o.created_at >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
  AND o.created_at < DATE_TRUNC('month', CURRENT_DATE)
GROUP BY p.id
ORDER BY total DESC
LIMIT 10
```

问题：'DAU'
SQL：
```sql
SELECT DATE(created_at) as day, COUNT(DISTINCT user_id) as dau
FROM events
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY day
ORDER BY day
```

【任务】
"""
```

**User prompt 简洁**——只放问题：

```python
user_prompt = f"问题：{business_question}"
```

**Eval set**——100+ 真实业务问题 + 人工写的 expected SQL：

```python
EVAL_SET = [
    {
        "question": "上个月销售额前 10 的产品",
        "expected_sql": "...",
        "expected_tables": ["products", "orders"],
    },
    {
        "question": "DAU",
        "expected_sql": "...",
    },
    # ... 100+ cases
]
```

**3 个关键技巧**：

**schema 必须动态注入**——schema 写死在 prompt 改了 prompt 不知道。每次调 LLM 前从 DB 读最新 schema：

```python
def get_schema() -> str:
    return """
Table: users
  id BIGINT PRIMARY KEY
  email VARCHAR UNIQUE
  created_at TIMESTAMP
  ...

Table: orders
  id BIGINT PRIMARY KEY
  user_id BIGINT REFERENCES users(id)
  amount DECIMAL
  status VARCHAR  -- 'pending' | 'paid' | 'shipped' | 'completed'
  created_at TIMESTAMP
  ...
"""

SYSTEM = SYSTEM.replace("{schema}", get_schema())
```

**严格禁止写操作**——system prompt 写"只能 SELECT"还不够，必须二次校验。LLM 可能输出 INSERT/UPDATE/DDL，代码层必须拦截：

```python
DANGEROUS = ["INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT"]

def validate_sql(sql: str) -> bool:
    upper = sql.upper()
    return not any(kw in upper for kw in DANGEROUS)

# 用
sql = extract_sql(llm_response)
if not validate_sql(sql):
    return "[生成的 SQL 含危险操作，已拒绝]"
```

**限定数据库用户**——物理隔离。创建只读账号，权限只 GRANT SELECT。即使 SQL 注入也只能 SELECT 不能改数据：

```sql
GRANT SELECT ON ALL TABLES IN SCHEMA public TO text2sql_user;
```

**评估指标**：语法正确 95%+、字段正确 85%+、JOIN 正确 80%+、性能合理（无全表扫）70%+。

## 案例 3：长文档摘要

用户上传 10000 字报告，AI 输出 500 字摘要 + 关键观点。

**System prompt：**

```python
SYSTEM = """
你是专业摘要写手，10 年编辑经验。

【任务】
基于【文档】生成 500 字摘要 + 关键观点。

【输出格式】
## 摘要
<500 字以内的总结，覆盖文档主要论点>

## 关键观点
- 观点 1：<一句话>
- 观点 2：<一句话>
- 观点 3：<一句话>
（3-5 条）

【规则】
1. 严格基于【文档】内容，不添加文档外信息
2. 不引用未在文档出现的数字、日期、人名
3. 不省略关键数据 / 结论
4. 摘要语气：客观中立，不用「我觉得」「显然」
5. 关键观点要 actionable（能据此做决策）

【任务】
"""
```

**User prompt**——支持用户指定重点：

```python
def build_user_prompt(document: str, focus: str = "") -> str:
    prompt = f"【文档】\n{document}"
    if focus:
        prompt += f"\n\n【重点】\n用户特别关注：{focus}"
    return prompt
```

**长文档处理**——10K token 文档 + 1K prompt + 500 输出 ≈ 11.5K token，单次 $0.03-$0.1。

3 个降本方案：

**方案 1：分层摘要**——文档分块、每块单独摘要、合并再总结：

```python
def hierarchical_summarize(document: str, chunk_size: int = 3000) -> str:
    chunks = split_into_chunks(document, chunk_size)

    # 1. 每段单独摘要
    chunk_summaries = []
    for chunk in chunks:
        summary = llm.call(SYSTEM_SUMMARIZE_ONE + "\n\n" + chunk)
        chunk_summaries.append(summary)

    # 2. 合并 + 总结
    combined = "\n\n".join(f"[段落 {i+1}]\n{s}" for i, s in enumerate(chunk_summaries))
    final = llm.call(SYSTEM + "\n\n【分段摘要】\n" + combined)
    return final
```

成本：$0.03 → $0.005（**6x 节省**，token 总数从 12K 降到 ~5K）。

**方案 2：Map-Reduce**——跟方案 1 类似但合并用 map-reduce，适合超长文档（>50K token）。

**方案 3：Cache**——文档部分写 cache，后续只算 query 部分。Anthropic Prompt Cache 直接支持。

**评估指标**——用 ROUGE 分数（摘要 vs 参考摘要）：

```python
from rouge_score import rouge_scorer

scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
scores = scorer.score(reference_summary, llm_summary)
print(f"ROUGE-1: {scores['rouge1'].fmeasure:.3f}")
```

实测 ROUGE-1 60-80% 算 good。

## 案例 4：代码 review Agent

自动 review PR，给出具体修改建议。

**System prompt：**

```python
SYSTEM = """
你是资深代码审查员，10 年大厂经验，专精分布式系统。

【任务】
审查 PR 的 diff，给具体修改建议。

【审查维度】
1. 正确性：bug / 边界 case / 错误处理
2. 性能：O(n²) 以上的循环、内存泄漏、阻塞 IO
3. 安全：SQL 注入、XSS、密钥泄露、权限绕过
4. 可读性：命名、注释、复杂度
5. 测试：覆盖率、边界 case

【输出格式】
按严重程度排序，每条问题：
- 严重程度：critical / high / medium / low / nit
- 维度：correctness / performance / security / readability / test
- 文件：path/to/file.py
- 行号：N（如果能定位）
- 描述：1-2 句话
- 修复：具体代码示例

【规则】
1. 不确定就标「需要人工判断」
2. critical 必须阻断合并
3. 风格问题只标 nit，不展开
4. 涉及改 API / 架构必须标 critical

【任务】
"""
```

**User prompt**——直接放 PR diff：

```python
def build_user_prompt(diff: str) -> str:
    return f"""
【PR Diff】
```diff
{diff}
```

【审查结果】
"""
```

**3 个关键设计**：

**严重程度 + 维度组合 = 精准定位**——「high / performance / db.py:42」比「这个代码不好」强 100 倍。

**必须给修复方案**——只描述问题没用，给具体代码：

```python
# 错：只描述问题
"这段代码性能不好"

# 对：给具体代码
"修复：改为 batch 查询
```python
results = db.execute('SELECT * FROM users WHERE id = ANY(%s)', ([1, 2, 3],))
```"
```

**边界判断**——在 system prompt 里明确"不确定就标「需要人工判断」"、"涉及改 API / 架构必须标 critical"。

**评估指标**：critical 问题召回率 ≥ 80%（不能漏 critical）、误报率 ≤ 30%（避免消磨 review 信任）、人类 reviewer 接受率 ≥ 50%。

## 4 个案例对比

| 维度 | 客服 RAG | Text-to-SQL | 长文档摘要 | 代码 review |
|---|---|---|---|---|
| 输入 token | 8000 | 500 | 10000 | 5000 |
| 输出 token | 300 | 200 | 700 | 1000 |
| 主要成本 | 输入 RAG context | Schema | 长文档 | Diff |
| 主要技巧 | 检索 + few-shot | 严格 schema + 危险 SQL 拦截 | 分层摘要 + cache | 严重程度 + 修复示例 |
| 准确率目标 | 85% | 80% | ROUGE-1 70% | 召回 80% / 误报 ≤ 30% |
| 成本/次 | $0.01 | $0.003 | $0.02 | $0.02 |
| 失败模式 | 编造产品信息 | 危险 SQL | 漏关键信息 | 误报 / 漏 critical |

**4 个案例的共同点**：都有 system + few-shot + 严格输出格式、都有 eval set + 持续监控、都有 prompt injection 防御、都有 cache / 成本控制。

## 实战 5 步：把你的任务 prompt 化

**第 1 步：写「任务描述 + 输入 + 输出」1 句话**——`任务：把 [输入] 转成 [输出]`。

**第 2 步：写 5-10 个 eval case**——3 个典型 case + 2 个边界 case + 1 个错误输入 case。

**第 3 步：写 v1 prompt（基础）**——`你是 X。任务：Y。输出格式：Z。` 跑 eval，看通过率。

**第 4 步：迭代到 v2-v3**——加 persona、加 few-shot、加约束。每改一个看 eval。

**第 5 步：production 化**——加 eval pipeline（每次部署前跑）、加红队测试（ch08 的 attack library）、加 cache（ch07）、加 prompt version 管理（ch09）。

— 完 —
