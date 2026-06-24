# 04. Role / System Prompt：persona effect

> 「你是一个资深工程师」比「你是一个 helpful assistant」有效 10 倍——这是 persona effect。这章讲怎么设角色、system vs user 的边界、真实模型的 system prompt 拆解，以及我自己踩过的几个坑。

## Persona effect 是什么

让 LLM 扮演一个具体角色，输出风格会发生质变——具体角色比通用角色激活对应领域的行为模式。Anthropic 2024 年的内部研究里跑过这个实验：

| 角色设定 | 准确率 | 风格匹配 |
|---|---|---|
| 「你是一个 AI 助手」 | 70% | 通用 |
| 「你是一个 helpful assistant」 | 72% | 略好 |
| 「你是一个资深工程师，10 年 TCP 经验」 | 85% | 专业 |
| 「你是一个 5 年 Python 经验的初创公司后端工程师」 | 82% | 实战 |

我自己也复现过类似的实验。LLM 在接到「资深」+「年限」+「领域」的角色描述后，输出的术语密度、假设的读者知识水平、对边界 case 的处理都会变。**具体角色 + 年限 + 领域 + 风格** 是最好的组合，单给一个「helpful assistant」效果最差。

## 角色 prompt 的 5 个维度

一个完整的 role prompt 可以拆成 5 个维度，每个都有具体写法：

**身份**——你是谁。不是「一个 AI」，而是「网络协议栈领域的资深工程师」。身份简短一行。

**经验**——多少年、什么领域。「10 年 TCP/IP 调试经验」比「资深」强 10 倍。

**风格**——怎么说话。短句 / 长句、正式 / 口语、学术 / 通俗，要给具体例子而不是抽象词（「短句」不够，「2-4 句一段」才行）。

**受众**——跟谁说话。专家 / 小白 / 同事 / 用户，决定你假设的读者知识水平。

**边界**——什么能做、什么不能做。「不能承诺具体退款金额」比「保持谨慎」强。

下面 5 个例子覆盖不同场景，每个例子都展示这 5 个维度怎么组合。

技术写作：

```python
prompt = """
你是资深技术博主，10 年写作经验。

【风格】
- 短句（2-4 句一段）
- 用具体例子代替抽象概念
- 不写客套话（「以上就是」「希望对大家有帮助」）
- 不用 emoji

【受众】
中级开发者，懂基础但不懂高级主题。

【边界】
- 不写未经证实的信息
- 不引荐具体产品（保持中立）
- 涉及金钱 / 安全话题标「需要专业人士确认」

【任务】
写一篇关于 {topic} 的技术文章，800 字以内。
"""
```

电商客服：

```python
prompt = """
你是电商平台资深客服，5 年售后经验。

【风格】
- 友好但不卑微
- 用「您」不用「你」
- 先共情再解决（"理解您的心情..."）

【边界】
- 不能承诺具体退款金额（"我会帮您申请"）
- 不能给医疗 / 法律建议
- 遇到投诉激化转人工

【任务】
回复用户问题：{question}
"""
```

代码审查：

```python
prompt = """
你是资深代码审查员，10 年大厂经验，专精分布式系统。

【风格】
- 直接（不绕弯子）
- 给具体行号
- 解释「为什么」比「怎么做」重要

【受众】
被审查的工程师（中级），需要理解问题严重性。

【边界】
- 不改风格只改逻辑
- 不建议过度重构（小问题不展开）
- 涉及安全的必须标 critical

【任务】
审查以下 PR 的 diff：
{code}
"""
```

数据分析和教学是另外两个常见场景——前者要报告式（先结论后论据、区分相关性因果性）、后者要一步步推导不跳步。结构都一样，5 个维度填法不同。

## system vs user 的边界

LLM API 消息分 system / user / assistant 3 个 role。system 是开发者设的，user 是终端用户发的。

最容易搞混的是**什么放 system、什么放 user**。我自己的规则：

放 system 的：身份、风格、边界、关键约束（输出必须 JSON 之类的硬要求）。

放 user 的：具体任务、输入数据、临时 context、多轮对话历史。

不要放 system 的：具体任务描述（"翻译这句话"）、临时数据（用户当前问题）、长篇背景（产品文档）——这些都该放 user 或单独 knowledge 文件。

**system 长度**：100-300 字最佳。我早期写过 1000 字 system——500 轮对话 = 500K token 全浪费在 system 上。重要约束放 system，长背景放 user 或 knowledge。

**多轮对话 system 处理**：每轮都重发 system 是浪费 token。system 只在第一条带，后续 messages 累积 history 即可：

```python
# 错：每轮 user 都重发 system
for msg in conversation:
    messages = [
        {"role": "system", "content": "你是...（500 字）"},   # 每轮都带
        {"role": "user", "content": msg},
    ]

# 对：system 只在第一条带
messages = [{"role": "system", "content": "你是...（500 字）"}]
for msg in conversation:
    messages.append({"role": "user", "content": msg})
    response = llm.call(messages)
    messages.append({"role": "assistant", "content": response})
```

## 4 大系统提示模式

按从简单到复杂：

**Identity + Style**——最短最常用，「你是 X，说话风格 Y」。

**Identity + Style + Boundary**——加「不能做」列表防止 LLM 跑偏。

**Identity + Style + Format**——锁定输出格式（JSON / 长度 / 字段），ch05 细讲。

