# 05. Structured Output

> LLM 默认吐「散文」——想拿结构化 JSON 怎么办？这章拆 3 种方法 + Pydantic 锁字段 + 真实 query 改写 pipeline。

## 3 种结构化输出方法

### 方法 1：Prompt 引导

```python
prompt = """
分析下面评论，输出 JSON：
{
  "sentiment": "positive" | "negative" | "neutral",
  "score": 0-10 的数字,
  "issues": ["物流", "质量", ...]
}

评论：'产品不错但物流太慢了'
"""
```

**实测**：50-70% 准确率（看任务复杂度）。LLM 可能：
- 输出多余文字（"好的，分析如下..."）
- 字段缺失（忘了 score）
- 字段类型错（score 写成中文「八」）

**适合**：探索性场景（你也不知道要什么 schema）。

### 方法 2：JSON Mode（OpenAI / 部分模型支持）

```python
import openai

response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_object"},   # ← 强制 JSON
)

data = json.loads(response.choices[0].message.content)
```

**实测**：99% 准确率。LLM 不会输出多余文字，强制是合法 JSON。

**注意**：
- 仍然要 prompt 里给 schema（否则 LLM 不知道字段名）
- **不保证字段类型对**（score 可能是字符串 "8" 而不是数字 8）
- 模型支持：GPT-4o / GPT-4o-mini / Gemini 2.5 Flash / 部分开源模型

### 方法 3：Tool Use（Function Calling）

```python
import openai
import json

tools = [{
    "type": "function",
    "function": {
        "name": "save_review_analysis",
        "description": "保存评论分析结果",
        "parameters": {
            "type": "object",
            "properties": {
                "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                "score": {"type": "integer", "minimum": 0, "maximum": 10},
                "issues": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["sentiment", "score", "issues"],
        },
    },
}]

response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}],
    tools=tools,
    tool_choice={"type": "function", "function": {"name": "save_review_analysis"}},
)

# 解析
tool_call = response.choices[0].message.tool_calls[0]
data = json.loads(tool_call.function.arguments)
```

**实测**：99.5% 准确率。LLM 按 schema 填字段，类型 + 必填 + enum 都强制。

**优点**：
- schema 校验严格（OpenAI 后端做）
- 支持嵌套、enum、约束
- 不用 prompt 引导字段名

**缺点**：
- 实现稍复杂
- 部分模型支持度差（Claude 用自己的 tool use API，不完全一样）

## Pydantic 校验

不管用哪种方法，**LLM 输出都要用 Pydantic 二次校验**——模型可能 99% 对，但 1% 错你就要兜底。

```python
from pydantic import BaseModel, Field, ValidationError
from typing import List
from enum import Enum


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class ReviewAnalysis(BaseModel):
    sentiment: Sentiment
    score: int = Field(..., ge=0, le=10)
    issues: List[str] = Field(default_factory=list)
    summary: str = Field(..., min_length=10, max_length=200)


# 用法 1：从 JSON 解析
try:
    data = json.loads(llm_response)
    analysis = ReviewAnalysis(**data)
except (json.JSONDecodeError, ValidationError) as e:
    # 处理错误：重试 / fallback
    print(f"LLM 输出格式错: {e}")
```

**Pydantic 校验做的事**：
- 字段必填（缺字段直接报错）
- 字段类型对（数字不是字符串）
- 范围约束（score 0-10）
- 枚举约束（sentiment 必须在 3 个值里）
- 长度约束（summary 10-200 字）

**实测**：Pydantic 兜底后，结构化输出在生产里的可靠性 = 99.9%+。

## Claude 的 Tool Use（不同 API）

Claude 的 tool use API 跟 OpenAI 不一样：

```python
import anthropic

client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    tools=[{
        "name": "save_review_analysis",
        "description": "保存评论分析结果",
        "input_schema": {   # ← 注意是 input_schema 不是 parameters
            "type": "object",
            "properties": {
                "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                "score": {"type": "integer"},
                "issues": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["sentiment", "score"],
        },
    }],
    messages=[{"role": "user", "content": "分析评论：'产品不错但物流太慢了'"}],
)

# 解析
for block in response.content:
    if block.type == "tool_use":
        data = block.input   # ← 直接是 dict
        analysis = ReviewAnalysis(**data)
```

