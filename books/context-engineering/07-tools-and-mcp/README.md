# 07. 工具调用与 MCP

2025 年 11 月我们做一个代码助手 agent。Agent 系统 prompt 里挂了 200 个工具——文件读写、git、docker、数据库、网络、API 调用、测试、部署、监控。

**问题立刻就来了**：
1. 工具定义的 JSON schema 占了 12K token context
2. 模型在 200 个工具里"找"该用哪个，attention 严重分散
3. 准确率从 5 个工具时的 92% 跌到 200 个工具时的 41%
4. 单次调用 token 成本 $0.15

我做的第一件事：**砍到 8 个核心工具**。准确率回到 88%，token 成本降到 $0.03。

**这不是"少就好"，是"对的工具才不污染 context"**。

这一章讲工具调用和 MCP——**工具定义怎么写、怎么暴露、怎么组合**。

## 工具定义的基本结构

工具（Tool / Function）在 LLM 应用里是一个**模型可以调用的函数**。模型不直接执行——它输出"调用哪个工具 + 传什么参数"，应用层执行后把结果喂回给模型。

工具的 schema 包含 3 部分：
- **name**：工具的标识符（snake_case）
- **description**：模型读这段决定"是否调用"
- **parameters**：参数的 JSON Schema（类型、必填、说明）

示例：
```json
{
  "name": "search_orders",
  "description": "查询订单数据库。用 user_id 或 date_range 过滤。最近 90 天的订单。",
  "parameters": {
    "type": "object",
    "properties": {
      "user_id": {"type": "string", "description": "用户 ID, 格式 UUID"},
      "date_range": {"type": "string", "description": "日期范围, 格式 YYYY-MM-DD..YYYY-MM-DD"},
      "status": {"type": "string", "enum": ["pending", "shipped", "delivered", "returned"]}
    },
    "required": ["user_id"]
  }
}
```

**3 个写好工具的规则**：

**1. Description 要"完整且具体"。** 模型读 description 决定是否调用。**"查询订单"不够好，"查询订单数据库，按 user_id 或 date_range 过滤，仅返回最近 90 天"才好。** 模糊的 description 让模型在"该用哪个工具"上做错决策。

**2. Parameters 要"带约束"。** enum / format / min / max 全用上。**模型在生成参数时会参考这些约束**。比如 `"format": "email"` 让模型知道怎么生成合法的 email。

**3. 工具要"原子"。** 一个工具做一件事。**别做"manage_orders"这种万能工具，它能创建/查询/修改/删除订单**。拆成 `create_order` / `get_order` / `update_order` / `delete_order`。

## 工具的"context 污染"问题

工具定义本身占 context。**100 个工具的 JSON 定义大约 5-8K token**。再加上 tool call result 一起算：

- 100 个工具定义：5-8K
- 一次 ReadFile 返回 50K 代码：50K（如果进来）
- 一次 SQLQuery 返回 10K 结果：10K
- 一次 search 召回 20 个 chunk：8K

**工具调用一次可能"挤进"几十 K context**。这导致：
1. Context 接近上限
2. Lost in the Middle 现象加剧
3. 模型开始 "forget" 之前的指令

**3 个解法**：

**解法 1：限制工具数量（"3-8 个任务相关工具"原则）。**

我自己的 2026 年默认：**单 agent 同时暴露的工具数 ≤ 8**。多了就分 agent 或按任务类型动态加载。

**解法 2：限制工具结果大小。**

ReadFile 默认只返回前 100 行，超过的用 `read_file_chunk(path, start, end)`。SQLQuery 默认 LIMIT 100，超过的让模型分页查。

**解法 3：把工具调用结果"压缩"再进 context。**

工具返回 50K token 的代码，先让 LLM 提取关键信息（3-5K token 摘要）再进 context。这跟 Compress 策略一样。

## MCP（Model Context Protocol）

**MCP 是 2024 年 11 月 Anthropic 推出的工具调用统一协议**。在 MCP 之前，每个 LLM 框架有自己的 tool 接口：
- LangChain 有 Tool 类
- OpenAI 有 function calling JSON schema
- Anthropic 有 tool_use 格式
- AutoGen 有 function_map

**同一个"查天气"工具，在不同框架里要写 4 套**。这是工具生态碎片化的核心问题。

MCP 定义了一个标准协议：MCP Server 暴露工具，MCP Client（Claude Desktop / Cursor / Continue.dev / Zed 等）调用工具。**一次编写，到处运行。**

到 2026 年 3 月，MCP 已经：
- 97M 月 SDK 下载
- 10,000+ 公开 MCP Server
- 25,000+ GitHub stars
- 2025 年 12 月捐给 Linux Foundation（中立化）

