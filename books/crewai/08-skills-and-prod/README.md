# 08. Skills 与生产化基础

> v1.14 引入的 Skills 系统是这版最大亮点之一——把领域知识（写代码规范、特定业务流程、领域术语表）打包成「skill package」，像装 npm 包一样注入到 Agent prompt 里。再加生产化基础：observability、testing、deployment、cost control。

## Skills：filesystem-based 技能包

### 跟 Tools / Knowledge 的关系

新人最常问的：「Skills / Tools / Knowledge 到底什么区别？」一句话：

| 类型 | 给 Agent 什么 | 怎么用 |
|------|--------------|--------|
| **Tools** | 调用的函数（actions） | Agent 自己决定调不调 |
| **Knowledge** | 静态参考资料（facts） | RAG 检索后塞进 prompt |
| **Skills** | 流程方法论（how to think） | 整个 SKILL.md 注入 prompt |

**Skills 改 Agent 怎么想，Tools 让 Agent 能做什么，Knowledge 给 Agent 知识。**

### Skills 的目录结构

```
my_project/
├── skills/
│   ├── code-review/
│   │   ├── SKILL.md              # 必填：frontmatter + 内容
│   │   ├── references/
│   │   │   └── style-guide.md    # 选填：参考文档
│   │   └── scripts/
│   │       └── lint.sh           # 选填：可执行脚本
│   ├── pr-writing/
│   │   └── SKILL.md
│   └── data-analysis/
│       └── SKILL.md
```

`SKILL.md` 是核心。目录名必须跟 `name` 字段一致。

### SKILL.md 格式

```markdown
---
name: code-review                  # 必填：1-64 字符，跟目录名一致
description: 代码审查规范，专注于安全和性能问题。  # 必填：1-1024 字符
license: Apache-2.0                # 选填
compatibility: crewai>=1.14.0     # 选填：环境要求
metadata:                          # 选填
  author: your-team
  version: "1.0"
---

## 代码审查 Checklist

审查代码时按这个清单走：

1. **安全**：检查注入漏洞、认证绕过、数据泄露
2. **性能**：查 N+1 查询、不必要的内存分配、阻塞调用
3. **可读性**：命名清晰、注释合理、风格一致
4. **测试**：新增功能有测试覆盖

### 严重程度分级
- **Critical**：安全漏洞、数据丢失 → 阻断合并
- **Major**：性能问题、逻辑错误 → 要求修改
- **Minor**：风格问题、命名建议 → 建议但不阻断
```

`name` 跟目录名严格一致。`description` 决定 LLM 什么时候 activate 这个 skill。

### 挂到 Agent

```python
from crewai import Agent
from crewai_tools import GithubSearchTool, FileReadTool


reviewer = Agent(
    role="高级代码审查员",
    goal="审查 PR 质量和安全性",
    backstory="资深工程师，擅长安全编码实践。",
    skills=["./skills"],                       # ← 注入 skills 目录
    tools=[GithubSearchTool(), FileReadTool()], # ← 跟 tools 并存
)
```

Agent 现在既有「方法论」（skill 注入的 prompt），又有「能力」（tools 可调用）。

### 5 个常见 Skills 模式

**模式 1：只 Skills（只给方法论，不需要动作）**

```python
writer = Agent(
    role="技术写作员",
    goal="写清晰的 API 文档",
    backstory="...",
    skills=["./skills/api-docs-style"],
    # 没有 tools — Agent 纯写
)
```

**模式 2：只 Tools（只给动作，不需要特殊方法论）**

```python
researcher = Agent(
    role="网络研究员",
    goal="找信息",
    backstory="...",
    tools=[SerperDevTool()],
    # 没有 skills — 通用研究不需要特殊规范
)
```

**模式 3：Skills + Tools（最常见）**

```python
analyst = Agent(
    role="安全分析师",
    goal="审查基础设施",
    backstory="...",
    skills=["./skills/security-audit"],   # 审计方法论
    tools=[SerperDevTool(), FileReadTool()],  # 调研能力
)
```

**模式 4：Skills + MCPs**

```python
agent = Agent(
    role="数据分析师",
    skills=["./skills/data-analysis"],
    mcps=["https://data-warehouse.example.com/sse"],  # MCP 远程
)
```