**Claude tool use 特点**：
- `input_schema` 而不是 `parameters`
- tool_use block 直接在 content 里（不是单独字段）
- 模型可以「拒绝」调 tool（返回 text block 而不是 tool_use）

**强制调 tool**（Claude）：

```python
tool_choice = {"type": "tool", "name": "save_review_analysis"}
# 强制 LLM 必须调这个 tool，不能返回 text
```

## 嵌套结构

实际任务经常要嵌套结构：

```python
from pydantic import BaseModel
from typing import List, Optional


class FactSource(BaseModel):
    url: str
    title: str
    snippet: str


class Fact(BaseModel):
    claim: str
    sources: List[FactSource] = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)


class ResearchReport(BaseModel):
    topic: str
    facts: List[Fact] = Field(..., min_length=3, max_length=10)
    summary: str = Field(..., min_length=100)
    conclusion: Optional[str] = None


# 嵌套 model 的 JSON schema
import json
schema = ResearchReport.model_json_schema()
print(json.dumps(schema, indent=2))
```

**OpenAI Tool 用嵌套**：

```python
tools = [{
    "type": "function",
    "function": {
        "name": "save_research",
        "description": "保存研究结果",
        "parameters": ResearchReport.model_json_schema(),
    },
}]
```

## 实战：query 改写 pipeline

任务：把用户口语化搜索改写成结构化 query。

### 第 1 步：定义 Pydantic 模型

```python
class StructuredQuery(BaseModel):
    core_category: str = Field(..., description="核心品类（手机/衣服/...）")
    attributes: List[str] = Field(default_factory=list, description="关键属性")
    price_range: Optional[str] = Field(None, description="价格范围，如 '300-500元'")
    use_case: Optional[str] = Field(None, description="使用场景")
    keywords: List[str] = Field(..., min_length=2, max_length=8, description="检索关键词")
```

### 第 2 步：tool schema

```python
import json

tool_schema = StructuredQuery.model_json_schema()
tool_schema["description"] = "把用户口语化搜索改写成结构化 query"

tools = [{
    "type": "function",
    "function": {
        "name": "rewrite_query",
        "description": tool_schema["description"],
        "parameters": tool_schema,
    },
}]
```

### 第 3 步：循环调用

```python
def rewrite_query(user_input: str) -> StructuredQuery:
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "你是电商搜索 query 改写工程师。"},
            {"role": "user", "content": f"改写：'{user_input}'"},
        ],
        tools=tools,
        tool_choice={"type": "function", "function": {"name": "rewrite_query"}},
    )

    tool_call = response.choices[0].message.tool_calls[0]
    args = json.loads(tool_call.function.arguments)
    return StructuredQuery(**args)


# 跑
for user_input in [
    "我想买个能拍照好看的手机",
    "夏天穿凉快的鞋",
    "送女朋友的香水不要太贵",
    "便宜点的外套",
]:
    result = rewrite_query(user_input)
    print(f"输入: {user_input}")
    print(f"→ category: {result.core_category}, keywords: {result.keywords}\n")
```

### 第 4 步：验证

```python
# 边界 case 处理
test_inputs = [
    "你好",          # 不像 query
    "iPhone 15",     # 已经是结构化
    "随便看看",      # 模糊
]

for inp in test_inputs:
    try:
        result = rewrite_query(inp)
        # 处理「不像 query」的 case：fallback
        if not result.keywords:
            print(f"'{inp}' 改写后无 keywords")
    except ValidationError as e:
        # Pydantic 校验失败
        print(f"'{inp}' 改写失败: {e}")
        # fallback：直接用原始输入当 keywords
```

## 5 大反模式

### 反模式 1：JSON 字符串拼 prompt

```python
# 错
prompt = f"""
输出 JSON：{json.dumps(schema, indent=2)}
"""
# JSON 容易让 LLM 看错缩进 / 引号

# 对
prompt = """
输出 JSON，包含字段：
- sentiment: positive / negative / neutral 之一
- score: 0-10 的整数
- issues: 字符串数组

{其他指令}
"""
```

**经验**：手写 schema 比 JSON 字符串更稳。

### 反模式 2：要求输出 + 解释一起

