# 07. Skills 测试与评估

2025 年 12 月我发布了一个 Skill，团队 3 个人用。**2 周后他们说"用不上"**。

我以为 Skill 写得不好。**实际是触发条件错**——他们 80% 的对话里我以为会触发的场景没触发，**反而在他们改 React 组件时被触发 5 次（不应该触发）**。

**没有测试 = 凭感觉发 Skill**。**这章讲怎么用 golden set 测 Skill**。

## 3 个评估维度

Skill 的质量用 3 个指标衡量：

**1. 触发准确率（Trigger Accuracy）**

模型在**该用**的时候调用 Skill 的比例。

```
触发准确率 = 实际触发的次数 / 应该触发的次数
```

**好的 Skill 触发准确率 ≥ 85%**。

**2. 触发拒绝率（Rejection Accuracy）**

模型在**不该用**的时候不调用 Skill 的比例。

```
触发拒绝率 = 正确拒绝的次数 / 应该拒绝的次数
```

**好的 Skill 触发拒绝率 ≥ 90%**。

**3. 输出质量（Output Quality）**

触发后，输出是否符合预期。

```
输出质量 = 符合预期的输出数 / 总触发数
```

**好的 Skill 输出质量 ≥ 80%**。

**3 个指标相乘 = 整体效果**。**1 个指标 50%**（哪怕其他 100%）= Skill 不可用。

## Golden Set 是什么

Golden Set = **标注过的测试用例集**。每个用例包含：
- 用户消息
- 预期行为（"该触发" / "不该触发" / "触发后输出 Y"）

**示例**（code-review Skill 的 golden set）：

```yaml
- id: 1
  user_message: "帮我 review 一下这段代码：function foo() {...}"
  should_trigger: true
  expected_output:
    - "using skill code-review"
    - "🔴/🟡/🟢 标记"
    - "按 4 个维度审查"
  pass: true

- id: 2
  user_message: "这个 PR 你看看"
  should_trigger: true
  expected_output:
    - "using skill code-review"
  pass: true

- id: 3
  user_message: "什么是 TypeScript?"
  should_trigger: false

- id: 4
  user_message: "改一下 README.md 里的拼写"
  should_trigger: false

- id: 5
  user_message: "我刚才改的代码有没有问题？"
  should_trigger: true
```

**Golden set 大小**：
- **新 Skill**：至少 20 个用例
- **成熟 Skill**：50-100 个用例
- **关键 Skill**：200+ 用例

## 怎么测触发

**Step 1：人工跑 20 个用例**

启动 Claude Code，对每个 user_message 走一遍：

```text
[打 20 个不同的对话]
- 10 个"应该触发"
- 5 个"边缘"（可能触发）
- 5 个"不该触发"
```

观察 Claude Code 输出，看：

- "using skill X" 出现在哪
- 实际触发 vs 预期触发的差异

**Step 2：记录到 spreadsheet**

**记录示例：** 用例 1 "review 一下" → 触发 → ✅；用例 2 "看看这个 PR" → 触发 → ✅；用例 3 "什么是 TS" → 不触发 → ❌ 误触发；用例 4 "改 README 拼写" → 不触发 → ✅；用例 5 "代码有问题吗" → 触发 → ✅。

**Step 3：算指标**

```
触发准确率 = 实际触发的 "应该触发" / 总 "应该触发"
触发拒绝率 = 正确拒绝 / 总 "不该触发"
```

**如果触发准确率 < 80%**：description 写错，重写

**如果触发拒绝率 < 80%**：description 太宽，加否定词

## 怎么测输出质量

触发后，**输出是否符合预期**？

**Step 1：给每个 "应该触发" 用例写 expected_output**

```yaml
- id: 1
  should_trigger: true
  expected_output:
    contains:
      - "🔴 严重"
      - "🟡 警告"
      - "🟢 建议"
    format: "markdown"
    must_mention_files: true
    must_mention_line_numbers: true
```

**Step 2：自动评估脚本**

写一个脚本，**对每次实际输出做正则/关键词检查**：

```python
def evaluate_output(actual, expected):
    score = 0
    for keyword in expected.contains:
        if keyword in actual:
            score += 1
    return score / len(expected.contains)
```

**Step 3：算分**

```
输出质量 = 得分 ≥ 0.8 的次数 / 总触发次数
```

**低于 80%**：body 写错，**重写模板**或**加清单**。

## 评估的 3 个层级

**Level 1：触发测试**（基础）

只测"该不该触发"。**10 分钟搞定**。

```text
对每个用例：
- 启动对话
- 观察是否触发
- 记录 ✓/✗
```

**Level 2：触发 + 输出结构**（中等）

测触发 + 输出是否含预期关键词。**30 分钟**。

```text
对每个"应该触发"用例：
- 跑对话
- 看输出含哪些关键词
- 算包含率
```

**Level 3：触发 + 输出 + 人类评估**（高级）

测触发 + 输出 + 人类打分（1-5 分）。**1-2 小时**。

```text
对每个用例：
- 跑对话
- 3 个人独立打分
- 取平均分
```

**我自己 2026 年标准**：**新 Skill 跑 Level 1+2，老 Skill 季度跑 Level 3**。

## 写 golden set 的 5 个技巧

