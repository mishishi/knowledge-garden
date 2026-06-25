# 01. Prompt 基础 + Token 经济学

> 写好 prompt 跟写好代码一样——知道每一行在干什么，比套用模板重要 10 倍。这章拆 4 元素、怎么算钱、不同模型 prompt 风格的差异。

## 4 元素 Anatomy

任何 prompt 都由 4 部分组成——缺一个不完整，多一个反而乱：

```
┌─ ROLE     你是谁（persona / 视角 / 边界）
├─ CONTEXT  必要背景（数据 / 约束 / 之前发生过什么）
├─ TASK     要做什么（具体动作 + 验收标准）
└─ FORMAT   输出格式（JSON / markdown / 长度限制）
```

**ROLE：身份 + 边界**——让模型「扮演」某个具体角色比「你是一个 helpful assistant」效果好。具体角色（资深工程师 / 10 年律师 / 翻译）激活对应领域行为模式。

```python
# 差：只说身份
prompt = "你是翻译。"

# 好：身份 + 边界 + 风格
prompt = """
你是一个技术文档翻译，把英文翻译成中文。
- 保留代码块、API 名、专有名词不译
- 语气正式，避免口语化
- 不确定时保留英文原文 + 括号注释
"""
```

**CONTEXT：必要背景**——决定输出的针对性。同样 task，给「电商平台客服」和「品牌营销人员」是不同输出。

```python
# 差：没 context
prompt = "分析这段评论的情感。\n评论：..."

# 好：给 context
prompt = """
你是电商平台客服质检。

【任务】
分析下面这条用户评论的情感。

【输出要求】
- 0-10 分，0 = 极度负面，10 = 极度正面
- 标注主要问题（物流 / 质量 / 服务 / 其他）
- 一句话总结

【评论】
{review}
"""
```

**TASK：动词 + 验收标准**——动词要可验证：分析 / 列出 / 总结 / 重写 / 翻译。避免「看看 / 想一下 / 优化」这种模糊词。

```python
# 差：动词模糊
"帮我看看这个代码"

# 好：动词明确 + 验收标准
"找出这个函数的所有性能问题（O(n²) 以上的循环、内存泄漏、阻塞 IO），按严重程度排序，每条问题给具体修复建议。"
```

**FORMAT：输出格式**——决定下游可解析性。JSON / markdown / 列表 / 表格——选对格式能省下游 50% 处理代码。

```python
# 差：没格式
"写一个产品介绍"

# 好：明确格式
"写一个 200 字以内的产品介绍，markdown 格式，分 3 段：问题、方案、特点。不要 emoji。"
```

## 4 元素怎么组合

4 元素不一定都齐全，**取决于任务复杂度**：

| 任务 | 必需元素 | 可省 |
|---|---|---|
| 翻译这句话 | TASK | ROLE / CONTEXT / FORMAT |
| 分析评论 | TASK + FORMAT | ROLE / CONTEXT |
| 写产品介绍 | TASK + FORMAT + ROLE | CONTEXT（产品自己就是 context）|
| 分析代码 bug | 4 个都要 | — |
| 模拟 X 角色回答 Y 问题 | ROLE + CONTEXT + TASK | FORMAT |

经验：3 元素以上时，**用 markdown 标题分块**——LLM 对结构化文本解析比散文好 30%。

## Token 经济学

写 prompt 前先懂钱——**prompt 越长，token 越多，调用越贵**。

**怎么算 token**——用 tiktoken：

```python
import tiktoken
enc = tiktoken.encoding_for_model("gpt-4o")
tokens = enc.encode("你好世界")
print(len(tokens))  # 3 tokens（中文 1 字符 ≈ 1-2 token）
```

经验公式：1 个英文单词 ≈ 1.3 token，1 个中文字 ≈ 1.5 token，1 行代码 ≈ 10-30 token，1 张图片（1024x1024）≈ 85-255 token（按 tile 计费）。

**价格表（2026 年中）**：

| 模型 | Input $/1M | Output $/1M | 备注 |
|---|---|---|---|
| GPT-4o | 2.50 | 10.00 | 综合强 |
| GPT-4o-mini | 0.15 | 0.60 | 性价比首选 |
| Claude Sonnet 4.5 | 3.00 | 15.00 | 长 context / code |
| Claude Haiku 4.5 | 1.00 | 5.00 | 轻量任务 |
| Gemini 2.5 Flash | 0.15 | 0.60 | 多模态强 |
| DeepSeek V3 | 0.14 | 0.28 | 便宜到离谱 |
| o3 (reasoning) | 10.00 | 40.00 | 复杂推理 |

**算个账**——3 段 prompt × 2000 input + 1 段 response × 500 output：

- GPT-4o-mini：$0.0012 / 次
- GPT-4o：$0.006 / 次
- o3：$0.038 / 次

**100 万次调用 = GPT-4o-mini $1,200，GPT-4o $6,000，o3 $38,000**。差距 30 倍。**选错模型烧光预算**。

**哪里在烧 token**——3 个最常见烧钱点：