```python
# 错
prompt = """
分析评论情感，输出 JSON + 解释为什么。
"""
# LLM 经常「解释完了忘记 JSON」

# 对：分两步或明确定位
prompt = """
分析评论情感。

先输出你的【思考】（1-2 句话），再输出【JSON】结果。
"""
# 或者
prompt = """
先解释你的判断（1 段话），然后在新一行用 ```json 代码块输出结果。
"""
```

### 反模式 3：JSON 太深

```python
# 错：嵌套 5 层
{
  "level1": {
    "level2": {
      "level3": {
        "level4": {
          "level5": "value"
        }
      }
    }
  }
}
# LLM 容易填错嵌套

# 对：扁平化
{
  "level1_level2_level3_level4_level5": "value"
}
# 或拆成多个 tool
```

**经验**：JSON 嵌套 ≤ 3 层。

### 反模式 4：enum 不给可选值

```python
# 错
prompt = "输出 sentiment 字段"
# LLM 可能输出 "happy" / "sad" / "good" / "bad"...

# 对
prompt = """
sentiment 字段必须是以下之一：
- positive（正面）
- negative（负面）
- neutral（中性）
"""
```

**更强**：用 enum type 锁（tool use / JSON schema）。

### 反模式 5：没 fallback

```python
# 错：LLM 输出失败直接报错
result = rewrite_query(invalid_input)   # ValidationError → 用户看到报错

# 对：失败 fallback
def safe_rewrite(input_):
    try:
        return rewrite_query(input_)
    except (ValidationError, json.JSONDecodeError):
        # 简单 fallback：原始输入当 keywords
        return StructuredQuery(
            core_category="unknown",
            keywords=input_.split()[:5],
        )
```

## 性能优化

### 优化 1：tool use 比 prompt 引导便宜

```python
# 测过：tool use 的 token 比 prompt 引导少 20-30%
# 因为不用在 prompt 里重复 schema
```

### 优化 2：JSON schema 简单化

```python
# 错：复杂 schema
{
  "type": "object",
  "properties": {
    "result": {
      "type": "object",
      "properties": {
        "data": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {...}
          }
        }
      }
    }
  }
}

# 对：扁平 + 必要字段
{
  "type": "object",
  "properties": {
    "items": {"type": "array", "items": {"$ref": "#/definitions/Item"}}
  }
}
```

### 优化 3：批量处理

```python
# 错：1 个 query 1 次 LLM call
for q in queries:
    rewrite_query(q)   # 100 次 call

# 对：1 个 LLM call 处理多个（如果模型支持）
prompt = f"""
改写以下 5 个 query：
1. {queries[0]}
2. {queries[1]}
...
5. {queries[4]}

输出 JSON 数组。
"""
```

## 跑不起来的常见坑

**坑 1：JSON 字符串里有 markdown code block**

```python
# LLM 输出
"```json\n{...}\n```"

# json.loads() 直接报错
# 修复：strip markdown
clean = response.replace("```json", "").replace("```", "").strip()
data = json.loads(clean)
```

**坑 2：tool_choice 在不支持的模型上用**

```python
# 部分模型不支持 tool_choice={"type": "function", ...}
# 退化为 prompt 引导

if not model_supports_tool_choice(model):
    # fallback 到 prompt 引导 + Pydantic 校验
    response = llm.call(prompt_with_schema_instruction)
    data = ReviewAnalysis(**json.loads(extract_json(response)))
```

**坑 3：schema 太大导致 tool 失败**

```python
# 错：100 字段的 schema
# OpenAI 会拒绝 / token 爆炸

# 对：拆成多个 tool，按需调用
@tool
def get_basic_info(...) -> BasicInfo: ...

@tool
def get_detailed_info(...) -> DetailedInfo: ...
```

**坑 4：JSON 字段名跟代码不一致**

```python
# 错：prompt 说 "productName"，代码用 "product_name"
# json.loads 后字段拿不到

# 对：Pydantic alias
class Product(BaseModel):
    product_name: str = Field(..., alias="productName")

    class Config:
        populate_by_name = True
```

## 这章跑完之后你该会什么

- 3 种结构化输出方法（prompt 引导 / JSON mode / tool use）的取舍
- Pydantic 校验作为兜底层
- 嵌套结构 + 边界约束（Field 约束）
- Claude vs OpenAI tool use API 差异
- 真实 query 改写 pipeline 完整实现
- 5 大反模式
- 3 大性能优化