**模式 5：Crew-level Skills（所有 Agent 共享）**

```python
crew = Crew(
    agents=[researcher, writer, reviewer],
    tasks=[...],
    skills=["./skills"],   # ← 全 crew 共享
)
```

Agent-level 优先于 Crew-level。如果同名 skill 同时在 Agent 和 Crew 配，Agent 那个生效。

### 官方 Skills 注册（npx skills add）

CrewAI 官方维护了一批 Skills，可以一行命令装到 Claude Code / Cursor / Codex：

```bash
npx skills add crewaiinc/skills
```

这会把 Skills 装到你的 `~/.claude/skills/` 或 `~/.cursor/skills/`，CLI coding agent 自动用。

适合：让 Claude Code / Cursor 写 CrewAI 项目时自带 CrewAI 知识。

### 编程方式加载 Skills

如果你要更精细控制：

```python
from pathlib import Path
from crewai.skills import discover_skills, activate_skill


# 1. 发现
skills = discover_skills(Path("./skills"))

# 2. 激活（加载 SKILL.md 全文）
activated = [activate_skill(s) for s in skills]

# 3. 传给 Agent
agent = Agent(
    role="...",
    skills=activated,   # ← 直接传激活后的对象
)
```

适合：在脚本里动态选 skill，不靠路径约定。

### Skills 加载机制（Progressive Disclosure）

Skills 不是一次性全塞 prompt 的：

| 阶段 | 加载什么 | 何时 |
|------|---------|------|
| Discovery | 名字 + description + frontmatter | `discover_skills()` |
| Activation | SKILL.md 完整 body | `activate_skill()` |

正常 Agent 执行时（`skills=["./skills"]`），这两个阶段都自动发生。手动控制才用到 `discover_skills` / `activate_skill`。

### Skills 软警告

`SKILL.md` body 超过 **50,000 字符**会有软警告。没有硬限制，但太大的 skill 注入会稀释 Agent 注意力。

**经验**：单个 skill body 控制在 5,000-10,000 字符。超长内容放 `references/` 目录，让 Skill 主体引用它们。

### Skills 常见坑

**坑 1：`allowed-tools` 字段是 experimental**

```yaml
---
allowed-tools: web-search file-read   # ← 这只是 metadata
---
```

`allowed-tools` 不会自动给 Agent 装这些 tools。**必须自己配 `tools=[...]`**。

**坑 2：目录名跟 `name` 字段不一致**

```
skills/Code-Review/       # 目录名
SKILL.md:
  name: code-review       # 跟目录名不一致
```

启动时 CrewAI 找不到这个 skill。**改目录名或改 name 字段保持一致**。

**坑 3：Skill 太多**

一个 Agent 挂了 10 个 skills。每个 skill 注入 prompt 1-2KB，10 个就是 20KB context。**挑 2-3 个最相关的**。

## 生产化 4 件套

Skills 之外，v1.14 还提供 4 个生产化工具。

### 1. Observability（可观测性）

CrewAI 支持多种 observability 后端：

```python
import os

# Langfuse（开源，自托管友好）
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-xxx"
os.environ["LANGFUSE_SECRET_KEY"] = "sk-xxx"
os.environ["LANGFUSE_HOST"] = "https://cloud.langfuse.com"

# Arize Phoenix
os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = "http://localhost:6006"

# OpenTelemetry（通用）
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4317"
```

启动后所有 `crew.kickoff()` 调用自动 trace。

**推荐**：本地开发用 Arize Phoenix（Docker 一键起），生产用 Langfuse Cloud 或自托管。

### 2. Testing

CrewAI 没有官方 testing framework，但提供 mock LLM：

```python
from crewai.agents.agent_builder.base_agent import BaseAgent


class MockLLM:
    def call(self, messages, **kwargs):
        return "Mock response"

    async def acall(self, messages, **kwargs):
        return "Mock response"


# 在测试里用
agent = Agent(
    role="...",
    llm=MockLLM(),   # ← 替换真 LLM
    tools=[],
)
```

测试不烧 token，跑得快。

**eval harness**（评估输出质量）：

