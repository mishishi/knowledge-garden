# 06. Batch vs Stream

OpenAI 的 Batch API 给 50% 折扣。我一开始以为"那肯定用 batch 啊，便宜一半"。后来发现事情没那么简单。

Batch 的代价是**延迟**。不是 streaming 的 token 延迟，是"提交 → 拿到结果"的整体延迟。OpenAI 承诺 24 小时内，但实际 1-6 小时。**意味着你的用户不能等**。

什么时候能 batch？什么时候必须实时？我用 4 个真实 case 讲清楚。

## Batch API 怎么计费

OpenAI Batch API：

- 价格：input / output **各打 5 折**
- 延迟：1-6 小时（无 SLA）
- 输入：JSONL 文件，10K request 上限
- 输出：JSONL 文件，逐行拿结果

实际算账：

```
实时 1 个 call:  GPT-4o input 2K + output 500 = $0.0056 + $0.005 = $0.0106
Batch 1 个 call:  同样 prompt = $0.0028 + $0.0025 = $0.0053
```

50% off。一个月 1 万次 call 省 $53。

但前提是**这些 call 都不着急**。

## 4 个 case 决定 batch 还是 stream

**Case 1 — 用户实时对话**（agent 客服、coding assistant）

不能 batch。用户等 1 秒都觉得慢。

但**用户实时对话里的 background 任务**可以 batch。agent 收到用户消息 → 返回 reply → 后台 batch 一些 heavy task（比如"学习这个对话"、"更新 user profile"、"index 这次对话到 RAG"）。这些跟用户对话异步，对延迟不敏感。

我的 agent 70% 的 call 是用户实时对话，30% 是后台 housekeeping。后台全部 batch。**省 $40/月**。

**Case 2 — 批量数据处理**（每天扫 1K 条 review 做 sentiment）

必须 batch。本来就是 offline job，攒一天一次跑完最合理。

如果用实时 API 跑 1K 条 review：
- 串行：1K × 2 秒 = 33 分钟（用户视角）
- 并行 10：3.3 分钟（你付 10 倍瞬时成本，OpenAI 限速 10K RPM 你可能撞墙）

batch：1K 条 request 一次提交，2 小时后回来，**省一半钱 + 你的服务器 0 占用**。

**Case 3 — Eval 任务**（跑 golden set 测 prompt 改动效果）

必须 batch。Eval 本来就是 batch job，能等 1 小时。

很多 indie 犯的错：eval 跑实时 API。eval 一次 100 个 case × $0.05 = $5。一个月改 5 次 prompt = $25。batch 打 5 折 = $12.5。**一年省 $150**。

**Case 4 — 定时 summarization**（每天给用户发邮件总结他们的 agent 对话）

应该 batch。每天定时（比如凌晨 3 点）攒所有用户的对话一次跑，第二天早上 8 点之前完成。

但**别每天 batch**。如果你要实时给用户提示（比如"你的 agent 刚完成一个任务"），那必须实时。

## 怎么判断能不能 batch

三个问题：

**1. 用户当前在等结果吗？**

在等 → 实时。不在等 → batch。

**2. 这个 call 失败能重跑吗？**

能 → batch（batch API 失败会重试，你不用管）。不能（必须 idem-potent + 立即知道结果） → 实时。

**3. 这个 call 是关键路径还是辅助路径？**

关键路径（用户看到结果） → 实时。辅助路径（log、stats、cache 更新） → batch。

## 我的 batch 实战：50% 折扣拿满

跑 6 个月 batch 之后我的账单构成：

| 用途 | 频率 | 实时/batch | 月 cost |
|---|---|---|---|
| 用户对话 | 27K call | 实时 4o + cascade mini | $85 |
| 后台 housekeeping | 8K call | batch 4o-mini | $8 |
| Eval (golden set) | 5 次 × 100 | batch 4o-mini | $1.5 |
| 文档 indexing (RAG) | 1.2K doc | batch 3.5-turbo | $0.8 |
| 用户 summary 邮件 | 500 封 / 天 | batch 4o-mini | $12 |

实时 $85，batch $22.3。**batch 占了 21% 的工作量只花 21% 的钱——刚好**。剩下的 79% 工作量是用户对话不能 batch。

如果我什么都不 batch，全部走实时：**总账单会到 $155**（85 × 1.5 + 22.3 × 1.5）。batch 让我**少花 $48/月**。

## 几个 batch 陷阱

**1. JSONL 写错格式 → 整个 batch 失败**

OpenAI Batch 校验很严。JSONL 一行一个 request，schema 必须对。**先在 1K call 试 1 个 batch 验证 pipeline，再上 10K**。

**2. Output 也是 JSONL，要解析回来**

不要假设 line 顺序跟 input 一致。每个 output 有 `custom_id` 字段，从 input 时就要传，output 用这个字段 join。

```python
results_by_id = {}
for line in batch_output_file:
    r = json.loads(line)
    results_by_id[r["custom_id"]] = r["response"]["body"]
```

**3. Batch 失败重试有上限**

OpenAI 失败超过 5 次自动放弃这个 request。你要自己 catch 这种情况 fall back 到实时 API，否则用户数据会丢。

**4. 价格是固定的，但 RATE LIMIT 也是**

Batch 走专门的限速池，不跟实时 API 抢配额。但 batch 池本身也有 200 RPM 限制。1 万 call 的 batch 大概要 1 小时发出去。

下一章讲用户粒度 quota——前面 5 章都是"我"的成本优化，这章开始"管别人怎么用我的 agent"。
