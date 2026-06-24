# 06. 结构化输出与 Guardrail

> 写中。先看 ch01-05。

LLM 输出字符串不靠谱——想拿到结构化 JSON、想保证输出符合业务规则、想在违规时拦截——靠 Pydantic 模型 + Guardrail。

## 大致会覆盖

- **`output_pydantic`**：把 Task 输出锁定为 Pydantic 模型，自动校验、自动重试
- **`output_json`**：松一点，只要求 JSON 格式不锁 schema
- **嵌套模型**：list of items、optional 字段、enum
- **Guardrail**：在 Task 输出后跑验证函数，失败就重试或报错
- **业务校验**：URL 必须能 ping 通、金额必须 > 0、JSON 字段必须非空
- **生产经验**：模型不听话时怎么 prompt 比 schema 强

## 下篇

[07. Flows：状态化的事件驱动编排](../07-flows/) — Crew 适合「一组人干一件事」，Flow 适合「流水线有状态」。v1.14 官方推荐生产用 Flow 包 Crew。