1. **重复 system prompt**——每条消息都带 system，10 轮对话 = 10 次 system token。修：用 conversation history 复用，不每条都重发 system。
2. **大 context 不缓存**——5000 token context 跑 100 次 = 500,000 token input。修：**Prompt caching**（ch07 细讲）。
3. **reasoning model 滥用**——o3 处理「翻译这句话」就是烧钱。修：简单任务用 mini / haiku / flash，reasoning 留给复杂任务。

## 不同模型 prompt 风格的差异

同样的 prompt 在不同模型上效果差很多——**不是越长越好，是「对模型口味」**。

**GPT-4o / GPT-4o-mini（OpenAI）**——严格遵守 system prompt 指令，擅长 JSON / Tool use，写代码质量高，推理能力中上。Prompt 风格：直接给指令少铺垫，明确格式（「输出 JSON，包含 X、Y、Z 字段」），避免冗长背景。

```python
prompt = """
你是 Python 后端工程师。

任务：找出下面代码的安全漏洞（SQL 注入、XSS、密钥泄露、权限绕过）。

输出格式：markdown 列表，每条漏洞格式：
- 严重程度：critical / high / medium / low
- 行号：N
- 描述：1 句话
- 修复：具体代码示例

代码：
```python
{code}
```
"""
```

**Claude Sonnet 4.5（Anthropic）**——严格遵守 system prompt，长 context（200K）下表现好，写作质量高，不喜欢「step by step think」强制 CoT。Prompt 风格：给完整背景（context 写多），强调「不能 X」（边界明确），多给示例。

**Gemini 2.5 Flash（Google）**——多模态强（图像 + 视频 + 音频），长 context（1M token），价格便宜，中文表现稍弱。Prompt 风格：多模态描述要详细（「图中的蓝色框」，不能只说「这个」），适合多模态分析任务。

**Reasoning model（o3 / Claude with thinking）**——自动「思考」，不强制要 CoT prompt，慢（10-60s）贵，简单任务反而效果差（容易过度思考）。Prompt 风格：**直接给任务，不要加 CoT 引导**，给完整信息（模型会自己思考），复杂任务用，简单任务别用。

```python
# 错：reasoning model + CoT 引导
prompt = "Let's think step by step. 任务：证明这个定理。"

# 对：直接给任务
prompt = "证明：对于任意正整数 n > 1，存在素数 p 满足 n < p < 2n。直接给完整证明。"
```

**reasoning model 加 CoT 引导反而干扰它**——它自己会想，被强制按你的格式反而不自然。

**怎么选模型**——按任务类型：

- 翻译 / 摘要：Claude Haiku 4.5 / GPT-4o-mini
- 代码生成：Claude Sonnet 4.5 / GPT-4o
- 数据提取（JSON）：GPT-4o-mini（strict JSON 模式）
- 复杂推理：o3 / Claude with thinking
- 多模态：Gemini 2.5 Flash
- 长文档分析：Claude Sonnet 4.5（200K context）
- 超低成本：DeepSeek V3

**经验法则**：先 mini / haiku 试，效果差再上 sonnet / 4o，最后才用 reasoning。

## 3 个常见 prompt 错误

**错误 1：把「聊天风格」当 prompt**——跟 LLM 不要「客气」，它不会因为你语气好就更努力。直接给任务。

```python
# 错
"你好，我想请教一下，你能不能帮我..."

# 对
"任务：..."
```

**错误 2：把所有信息塞 prompt**——把整个产品文档塞 prompt 既贵又噪声。先 RAG 检索相关段落。

```python
# 错：把整个产品文档塞 prompt
prompt = f"产品文档：{50000_words_pdf_content}\n\n回答用户问题：{question}"

# 对：先 RAG 检索相关段落
relevant = vector_search(question, top_k=3)
prompt = f"相关文档：\n{relevant}\n\n问题：{question}"
```

50000 token 输入 = 12.5 美分/次（GPT-4o）。**先 RAG 检索再拼 prompt** 永远更便宜 + 更准。

**错误 3：不指定输出长度**——不指定 → LLM 默认 500-2000 字，看心情。**长 prompt 慢、贵、容易啰嗦**。

```python
# 错
"写一篇关于 X 的文章"

# 对
"写一篇 800 字以内的文章，markdown 格式，分 3 段"
```

## 跑不起来的常见坑

**坑 1：以为 prompt 是自然语言**——Prompt 是给 LLM 看的「配置文件」，不是给人看的「聊天」。**结构化 + 标题分块 + 明确格式**永远比散文式 prompt 好。

**坑 2：prompt 在多轮对话里越加越长**——每条都带 500 字 system → 100 轮对话 = 50,000 token system。**system 写短**（100 字以内），长背景放 context 或 knowledge。

**坑 3：跨模型复制 prompt**——GPT-4o 写得好的 prompt 不一定在 Claude 上好。**不同模型对「指令」的解析风格不同**——拿到好 prompt 后要在目标模型上跑测试。

## 写完 prompt 的 6 项检查清单

- 4 元素是否齐全（按任务复杂度调整）
- 动词是否可验证
- 输出格式是否明确
- 长度是否合理（system < 100 字，total < 4000 token）
- 跑在 3 个简单 case 上，是否能稳定输出
- 跑在 3 个 edge case 上，是否不胡说

第 5、6 项是关键——prompt 写完不跑 case = 赌博。