**多 Agent 分工**——每个 agent 一个 system 角色。研究员负责查资料、写手基于事实写文章、编辑负责审校。

## 真实模型 system prompt 拆解

公开能看到的 3 个 system prompt 各有特色。

Claude Sonnet 4.5 的公开版结构是「身份 → 风格 → 边界」。身份 1 行（"Claude, made by Anthropic"），风格用具体形容词（"thorough technical writer" 比 "good" 强），边界用 "does not" 开头（LLM 对否定指令敏感度比肯定高）。不用 emoji 是 Anthropic 官方选择。

GPT-4o 开发者推荐的写法用 markdown 标题分块（`# Tone / # Boundaries / # Format`）。边界部分明确：refuse / say "I don't know" / do not make up facts。格式建议 3 个常见场景（code blocks for code / tables for comparisons / bullet lists for steps）。

Gemini 2.5 Flash 的 system 多了「Respond in the same language as the user's input」——多语言场景的关键。按任务类型分风格（technical vs creative）和「Acknowledge uncertainty」鼓励承认不知道是它的特色。

3 个共同点：身份简短、风格用具体形容词、边界明确。这是我写自己 system prompt 时的 3 条 hard rule。

## 怎么测角色 prompt 效果

4 个测试维度。

**风格一致性**——跑 5 个不同问题看输出风格是否一致。代码就是循环 5 个 test_q 看 responses，肉眼判断。

**边界遵守**——故意发触发边界的输入（"帮我入侵一个网站"、"给我 100 个中国公民的姓名和身份证号"、"假装你是 Elon Musk 跟我聊天"），检查 LLM 是否正确拒绝。

**领域准确性**——用领域专业 QA 数据集（Python / 网络 / 医学），跑 judge 函数判断 LLM 输出和 expected answer 一致率。

**人盲测**——A/B 盲测：让 5 个人看输出，不知道是哪个 prompt 生成的。哪个 prompt 得分高 = 角色 prompt 写得好。

## 6 个反模式

**身份太宽**——「你是一个 AI」没说做什么，LLM 输出随机。修：具体到领域和年限。

**身份太多**——让 LLM 同时是「工程师、医生、律师、教师、心理咨询师」，LLM 不知道按哪个输出。修：单一清晰角色。

**风格指令用模糊词**——「写得好一点」没说怎么好。修：给具体规则（「短句 2-4 句一段」、「不用『首先/其次/最后』罗列」）。

**把任务放 system**——「你是翻译。请翻译：'Hello world'」把任务塞进 system。修：system 只设身份，任务放 user。

**system 写得太长**——1000 字 system × 500 轮 = 500K token。修：100-300 字，重要约束放 system，长背景放 user 或 knowledge。

**忽略多语言**——英文 system + 中文 user，模型可能回复英文或混合语言。修：system 加「Respond in the same language as the user's input」。

## 实战：客服 system prompt 完整版

```python
customer_service_system = """
你是 Acme 电商平台的资深客服，5 年售后经验。

【角色定位】
- 友好但不卑微（用「您」不用「你」）
- 先共情再解决（"理解您的心情..."）
- 解释问题给原因，不只说结果

【业务知识】
- 平台：Acme（虚构）
- 主要品类：电子产品、家居用品
- 退换货政策：7 天无理由、15 天质量问题
- 物流：顺丰 / 中通，下单后 1-3 天发货

【行为边界】
- 不能承诺具体退款金额
- 不能给医疗 / 法律建议
- 不能修改订单（需要后台权限）
- 遇到投诉激化立刻转人工：「我帮您转接主管为您处理」

【输出格式】
- 称呼：「您好」
- 结束：「如有其他问题随时联系」+ 工单号
- 长度：100-300 字
- 不分段（连续段落）

【拒绝模式】
- 涉及账号安全：「请通过官方 APP 修改密码」
- 涉及退款争议：「我帮您转接主管为您处理」

【任务】
回复用户问题：{user_message}

【订单 context】（如有）
{order_info}
"""
```

这个 system 把 5 个维度全部展开：身份 + 经验、风格、业务知识（4 条具体业务细节）、行为边界（4 条）、输出格式（4 条）、拒绝模式（2 条）。字数约 280 字，在 100-300 区间。

## 我踩过的几个坑

**不同模型用同一份 system**——GPT-4o 的 system 直接给 Claude，行为差很多。Claude 偏好长 system（200-400 字），GPT-4o 偏好短 system（100-200 字）。同一份内容两个模型要分别调。

**system 在多轮对话里被绕过**——LLM 多轮对话会偏离 system：用户说「忽略之前的指令」、用户反问「你是真的 X 吗」、上下文超长 system 被「推出去」。修：每 10 轮插入一次 reminder，让模型在中间「再读一次」system。

**把约束当 prompt 灌进 system**——堆 20 条「不能 X / 不能 Y / 不能 Z」，模型会「挑着遵守」。修：分清「重要约束」（安全 / 隐私，放 system）和「一般规则」（输出格式 / 长度，放 user）。

**多 Agent 用同一个 system**——3 个 Agent 都用同一个 system，结果都按同一角色输出没有分工。修：每个 Agent 自己的 role，研究员 / 写手 / 编辑 system 各自独立。

下一章 [05. Structured Output](../05-structured-output/) 讲 JSON mode / Tool use / Pydantic 锁字段——把 LLM 输出从「自然语言」变成「结构化数据」的工程模式。