**1. 包含"边缘 case"**。

不只是"明显该触发"和"明显不该触发"——**包含模糊的 case**：

- "看看这个" — 不清楚是 code review 还是 debug
- "改一下这个" — 不清楚是不是 refactor
- "这个怎么用" — 可能是 tutorial

**2. 包含"用户可能犯的错"**。

- 拼写错误："review 一下"（写成"reivew"）
- 缩写："CR"（code review 的缩写）
- 同义词："看看"、"检查"、"审视"

**3. 包含 paths 边界的 case**。

- 改 src/ 下的 .ts → 应该触发
- 改 README.md → 不应该触发
- 改 tests/ 下的代码 → 是否触发（看 paths 配置）

**4. 包含"已经被其他 Skill 处理"的情况**。

```text
场景：用户问"代码 review"
预期：code-review 触发（不是 frontend-design）
```

**5. 包含真实项目里出现过的对话**。

不是凭空想象测试用例——**翻你项目的 git log**，看实际对话里有哪些触发过哪些 Skill。**这些才是最有价值的 case**。

## 评估的 3 个常见错误

**错 1：只看平均分，忽略分布**。

```text
整体质量 80% —— 看起来 OK
但 5 个用例里 1 个 0 分（严重错）+ 4 个 100 分
```

**这个 Skill 不可用**——**5% 的对话会大错**。**要看分布**。

**错 2：测试用例太理想**。

```text
"用户消息：'请审查这段代码'" —— 100% 触发
```

**真实对话是**："看看这个"，"CR 一下"，"我刚改的代码有没有 bug"。

**测试用例要"贴近真实"**。

**错 3：只测一次**。

LLM 输出有随机性。**同一个用例跑 3 次**：

- 3/3 一致 → 稳定
- 2/3 一致 → 不稳定，重测
- 1/3 一致 → 不稳定，看 description

## 我自己的评估节奏

**新 Skill 发布**：
- 写 20 个 golden case
- Level 1 + Level 2 测一遍
- 触发准确率 ≥ 80% + 拒绝率 ≥ 85% 才发

**已发布 Skill 季度评估**：
- 加 10 个新 case（从真实对话提取）
- Level 3 跑 1 轮
- 平均分 < 3.5/5 的重写

**Skill 大改后**：
- 全套 golden case 重跑
- 触发准确率 / 拒绝率不变 + 输出质量提升 = 改成功
- 触发准确率 / 拒绝率下降 = 回滚

## 评估的 4 个真实例子

我自己 2026 年评估 8 个 Skill 的真实数字：

| Skill | 触发准确 | 拒绝准确 | 输出质量 | 评估 |
|---|---|---|---|---|
| code-review | 92% | 88% | 85% | 优秀 |
| frontend-design | 95% | 92% | 90% | 优秀 |
| test-coverage | 85% | 80% | 75% | 需调 |
| db-migration | 90% | 95% | 88% | 优秀 |
| git-commit | 88% | 85% | 80% | 良好 |
| api-doc-gen | 78% | 90% | 82% | 需改 description |
| error-handling | 82% | 75% | 78% | 需调 |
| i18n-check | 95% | 92% | 88% | 优秀 |

**2 个需改**（test-coverage / error-handling）的具体动作：
- test-coverage：description 加 "单元测试 / 补测试" 关键词
- error-handling：description 加 "异常处理" 关键词

**改完再测**：test-coverage 触发 95% / 拒绝 88% / 输出 82%；error-handling 触发 90% / 拒绝 85% / 输出 85%。**改进 8-15pp**。**这就是"用数据改 Skill"的价值**。

## 3 个"失败"案例

我 2026 年初写的 3 个失败的 Skill：

**失败 1：refactor-helper**

```yaml
name: refactor-helper
description: 重构代码
```

**问题**：description 太宽 + 重构任务不标准化。**触发准确 30%，输出质量 50%**。

**教训**：**任务太开放 → 不适合 Skill**。**删了**。

**失败 2：debug-helper**

```yaml
name: debug-helper
description: debug 错误
```

**问题**：debug 任务太不可预测。**有时是性能问题，有时是逻辑错误，有时是环境问题**。**Skill 装上反而误导**。

**教训**：**任务差异大 → 不适合 Skill**。**用 prompt 临时聊**。

**失败 3：auto-test-fixer**

```yaml
name: auto-test-fixer
description: 修失败的测试
```

**问题**：触发后 Claude 倾向"改测试让它通过"而不是"修代码让它通过"。**逻辑反了**。

**教训**：**Skill 必须明确定义"做什么 / 不做什么"，否则模型会按自己的偏好**。

**3 个失败都删了**。**失败比成功更值得记录**。

## Golden Set 维护

**黄金法则**：**golden set 至少每 3 个月更新一次**。

**更新源**：
- 真实对话里 Skill 误触发的 case → 加到 golden set
- 真实对话里 Skill 该触发没触发的 case → 加到 golden set
- 真实对话里 Skill 触发后输出错的 case → 加到 golden set

**我自己的节奏**：
- 每月 review 真实对话
- 季度跑全套 golden set
- 半年做一次大改

下一章讲 Skills 的 token 成本优化——**Skills 多了会撑爆 context 吗？怎么优化？**