```python
def evaluate_output(actual, expected_criteria):
    """用 LLM 评估另一个 LLM 的输出"""
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"评估以下输出是否满足标准：\n标准: {expected_criteria}\n输出: {actual}\n\n0-1 分：",
        }],
    )
    return float(response.choices[0].message.content)


# 测试时
result = crew.kickoff(inputs={...})
score = evaluate_output(result.raw, "100 字以内中文短文，引用所有事实")
assert score >= 0.8
```

### 3. Deployment

从本地到云端一条命令：

```bash
# 登录
crewai login

# 部署
crewai deploy create

# 查看状态
crewai deploy status

# 看日志
crewai deploy logs

# 更新（改完代码再 deploy）
crewai deploy push
```

第一次部署大概 1 分钟。背后推到 [CrewAI AMP](https://app.crewai.com) 平台。

**前提**：

- 项目在 GitHub 仓库
- 项目有 `pyproject.toml`（`crewai create` 生成的都有）
- 配了 LLM API key 的环境变量

**生产部署架构**：

```
GitHub push
    ↓
CrewAI AMP 检测到新代码
    ↓
跑 crewai deploy push
    ↓
AMP 平台拉镜像、起容器
    ↓
endpoint 提供 API 访问
    ↓
生产流量打到 endpoint
```

### 4. Cost Control

3 个核心成本控制手段：

**Token budget**：

```python
from crewai import Crew

crew = Crew(
    agents=[...],
    tasks=[...],
    token_budget=50_000,   # 单次 kickoff 最多 5 万 token
)
```

超 budget 会强制结束。

**Model routing**：

```python
agent = Agent(
    role="...",
    llm="openai/gpt-4o-mini",   # 用便宜模型
)

# 复杂任务单独配
hard_agent = Agent(
    role="...",
    llm="openai/gpt-4o",   # 强模型
)
```

**Cache**（ch03 讲过）：

```python
agent = Agent(
    role="...",
    cache=True,
)
```

**实际省钱经验**：

- 80% 的子任务用 gpt-4o-mini 跑
- 关键决策（reasoning / final review）才上 gpt-4o
- 缓存打开（cache=True）
- 限 max_iter（防死循环）
- 输出长度加约束（description 里说「100 字以内」）

## 5 个生产化反模式

**反模式 1：本地跑通直接上生产**

本地没考虑：

- 限流（max_rpm）
- 超时（tool timeout）
- 错误重试
- 监控（observability）
- 成本上限（token_budget）

**反模式 2：prompt 写在代码里**

```python
# 错
agent = Agent(
    role="研究员",
    goal="...",
    backstory="...",   # 改个 prompt 要重新部署
)
```

**修复**：用 YAML 配置（ch01 推的写法）。

**反模式 3：所有 Agent 用同一个强模型**

```python
# 错
researcher = Agent(..., llm="gpt-4o")
writer = Agent(..., llm="gpt-4o")
reviewer = Agent(..., llm="gpt-4o")
```

3 个 Agent × gpt-4o = 3 倍成本。研究员和写作员 gpt-4o-mini 够用，reviewer 才上 gpt-4o。

**反模式 4：不用 Skills / Knowledge**

把领域知识硬塞进 prompt 字符串：

```python
agent = Agent(
    backstory="""
    你必须遵守以下规范：
    1. 命名规范：小写+下划线...
    2. 错误处理：必须 try/except...
    3. 测试：覆盖率必须 > 80%...
    ...（100 行规范）"""
)
```

**修复**：用 Skill 把规范放文件系统，prompt 简洁。

**反模式 5：没设 guardrail**

Agent 输出没校验就直接用。生产里要 Pydantic 锁字段 + Guardrail 业务校验（ch06）。

## 这章跑完之后你该会什么

- 区分 Skills / Tools / Knowledge
- 写 SKILL.md，挂在 Agent / Crew 上
- 知道 Skills 5 种常见模式
- 用官方 `npx skills add` 装 Skills
- 配 observability（Langfuse / Phoenix / OTEL）
- 写 eval harness + mock LLM
- 一条命令部署到 CrewAI AMP
- 控制成本（token budget / model routing / cache）
- 避免 5 个生产化反模式

## 下篇

[09. 实战：2 个 Side-Project 串起来](../09-side-projects/) — AI 内容工厂 + PR 代码评审 Multi-Agent，从需求到跑通。