**所有主流 AI 工具都支持 MCP**。这意味着 2026 年写一个 MCP Server 一次，能被 5+ 个 AI 工具同时用。

## MCP 的架构

```text
[AI 应用 (Claude Desktop / Cursor / IDE 等)]
       ↓
[MCP Client (内置在 AI 应用)]
       ↓ JSON-RPC 2.0
[MCP Server (你的工具服务)]
       ↓
[实际资源 (文件系统, 数据库, API, etc.)]
```

MCP 协议定义 3 类能力：
- **Tools**：模型可以调用的函数（有副作用）
- **Resources**：模型可以读取的数据（只读）
- **Prompts**：预定义的提示模板

**传输方式**：
- **stdio**：通过 stdin/stdout 通信，适合本地工具（启动子进程）
- **SSE / HTTP**：通过 HTTP 长连接通信，适合远程工具服务

## 写一个 MCP Server

最简单的方式是用 Anthropic 官方 SDK 的 `FastMCP`：

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("我的工具服务器")

@mcp.tool()
def search_github(query: str, language: str = None, limit: int = 5) -> str:
    """搜索 GitHub 仓库。query 搜索关键词, language 编程语言过滤, limit 返回数量 (1-10)。"""
    import httpx
    url = "https://api.github.com/search/repositories"
    params = {"q": query, "per_page": min(limit, 10), "sort": "stars"}
    if language:
        params["q"] += f" language:{language}"
    response = httpx.get(url, params=params, headers={"Accept": "application/vnd.github.v3+json"})
    return response.text

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

**关键点**：
- `@mcp.tool()` 装饰器把 Python 函数变成 MCP tool
- Docstring 就是 tool 的 description — **模型读这个决定何时调用**
- 参数类型注解自动变成 JSON schema

## MCP 的"工具分类"

2026 年 MCP Server 的成熟生态覆盖：

- **开发类**：filesystem、git、docker、postgres、sqlite
- **数据类**：database、vector store、S3、kafka
- **业务类**：Salesforce、Slack、Notion、Linear、Jira
- **AI 类**：stable diffusion、whisper、embedding models
- **自定义**：你公司内部的 API、文档、工具

**这意味着 2026 年写 agent 时，80% 的常用工具不用自己实现，直接用现成的 MCP Server**。

## MCP 的 context 影响

MCP 也有 context 污染问题。每个 MCP Server 暴露 5-10 个工具，**10 个 MCP Server = 50-100 个工具同时暴露在 context 里**。

**2026 年的解法**：
- **按需加载 MCP Server**：启动时只加载当前任务相关的 server
- **临时启用 / 临时禁用**：用 `/mcp` 命令动态切换
- **每个 session 只暴露 3-5 个 server**

**MCP 本身不解决 context 污染问题——它只是统一了协议。Context 管理还是要靠应用层的设计。**

## MCP 生态外的备选

不是所有场景都适合 MCP：
- **超低延迟场景**（高频交易、实时音视频）：MCP 的 JSON-RPC overhead 太大，用 gRPC / 直连 RPC
- **企业内部私有协议**：MCP 是公开标准，有些企业已经用自己的 RPC 框架
- **超简单场景**（1-2 个工具）：直接 hardcode 工具定义到 system prompt，不用 MCP

**我的 2026 年判断**：3 个以上工具 + 需要跨 AI 应用复用 → 用 MCP。**否则直接 hardcode 更简单**。

## 实战：客服系统的工具设计

回到那个客服 SaaS。我帮他们设计的 4 个工具：

```python
# 1. 查订单（read-only）
@mcp.tool()
def get_order(order_id: str) -> dict:
    """查询订单详情。order_id 格式为 ORD-XXXXX。返回订单状态、金额、商品、收货地址。"""

# 2. 查用户历史（read-only）
@mcp.tool()
def get_user_history(user_id: str, days: int = 90) -> list:
    """查询用户过去 N 天的工单和订单历史。days 默认 90，最多 365。"""

# 3. 创建工单（write）
@mcp.tool()
def create_ticket(user_id: str, issue_type: str, summary: str, priority: str = "normal") -> str:
    """创建客服工单。issue_type 必须是 'refund' | 'shipping' | 'product' | 'other' 之一。"""

# 4. 发邮件（write）
@mcp.tool()
def send_email(to: str, template: str, vars: dict) -> bool:
    """发送邮件。template 必须是注册的模板之一。vars 是模板变量。"""
```

**每个工具的 description 都写明了"输入什么、返回什么、何时调用"**。模型读这些 description 决定调用。

**所有 4 个工具的 schema 总共 1.2K token**。对比之前 30 个工具 8K token，**工具相关的 context 占用降 85%**。

下一章讲多 Agent context 管理——handoff 时 context 怎么传、消息怎么格式化、错误怎么恢复。
