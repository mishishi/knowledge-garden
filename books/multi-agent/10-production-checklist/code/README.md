# 第 10 章代码

## 文件结构

```
code/
├── 01_prompt_injection_guard.py    # 坑 1: Prompt 注入防护
├── 02_tool_authorization.py        # 坑 2: 工具权限控制
├── 10_eval_harness.py              # 坑 10: 评估函数 + Mock LLM
├── 11_prompt_versioning.py         # 坑 11: Prompt 版本管理
└── 12_cost_attribution.py          # 坑 12: 成本归因
```

## 12 个坑的完整列表（每个坑在 README 详细讲）

```
安全
├─ 01: Prompt 注入防护 ✓
├─ 02: 工具越权 ✓
└─ 03: 密钥泄露

稳定性
├─ 04: Token 失控
├─ 05: 超时雪崩
└─ 06: 级联失败

可观测性
├─ 07: 黑盒执行
├─ 08: 不可复现
└─ 09: Token 黑洞

工程化
├─ 10: 测试缺失 ✓
├─ 11: 版本管理 ✓
└─ 12: 成本归因 ✓
```

## 依赖

```bash
pip install openai
```

## 运行

```bash
# 不需要 API key
python 01_prompt_injection_guard.py
python 02_tool_authorization.py
python 11_prompt_versioning.py
python 12_cost_attribution.py

# 需要 API key
python 10_eval_harness.py
```

## 一页纸 Checklist

```
□ 1. 输入消毒（防 prompt 注入）
□ 2. 工具白名单 + 鉴权（防越权）
□ 3. 密钥只从环境变量读（防泄露）
□ 4. Token 预算 + watchdog（防失控）
□ 5. 工具超时 + Agent timeout（防雪崩）
□ 6. Circuit Breaker（防级联）
□ 7. Trace（每个 Agent 调用）
□ 8. 固定 seed + temperature=0（可复现）
□ 9. Token 成本追踪
□ 10. 评估函数 + Mock LLM（可测试）
□ 11. Prompt 版本管理
□ 12. 成本归因到用户 / 功能
```