# 第 1 章代码

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置 API Key

本教程默认使用 OpenAI 接口。任何 OpenAI-compatible 的服务都能用（DeepSeek / 通义千问 / 自部署 vLLM / Ollama 等），只需额外设置 `OPENAI_BASE_URL`。

### 方式 A：OpenAI 官方

```bash
export OPENAI_API_KEY=sk-xxx
```

### 方式 B：DeepSeek（便宜，国内直连）

```bash
export OPENAI_API_KEY=sk-xxx
export OPENAI_BASE_URL=https://api.deepseek.com/v1
```

修改 `single_agent.py` 里的 `model="gpt-4o-mini"` 为 `model="deepseek-chat"`。

### 方式 C：本地 Ollama（完全免费）

```bash
# 1. 启动 Ollama 服务
ollama serve

# 2. 拉一个模型
ollama pull llama3.1

# 3. 设置环境变量
export OPENAI_API_KEY=ollama  # Ollama 不校验 key，但 OpenAI SDK 要求非空
export OPENAI_BASE_URL=http://localhost:11434/v1
```

## 运行

```bash
# 单 Agent 示例
python single_agent.py

# Multi-Agent 示例（CrewAI）
python multi_agent.py
```

## 预期输出

### single_agent.py

```
============================================================
[用户] 东京今天天气怎么样？

[第 1 轮] Agent 决定调 1 个工具
  → 调用 get_weather({'city': 'Tokyo'})
  ← 返回: 东京: 22°C, 晴, 湿度 60%, 风速 3m/s

[Agent 回答] 东京今天 22°C，晴朗，湿度 60%，风速 3m/s，适合出门活动。
```

### multi_agent.py

你应该看到 CrewAI 打印的两个 Agent 的执行过程，最后输出一段 100 字以内的中文短文。

## 故障排查

| 报错 | 原因 | 解决 |
|------|------|------|
| `openai.AuthenticationError` | API key 错误或没设置 | 检查 `echo $OPENAI_API_KEY` |
| `ModuleNotFoundError: No module named 'crewai'` | 没装 crewai | `pip install -r requirements.txt` |
| `RateLimitError` | 触发了 API 速率限制 | 等几秒再跑，或换模型 |
| `single_agent.py` 跑了 5 轮还没结束 | prompt 或工具定义有问题 | 检查 `tools` 描述是否清晰 |
| `multi_agent.py` 卡在某个 Agent | CrewAI 版本差异 | `pip install --upgrade crewai` |