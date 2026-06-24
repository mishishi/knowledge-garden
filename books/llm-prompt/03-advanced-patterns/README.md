# 高级模式

> Chain-of-Thought / ReAct / Self-Consistency——这些模式让 LLM 的能力跃升一个台阶。

## Chain-of-Thought（思维链）

让 LLM "一步一步思考"，比直接给答案更准。

```
差 Prompt: "9.11 和 9.9 哪个大？"
好 Prompt: "9.11 和 9.9 哪个大？请一步步推理。"
→ LLM 会输出：9.11 = 9.11，9.9 = 9.90，所以 9.9 大
```

## ReAct

Reasoning + Acting。让 LLM 在思考和行动之间循环。

```
思考：我需要查今天东京的天气
行动：调用 get_weather("Tokyo")
观察：22°C，晴
思考：我可以给出穿衣建议了
行动：调用 recommend_clothing(temp=22)
...
```

## Self-Consistency

同一个问题问多次，取多数答案。

```
问 3 次 "9.11 和 9.9 哪个大？"
→ 3 次答案投票
→ 通常更准确
```

## 下篇

更多高级模式（ToT / Reflexion / Auto-CoT）会在 [Multi-Agent in Practice](../../multi-agent/) 系列里展开。