# Prompt 基础

> Prompt Engineering 是和 LLM 协作的第一课。

## 什么是 Prompt？

Prompt 是你给 LLM 的指令。一个好的 Prompt = 清晰的目标 + 足够的上下文 + 期望的输出格式。

```
差 Prompt: "写一篇文章"
好 Prompt: "用 200 字介绍 Multi-Agent 系统，包含 3 个核心概念，面向技术读者"
```

## 三要素

**1. 角色**：告诉 LLM 它是谁

```
你是一位资深 Python 工程师，正在 Code Review 一个 PR。
```

**2. 上下文**：告诉 LLM 必要的信息

```
这个 PR 修改了用户登录函数，使用了 SQL 拼接。
```

**3. 任务**：告诉 LLM 要做什么

```
找出 3 个安全问题，并给出修复建议。
```

## 下篇

[02. Few-shot 与示例](../02-few-shot/)