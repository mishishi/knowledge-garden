# 04. Tools 与 MCP：给 agent 接手和脚

> LLM 自己只能生成文字，干不了实事。Tool 是 Agent 的「手和脚」——查数据库、调 API、读文件、发邮件都靠它。这章分三层讲：内置工具怎么选、自定义 Tool 怎么写、MCP server 怎么接。

## Tool 来源的 3 个 Level

CrewAI 里 Agent 能用三类「外部能力」：

**Level 1：内置工具**（crewai-tools 包）—— SerperDevTool / WebsiteSearchTool / FirecrawlTool / FileReadTool / RagTool 等 40+ 官方工具。

**Level 2：自定义 Tool**（你自己写的 Python 函数）—— `@tool("Tool Name")` 装饰器或 `BaseTool` 子类。

**Level 3：MCP server**（Model Context Protocol 标准协议）—— 本地 stdio server / 远程 HTTP server / SSE 流式 server。

新手从 Level 1 开始，需要定制再 Level 2，多工具联邦再 Level 3。我自己的项目 80% 用 Level 1 + 20% 用 Level 2 自定义——Level 3 MCP 主要在 Claude Desktop 集成时用。

## Level 1：内置工具选型

crewai-tools 包里 40+ 官方工具按场景分：

搜索类：SerperDevTool（Google 搜索，要 SERPER_API_KEY）、WebsiteSearchTool（站内搜索）、FirecrawlTool（抓整页内容，包括 JS 渲染后的）。我自己用得最多的是 FirecrawlTool——传统 scraper 抓不到 JS 渲染内容，Firecrawl 用 headless browser 抓，AI 摘要后再返回，省 token。

文件类：FileReadTool（读文件）、DirectoryReadTool（列目录）、DirectorySearchTool（在目录里搜）。注意 FileReadTool 默认不限制文件大小——我自己 wrap 过加了 5MB 上限。

RAG 类：RagTool（基于 ChromaDB 的 RAG）、CSVSearchTool（CSV 语义搜索）、PDFSearchTool（PDF 内容搜索）、DOCXSearchTool、JSONSearchTool、XMLSearchTool。RagTool v1.14 支持自定义 embedding model 和向量库（之前只能 ChromaDB）。

数据库类：PgSearchTool（PostgreSQL 全文搜索）、MySQLSearchTool。SQL 注入风险——必须配 read-only user。

Web 类：ScrapeWebsiteTool（HTTP scraper）、SeleniumScrapingTool（浏览器自动化）。前者快但抓不到 JS，后者慢但完整。

其他：DallETool（图像生成）、CodeInterpreterTool（跑 Python）、JSONSearchTool。

我自己的项目里 80% 的需求被 crewai-tools 包覆盖了。剩下 20% 写自定义 Tool——下面讲怎么写。

## Level 2：自定义 Tool

两种方式：装饰器（简单）和子类（复杂）。

**装饰器方式**——最简单：

```python
from crewai.tools import tool

@tool("Get Weather")
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    import requests
    response = requests.get(f"https://api.weather.com/{city}")
    return response.json()["temperature"]
```

注意 docstring 必须写清楚——LLM 读 docstring 决定什么时候调这个 tool。docstring 模糊 LLM 就乱调。

**子类方式**——更复杂（多参数、复杂 schema、retry 逻辑）：

```python
from crewai.tools import BaseTool
from pydantic import Field
from typing import Type

class DatabaseQueryTool(BaseTool):
    name: str = "Database Query"
    description: str = "Execute a read-only SQL query against the user database."
    
    args_schema: Type[BaseModel] = QueryInput  # Pydantic schema
    
    def _run(self, query: str, limit: int = 100) -> str:
        # 必须 read-only，防 SQL injection
        if any(kw in query.upper() for kw in ["INSERT", "UPDATE", "DELETE", "DROP"]):
            return "Error: only SELECT queries allowed"
        # 必须 LIMIT，防全表扫
        if "LIMIT" not in query.upper():
            query += f" LIMIT {limit}"
        # 执行
        result = db.execute(query)
        return result.to_json()
```

子类方式比装饰器方式强在：
- 可以加参数校验（Pydantic schema）
- 可以加运行时检查（防 SQL injection / 限速 / sandbox）
- 可以维护内部状态（连接池 / cache）
- 可以做 retry / fallback / timeout

