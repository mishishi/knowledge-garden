# 第 2 章代码

## 运行

每个脚本支持场景参数：

```bash
# 场景 1：上下文爆炸
python single_agent_problems.py 1
python multi_agent_solutions.py 1

# 场景 2：角色冲突
python single_agent_problems.py 2
python multi_agent_solutions.py 2

# 场景 3：调试地狱
python single_agent_problems.py 3
python multi_agent_solutions.py 3
```

## 预期输出

跑 `multi_agent_solutions.py 2` 你会看到 CrewAI 的 verbose 输出：

```
[研究员开始] 调研 3 个 Python Web 框架
[研究员输出] FastAPI: 1. 异步原生 2. 类型注解 3. 性能最强
             Django: 1. 全功能 2. 企业首选 3. ORM 强大
             Flask: 1. 简单易学 2. 灵活 3. 生态成熟
[写作员开始] 基于事实写推荐文
[写作员输出] 在 2026 年的 Python Web 框架生态中...
```

verbose=True 让你能 step into 每个 Agent 的中间输出，便于调试。

## 依赖

同 [第 1 章 requirements.txt](../01-your-first-agent/code/requirements.txt)：
- `openai>=1.50.0`
- `crewai>=0.80.0`