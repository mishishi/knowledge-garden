# 06. 结构化输出与 Guardrail

> LLM 输出字符串不靠谱——想拿到结构化 JSON、想保证输出符合业务规则、想在违规时拦截——靠 Pydantic 模型 + Guardrail。

## 为什么需要结构化输出

Task 默认 `expected_output` 是「一段文字」。LLM 给你返回什么格式完全看心情——可能 markdown，可能 JSON，可能纯文本带 emoji。下游要解析就头秃。

3 个理由让你必须上结构化输出：

1. **下游要 parse**：前端要 JSON 才能渲染，DB 要 schema 才能插入
2. **业务校验**：URL 必须能 ping 通、金额必须 > 0、JSON 字段必须非空
3. **可调试**：输出是固定 schema，错了一看就知道哪个字段不对

v1.14 有两种结构化输出方式：`output_pydantic` 和 `output_json`。

## output_pydantic：完整 Pydantic 模型

### 最简单的例子

```python
from pydantic import BaseModel
from crewai import Agent, Task, Crew


class BlogPost(BaseModel):
    title: str
    content: str
    tags: list[str]


writer = Agent(
    role="技术写作员",
    goal="写结构化博客",
    backstory="...",
)

task = Task(
    description="写一篇关于 RAG 的博客",
    expected_output="包含 title / content / tags 的结构化博客",
    agent=writer,
    output_pydantic=BlogPost,   # ← 锁输出 schema
)
```

跑 `crew.kickoff()` 后：

```python
result = crew.kickoff()
result.pydantic   # BlogPost 实例
print(result.pydantic.title)     # "RAG 入门"
print(result.pydantic.tags)      # ["RAG", "LLM", "向量检索"]
```

### 嵌套模型

```python
from pydantic import BaseModel
from typing import List, Optional


class Fact(BaseModel):
    name: str
    description: str
    source_url: Optional[str] = None


class ResearchReport(BaseModel):
    topic: str
    facts: List[Fact]
    confidence: float   # 0-1，LLM 自评


task = Task(
    description="研究主题",
    agent=researcher,
    output_pydantic=ResearchReport,
)
```

### 带约束的字段

Pydantic v2 的 `Field` 让你加约束：

```python
from pydantic import BaseModel, Field


class ResearchReport(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200)
    confidence: float = Field(..., ge=0.0, le=1.0)
    tags: List[str] = Field(..., min_length=3, max_length=10)
```

跑出来 LLM 填错范围，Pydantic 自动报错，框架重试。

### Enum 字段

```python
from enum import Enum
from pydantic import BaseModel


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class Review(BaseModel):
    text: str
    sentiment: Sentiment
```

LLM 必须填 enum 里的值之一，否则 Pydantic 校验失败。

## output_json：松一点的 JSON

只要求「输出是合法 JSON」，不锁 schema：

```python
task = Task(
    description="...",
    agent=analyst,
    output_json=True,   # ← 只要 JSON，不锁字段
)
```

跑完：

```python
result = crew.kickoff()
result.json_dict   # dict 实例（框架自动 parse）
```

**什么时候用 output_json 而不是 output_pydantic**：

- 你想要 LLM 自由发挥字段
- 你下游要的是「JSON 字符串」而不是结构化对象
- 你不想写 Pydantic 模型（懒）

**什么时候必须用 output_pydantic**：

- 字段名要稳定（前端代码写死 `result.title`）
- 要做业务校验（Field 约束）
- 要 type safety（IDE 知道字段类型）

## Guardrail：业务校验拦截

Pydantic 只能校验「字段类型对不对」，不能校验「URL 能不能 ping 通」「金额是不是真的合理」——这些**业务规则**靠 Guardrail。

### 写法

```python
from crewai import Task


def validate_blog_post(result) -> tuple[bool, str]:
    """返回 (是否通过, 失败原因)"""
    blog = result.pydantic
    if len(blog.content) < 100:
        return (False, "内容太短，至少 100 字")
    if "广告" in blog.content or "联系方式" in blog.content:
        return (False, "内容包含广告或联系方式")
    return (True, blog.content)


task = Task(
    description="写博客",
    agent=writer,
    output_pydantic=BlogPost,
    guardrail=validate_blog_post,   # ← 业务校验
    guardrail_max_retries=3,         # ← 失败最多重试 3 次
)
```

**执行流程**：

```
Agent 输出 BlogPost
    ↓
Pydantic 校验字段类型  ← 自动
    ↓
guardrail() 业务校验   ← 你写的
    ├─ 通过 → 任务完成
    └─ 失败 → 把失败原因反馈给 Agent，让它重试
        └─ 重试 guardrail_max_retries 次
            └─ 还是失败 → 任务失败
```

### 实战：URL 必填 + 可达

```python
import requests
from pydantic import BaseModel


class LinkCheck(BaseModel):
    title: str
    url: str


def validate_link(result) -> tuple[bool, str]:
    link = result.pydantic
    try:
        resp = requests.head(link.url, timeout=5, allow_redirects=True)
        if resp.status_code >= 400:
            return (False, f"URL {link.url} 返回 {resp.status_code}")
    except requests.RequestException as e:
        return (False, f"URL {link.url} 请求失败: {e}")
    return (True, link.url)
```

**坑**：`requests.head()` 不一定所有 server 都支持，**用 `requests.get()` 配合 `stream=True` + `timeout=5` 更稳**：

```python
def validate_link(result) -> tuple[bool, str]:
    link = result.pydantic
    try:
        resp = requests.get(link.url, timeout=5, stream=True, allow_redirects=True)
        resp.close()   # 立刻关连接
        if resp.status_code >= 400:
            return (False, f"URL {link.url} 返回 {resp.status_code}")
    except Exception as e:
        return (False, f"URL {link.url} 不可达: {e}")
    return (True, link.url)
```