我自己所有涉及外部副作用的 Tool（写数据库 / 调外部 API / 改文件）都用子类方式。只读 + 简单的工具（查天气 / 读文件）才用装饰器。

## Tool 调用的失败模式

我自己的 Tool 上线后最常见的 3 种失败：

**失败 1：Tool 超时**——外部 API 不响应。修：每个 Tool 必须有 timeout（默认 30 秒）+ retry（最多 3 次指数退避）。

**失败 2：Tool 返回格式不一致**——比如天气 API 有时返回 `{"temp": 22}`、有时返回 `{"temperature": 22, "humidity": 45}`。LLM 解析失败。修：Tool 内部做 schema normalize，输出统一格式。

**失败 3：Tool 被滥用**——LLM 用 `read_file` 读 `/etc/passwd`、用 `bash` 调 `rm -rf`。修：每个 Tool 加 permission check（参考 [Harness Engineering 05](../harness-engineering/05-permissions-sandbox/) 那章的 sandbox 设计）。

## Level 3：MCP server

MCP（Model Context Protocol）是 Anthropic 2024 年推的标准协议——让 agent 通过统一接口连多个 tool 来源。一个 MCP server 可以暴露一组 tool，任何兼容 MCP 的 client（Claude Desktop / Cursor / CrewAI）都能用。

```python
from crewai import Agent
from crewai_tools import MCPTool

# 接本地 stdio MCP server
mcp_tool = MCPTool(
    command="python",
    args=["my_mcp_server.py"],
    transport="stdio",  # 或 "http" / "sse"
)

agent = Agent(
    role="数据分析师",
    goal="查询数据库",
    backstory="...",
    tools=[mcp_tool],
)
```

我自己的项目用 MCP 主要场景：
- 多个 agent 共享同一组 tool（写一次 MCP server，多个 agent 都能用）
- 第三方提供的 tool（不写 Python 直接接 Anthropic / Cursor / 其他 vendor 的 MCP server）
- Tool 需要独立进程跑（隔离失败，restart 不影响 agent）

## 自定义 Tool vs MCP server 何时选

| 维度 | 自定义 Tool | MCP server |
|---|---|---|
| 开发成本 | 低（一个 Python 函数）| 中（要写 server + protocol） |
| 部署 | 跟 agent 同进程 | 独立进程 / 独立部署 |
| 多 agent 共享 | 每个 agent 重复 import | 一次部署多 agent 用 |
| 失败隔离 | agent 挂 Tool 也挂 | Tool 挂 agent 还能跑 |
| 适用 | 单 agent 简单 tool | 多 agent 复杂 tool 联邦 |

我自己的决策：
- 1 个 agent + 1-2 个 tool → 自定义 Tool
- 多个 agent + 共享 tool 集 → MCP server
- Tool 需要重 / 长任务（爬虫 / 视频处理）→ MCP server（独立进程跑）

## Tool 的设计原则

我自己的 6 条原则（参考 [Harness Engineering 03](../harness-engineering/03-tool-design/) 那章的细节）：

1. **description 是 prompt 的一部分**——不是文档，要写「什么时候用」「什么时候不用」「举例」。
2. **schema 是约束不是建议**——用 enum / pattern / required 严格限制参数。
3. **错误信息帮 LLM 自纠**——不说"出错了"，说"出错了，你应该 X"。
4. **返回结果结构化且短**——LLM 处理 200 字 JSON 比 2000 字 prose 稳。
5. **Tool 之间正交**——不要"全家桶" tool，LLM 不知道选哪个。
6. **permission check 必须有**——危险操作（写 / 删 / 调外部）必须有 confirmation。

## 上 production 前 checklist

- 每个 Tool 有 timeout（默认 30 秒）
- 每个 Tool 有 retry（指数退避 + max 3 次）
- 危险 Tool 有 permission check + HITL 确认
- Tool description 写清「什么时候用 / 不用 / 举例」
- Tool 参数 schema 用 enum / pattern 严格限制
- Tool 输出结构化 + 截断到合理长度
- 失败有 fallback（返回简化版或"不知道"）
- Tool 数量控制在 ≤ 10（多了 LLM 选错率涨）

[05. Memory + Knowledge](../05-memory-and-knowledge/) 讲 v1.14 的两层记忆系统——Memory（短期 / 长期 / 实体）和 Knowledge（文件型知识源）的区别。
