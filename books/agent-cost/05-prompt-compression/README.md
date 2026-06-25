# 05. Prompt 压缩

Cache 把"重复"省了，routing 把"杀鸡用牛刀"省了，但**prompt 本身臃肿**这件事 cache 救不了你——每次都是新内容，每次都付全价。

我有个 agent 的 system prompt 一开始 8K token。**8K**。一个"你是 agent"开头，5 个工具描述，3 个示例，2 个边界规则，1 个格式要求。

review 的时候我自己看吐了。但删不动——每个部分当初都是因为模型出过错才加的，删了怕回归。

8 个月后我硬着头皮用 LLM 做 prompt rewriting + 手动 audit，把 8K 压到 1.2K。能力评估下来：复杂任务质量 -3%，简单任务 +1%（因为 context 短了模型更 focus）。**月账单省 $45**。

这一章是具体的压缩技术。

## 原则：先砍再说

我尝试过的 4 个技术，按 ROI 排序：

1. **抽象 + 反例替代长规则** — 1 个反例胜过 3 行说明
2. **Prompt rewriting** — 让 LLM 自己重写自己的 prompt
3. **Few-shot distillation** — 把 few-shot 蒸馏进 system description
4. **Context compression** — 跑前先用便宜 model 总结长 context

每个独立讲，最后给一个组合拳。

## 1. 抽象 + 反例 — 1 个反例胜过 3 行规则

我那条 "不要在回复里使用 emoji" 原本是这样写的：

```
你是一个专业的客服 agent。在回复用户时，请确保：
1. 不要使用任何 emoji 符号（包括但不限于 😊 🎉 ❤️ 等）
2. 保持专业、礼貌的语气
3. 回答要简洁明了，避免冗余
...
```

5 行。换成反例：

```
不要在回复里用 emoji。错误示例：😊 感谢您的咨询。
```

7 行（包含错误示例），但**模型遵守率反而更高**。

**经验法则：模型对"反面例子"比对"正面规则"敏感**。不要写"应该做什么"，写"不要做什么" + 一个反例。

我那个 8K prompt 砍 30% 是用这个方法。规则从"应该 X 应该 Y 应该 Z"变成"错误示例：X Y Z"。

## 2. Prompt rewriting — 让 LLM 重写自己的 prompt

这招意外有效。把当前 prompt 喂给一个 LLM，让它 "保留所有意图，重写得更紧凑"。

```python
def compress_prompt(prompt, target_tokens):
    rewrite_prompt = f"""以下是当前的 system prompt。请你重写它，让它更紧凑（目标 {target_tokens} token 以内），
但保留所有行为约束和质量要求。

输出要求：
- 不要改变原始意图
- 删除冗余
- 用更紧凑的句式
- 输出完整的新 prompt

原 prompt：
{prompt}
"""
    return call_llm(rewrite_prompt, model="gpt-4o")
```

跑了 3 次取最短的、但 eval 分数不降的那个。LLM 比人写 prompt 更激进（它没有"这样删会不会出问题"的焦虑）。

注意：**别让 LLM 加新内容**。给它的指令要明确"保留所有意图"+"不允许改语义"。否则它会"helpful"地加新规则。

我的经验：这个方法一次能砍 40-60%。配合下面的方法，8K → 2K 不是梦。

## 3. Few-shot distillation — 把示例炼进 description

我原本有 3 个完整示例：

```
例子 1：
用户：今天北京天气怎么样？
Agent：[完整回答 + JSON 格式]

例子 2：
用户：...[同上]

例子 3：
用户：...[同上]
```

3 个示例每个 800 token，共 2400 token。模型从这 3 个示例里学到的是：
- JSON 格式
- 简洁语气
- 不啰嗦

但其实**一个示例 + 一行说明**也能教会模型同样的事：

```
回复格式：{"answer": "...", "sources": ["..."], "confidence": 0.0-1.0}
语气：简洁专业，跟这个示例一致：[一个 100 token 示例]
```

省 1800 token。

经验法则：**few-shot 数量从 3 减到 1 通常影响很小，从 1 减到 0 可能掉 5-10%**。挑一个最有代表性的留着。

## 4. Context compression — 跑前先压缩

这一招对付**用户输入**而不是 system prompt。

场景：用户粘了 200 行代码进来让 agent debug。这段 8000 token 必发。

但你其实只需要"相关 50 行"。先跑一个 cheap model：

```python
def compress_user_input(user_input, query, max_tokens=2000):
    compress_prompt = f"""用户问：{query}
用户提供的内容：
{user_input}

请保留跟回答用户问题相关的部分，删除无关内容。
输出压缩后的内容（不超过 {max_tokens} token）。
"""
    return call_llm(compress_prompt, model="gpt-4o-mini")
```

注意：这一步本身花 token，但 mini 处理 8K input 也就 $0.02。如果主 call 4o + 8K input 是 $0.02，**总成本不变 + 后面 cascade 命中率提升**（context 短了 mini 也能答对）。

## 5. 压缩的 3 个反模式

**别压的：**
- 任务关键信息（数值、约束、边界）— 这些不能省
- 用户输入里关键的 ID / 名称 / 数字 — 改名 / 缩写模型可能不认
- System prompt 里的 "你是 X" 这类身份声明 — 砍了模型会"扮演"别的

**别瞎压的：**
- 输出格式要求（JSON schema）— 砍了模型就开始 free-form
- 工具签名（必须精确匹配）— 砍了 tool call 出错率暴涨
- 评估标准（"用 K 个来源"）— 砍了模型不知道 benchmark

**别激进到：**
- 用缩写（"u" = user, "a" = agent）— 模型不认
- 删除标点（"hello,world" vs "hello, world"）— 影响 token 解析
- 强行塞 1 个 prompt 进 100 token — 复杂任务至少 500 token

## 我的 4K → 800 实战

8K → 1.2K 用了 3 轮，每轮 eval 一次：

| 轮次 | 操作 | 长度 | Eval 分数 | 月成本 |
|---|---|---|---|---|
| 0 | 原始 | 8200 | 0.87 | $400 |
| 1 | 抽象 + 反例 | 5800 | 0.87 | $310 |
| 2 | Prompt rewriting | 2100 | 0.85 | $180 |
| 3 | Few-shot distillation | 1200 | 0.84 | $110 |

每轮 5 小时（含 eval），共 15 小时。**省 $290/月 = 1.5 个月回本**。

下一章讲 batch vs stream——同样是 LLM call，"实时返回 1 个"和"攒 50 个一起算"成本能差 50%。