### Guardrail 限制

**限制 1：Guardrail 失败 → 重试 → 烧 token**

3 次重试 = 3 倍 token。**业务校验**应该尽量放在「字段层」（Pydantic Field 约束）而不是 Guardrail。

**限制 2：Guardrail 返回的字符串会喂回 Agent**

错误信息要写得**让 LLM 能改**：

```python
# 差：返回模糊信息
return (False, "不对")

# 好：返回具体可改的反馈
return (False, "URL https://broken.com 不可达（502 Bad Gateway）。请用 https://working.com 替代。")
```

**限制 3：Guardrail 不能跑异步**

如果要做 async 校验（比如批量调 API），用 `asyncio.run()` 同步跑：

```python
import asyncio

def validate_many_links(result) -> tuple[bool, str]:
    async def check_all(links):
        return [await check_one(l) for l in links]

    # 同步 wrapper
    results = asyncio.run(check_all(result.pydantic.links))
    failed = [l for l, ok in zip(result.pydantic.links, results) if not ok]
    if failed:
        return (False, f"这些 URL 不可达: {failed}")
    return (True, "all good")
```

## 真实案例：研究 Agent + 结构化输出

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from crewai import Agent, Task, Crew


class FactSource(BaseModel):
    url: str
    title: str
    snippet: str


class Fact(BaseModel):
    claim: str
    sources: List[FactSource] = Field(..., min_length=1)  # 至少 1 个来源
    confidence: float = Field(..., ge=0.0, le=1.0)


class ResearchReport(BaseModel):
    topic: str
    summary: str = Field(..., min_length=50)  # 至少 50 字总结
    facts: List[Fact] = Field(..., min_length=3, max_length=10)
    conclusion: str


researcher = Agent(
    role="技术研究员",
    goal="调研 {topic}，输出可验证的事实清单",
    backstory="你做调研必须有来源。每个事实至少 1 个 URL 来源，不确定的标低 confidence。",
    tools=[SerperDevTool()],
    verbose=True,
)


def validate_research(result) -> tuple[bool, str]:
    report = result.pydantic
    if len(report.facts) < 3:
        return (False, f"事实数量不足（{len(report.facts)} < 3），请补调研")

    # 验每个 fact 都有 source
    for i, fact in enumerate(report.facts):
        if not fact.sources:
            return (False, f"第 {i+1} 个事实 '{fact.claim}' 没有来源 URL，请补")

    return (True, report.summary)


task = Task(
    description="调研主题 {topic}",
    expected_output="包含 summary / facts / conclusion 的结构化报告",
    agent=researcher,
    output_pydantic=ResearchReport,
    guardrail=validate_research,
    guardrail_max_retries=3,
)
```

跑出来你会看到：

1. Agent 先尝试输出（可能 facts 只有 2 个）
2. guardrail 失败：「事实数量不足」
3. Agent 看到反馈，重新调研补一个 fact
4. guardrail 通过 ✓

**没有 guardrail 的话**——Agent 输出 2 个 facts 跑完了，下游拿到残缺数据。**guardrail 强制 Agent 自己补完。**

## 4 大实战模式

### 模式 1：Strict（最严）

```python
output_pydantic=StrictModel   # 所有字段必填
guardrail=strict_check        # 业务校验
guardrail_max_retries=3       # 失败重试 3 次
```

适合：金融、医疗——输出错一个字都不能用。

### 模式 2：Loose（最松）

```python
output_json=True   # 随便，只要 JSON
```

适合：探索性分析——你也不知道要什么字段。

### 模式 3：Hybrid（最常用）

```python
output_pydantic=Model   # 锁核心字段
# 不配 guardrail
```

适合：80% 场景。

### 模式 4：Cascade（级联校验）

```python
output_pydantic=Model
guardrail=quick_check   # 第一道：字段层
# 然后在下游代码里再校验（业务层）
```

适合：校验逻辑复杂，Agent 那边只做粗校验。

## 跑不起来的常见坑

**坑 1：Pydantic v1 vs v2 不兼容**

```python
# Pydantic v1 写法（已废弃）
class BlogPost(BaseModel):
    class Config:
        schema_extra = {"example": {...}}

# Pydantic v2 写法
from pydantic import ConfigDict
class BlogPost(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {...}})
```

v1.14 用 Pydantic v2。老教程用 v1 写法会报错。

**坑 2：output_pydantic 和 output_json 不能同时用**

```python
# 错
task = Task(
    output_pydantic=Model,
    output_json=True,   # ← 冲突
)
```

只能二选一。

**坑 3：guardrail 重试烧光 token**

```python
guardrail_max_retries=10   # ← 10 次重试 = 10x token
```

默认值是 **0**（不重试）。手动设 3 足够。

**坑 4：Agent 看到 guardrail 失败但不知道怎么改**

```python
# 差
return (False, "无效")

# 好
return (False, "summary 字段少于 50 字（当前 30 字），请把摘要写更详细，至少 50 字")
```

**坑 5：循环 import 跑不起来**

Pydantic Model 跟 Crew 在同一个文件，但 Model 引用了 Tool 类型 → 循环 import。

**修复**：把 Model 放单独的 `models.py` 文件。

## 这章跑完之后你该会什么

- 用 `output_pydantic` 锁字段类型 + 约束
- 用 `output_json` 拿松散的 JSON
- 写 Guardrail 做业务校验
- 知道 4 大实战模式
- 避免 5 个常见坑

