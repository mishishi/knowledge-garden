# 06. MCP 集成：连接外部工具

2025 年 11 月我让 Claude Code 读 Postgres 数据库。**3 种方案**：

1. **手写 SQL 工具**（每次新数据库要重写）—— **不通用**
2. **REST API 包一层**（要维护 API）—— **累**
3. **MCP Server**（一次配置，所有 AI 工具都能用）—— **正解**

**MCP（Model Context Protocol）是 Claude Code 连接外部工具的标准协议**——**2024 年 11 月 Anthropic 推出，2025 年 12 月捐给 Linux Foundation**。

这一章讲 Claude Code 怎么配 MCP，**以及哪些 MCP Server 2026 年 4 月值得装**。

## MCP 在 Claude Code 里的角色

**MCP Server = Claude Code 的"工具"——连接外部系统**。

```text
Claude Code (MCP Client)
   ↓ JSON-RPC 2.0
MCP Server
   ↓
外部系统（Postgres / GitHub / Slack / Filesystem / ...）
```

**MCP 让 Claude Code 能"操作任何东西"**——**只要有 MCP Server**。

## Claude Code 配置 MCP 的 3 种方式

**方式 1：命令行配置（推荐）**

```bash
# 添加 Postgres MCP server
claude mcp add postgres npx -y @modelcontextprotocol/server-postgres "postgresql://user:pass@localhost/mydb"

# 添加 GitHub MCP server
claude mcp add github npx -y @modelcontextprotocol/server-github

# 添加 filesystem MCP server
claude mcp add filesystem npx -y @modelcontextprotocol/server-filesystem /Users/me/projects
```

**每次启动 Claude Code 自动连接**。

**方式 2：`.mcp.json`（项目级）**

```json
// .mcp.json
{
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {
        "POSTGRES_URL": "postgresql://user:pass@localhost/mydb"
      }
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "ghp_xxxxx"
      }
    }
  }
}
```

**项目级配置，团队共享**。

**方式 3：手动启用（session 内）**

```bash
# 列出所有可用 MCP server
/mcp

# 启用某个
> enable github

# 禁用某个
> disable postgres
```

**session 内动态控制**。

## 8 个"项目级"必备 MCP Server

我 2026 年 4 月项目里常驻 8 个 MCP Server。

**MCP 1：filesystem**

**作用**：让 Claude Code 读 / 写文件系统。

**配置**：

```bash
claude mcp add filesystem npx -y @modelcontextprotocol/server-filesystem /Users/me/projects
```

**典型用法**：

```text
用户：列出 src/api 下所有 .ts 文件
Claude Code 调用 filesystem 工具
返回：["user.ts", "order.ts", "product.ts"]
```

**MCP 2：postgres**

**作用**：让 Claude Code 查 / 改 Postgres 数据库。

**配置**：

```bash
claude mcp add postgres npx -y @modelcontextprotocol/server-postgres "postgresql://user:pass@localhost/mydb"
```

**典型用法**：

```text
用户：查最近 7 天订单里退款率
Claude Code 写 SQL → 跑 → 返回结果
```

**MCP 3：github**

**作用**：让 Claude Code 查 / 改 GitHub（PR / issue / repo）。

**配置**：

```bash
claude mcp add github npx -y @modelcontextprotocol/server-github
```

**典型用法**：

```text
用户：列出我所有 open 的 PR
Claude Code 调 GitHub API
返回：[PR #123, PR #124, ...]
```

**MCP 4：playwright**

**作用**：让 Claude Code 操作浏览器（自动化测试、爬虫）。

**配置**：

```bash
claude mcp add playwright npx -y @modelcontextprotocol/server-playwright
```

**典型用法**：

```text
用户：登录 app 测一下 login 功能
Claude Code：开浏览器 → 填表 → 截图 → 报告
```

**MCP 5：docker**

**作用**：让 Claude Code 管理 Docker 容器。

**配置**：

```bash
claude mcp add docker npx -y @modelcontextprotocol/server-docker
```

**典型用法**：

```text
用户：把当前 branch 跑个容器测试
Claude Code：docker run → 跑测试 → 删容器
```

**MCP 6：fetch（HTTP 请求）**

**作用**：让 Claude Code 发任意 HTTP 请求。

**配置**：

```bash
claude mcp add fetch npx -y @modelcontextprotocol/server-fetch
```

**典型用法**：

```text
用户：调 API 拿数据
Claude Code：fetch → 返回 JSON
```

**MCP 7：redis**

**作用**：让 Claude Code 查 / 改 Redis。

**配置**：

```bash
claude mcp add redis npx -y @modelcontextprotocol/server-redis
```

**典型用法**：

```text
用户：清空所有 session cache
Claude Code：FLUSHDB
```

**MCP 8：sentry**

**作用**：让 Claude Code 查 Sentry 错误。

**配置**：

```bash
claude mcp add sentry npx -y @modelcontextprotocol/server-sentry
```

**典型用法**：

```text
用户：查今天报的错误
Claude Code：列 Sentry issues → 分析 → 修
```

## MCP 的 3 个优势

**1. 一次配置，多端使用**

```text
配 1 个 Postgres MCP Server：
- Claude Code 能用
- Cursor 能用
- Continue.dev 能用
- 所有支持 MCP 的 AI 工具都能用
```

**2. 隔离 Claude Code 和外部系统**

Claude Code 不直接连接外部——**通过 MCP Server 转发**。**MCP Server 可以做权限控制、日志、限流**。

**3. 工具标准化**

不用为每个 AI 工具写一套"工具接口"——**MCP 统一了**。

## MCP 的 3 个坑

**1. 每个 MCP Server 占 token**

```text
1 个 MCP Server = 18,000+ token
5 个 MCP Server = 90,000+ token
10 个 MCP Server = 180,000+ token
```

**挂太多 MCP Server = context 提前满**。

**解法**：用 `/mcp` 动态启停。

**2. MCP Server 自己可能慢**

```text
MCP Server 慢 1 秒 × 每次 5 个工具调用 = 5 秒等待
```

**解法**：本地 cache 常用结果。

**3. MCP 工具权限过大**

```text
filesystem MCP：能读所有 .env
github MCP：能 push 到 main
```

**解法**：MCP Server 自己限制权限——**filesystem 加 allow 列表，github 用 read-only token**。

## 写一个简单的 MCP Server

**Anthropic 官方 Python SDK**：

```python
# my_mcp_server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("我的工具服务器")

@mcp.tool()
def get_user_count() -> int:
    """查询用户总数"""
    # 实际逻辑
    return 42

@mcp.tool()
def search_users(query: str, limit: int = 10) -> list:
    """搜索用户
    
    Args:
        query: 搜索关键词
        limit: 返回数量（1-50）
    
    Returns:
        用户列表，每个含 id, name, email
    """
    # 实际逻辑
    return [...]

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

**配置**：

```json
{
  "mcpServers": {
    "my-server": {
      "command": "python",
      "args": ["my_mcp_server.py"]
    }
  }
}
```

**3 行代码 + 1 个配置 = 1 个 MCP Server**。

## 真实工作流：MCP 帮我做的 5 件事

**1. 改完代码自动跑数据库 migration**

```text
用户：给 orders 表加 refunded_at 字段
Claude Code：
  - postgres MCP：ALTER TABLE orders ADD COLUMN refunded_at TIMESTAMP
  - 写 migration 文件
  - 跑 SQL
  - 验证
```

**2. 查 Sentry 错误并修复**

```text
用户：今天报了什么错
Claude Code：
  - sentry MCP：列 issues
  - 看 top 错误
  - 找代码位置
  - 修 + commit
```

**3. 跑 Docker 测试新分支**

```text
用户：在容器里跑 feature-A 分支的测试
Claude Code：
  - docker MCP：拉镜像
  - 挂载代码
  - 跑测试
  - 报告结果
```

**4. 自动化浏览器测试**

```text
用户：测一下 login 流程
Claude Code：
  - playwright MCP：开浏览器
  - 填表
  - 提交
  - 截图
  - 检查结果
```

**5. 调内部 API**

```text
用户：调 /api/users 看返回
Claude Code：
  - fetch MCP：发请求
  - 解析 JSON
  - 输出
```

## MCP 安全 5 原则

**1. 永远 deny 敏感路径**

```json
"deny": [
  "Read(**/.env*)",
  "Read(**/.ssh/**)"
]
```

**2. MCP token 用最小权限**

```json
"env": {
  "GITHUB_TOKEN": "ghp_xxxxx"  // 只给 read 权限
}
```

**3. 隔离 MCP server**

每个 MCP Server 跑独立进程，**不要复用 Python 进程**。

**4. 监控 MCP 调用**

记日志——**哪个 MCP 调用了、什么时候、调了什么**。

**5. 季度 review**

每 3 个月看一次 MCP 配置——**移除用不到的 server，升级过时的**。

## MCP + Skills + CLAUDE.md 的协同

```text
CLAUDE.md：项目级规则（始终加载）
   ↓
Skills：工作流（按需加载）
   ↓
MCP：外部工具（按需连接）
```

**3 个机制各司其职**：
- **CLAUDE.md** = 团队宪法
- **Skills** = 标准 SOP
- **MCP** = 工具集

**配合使用**：
- CLAUDE.md 写"用 Postgres MCP 查用户"
- Skills 触发时自动用 MCP
- MCP 工具结果进 context 后 Skill 处理

## 实战：MCP + Skill 自动化

**场景**：每次 PR 自动跑数据库 migration 测试。

**Skill: pr-migration-test**

```yaml
---
name: pr-migration-test
description: PR 提交流程中跑 migration 测试
paths: ["migrations/**"]
---

# PR Migration Test
1. 启动 Postgres MCP（如果未连接）
2. 用 MCP 跑当前 migration
3. rollback
4. 再跑一次
5. 报告是否一致
```

**配置**：

```json
// .mcp.json
{
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {
        "POSTGRES_URL": "postgresql://..."
      }
    }
  }
}
```

**工作流**：

```text
用户：push PR
   ↓
GitHub Actions 触发 Claude Code
   ↓
Claude Code 加载 pr-migration-test Skill
   ↓
Skill 触发 postgres MCP
   ↓
MCP 跑 migration 测试
   ↓
Skill 输出 PASS/FAIL
   ↓
GitHub Actions 根据结果 merge
```

**0 手动**。

## MCP 的"伪 8 大用途"分类

**1. 文件系统**：filesystem
**2. 数据库**：postgres / mysql / sqlite / mongodb / redis
**3. 版本控制**：github / gitlab
**4. 部署运维**：docker / kubernetes / terraform
**5. 监控日志**：sentry / datadog / grafana
**6. 通信**：slack / discord / email
**7. 测试自动化**：playwright / selenium
**8. 内部 API**：fetch / 任何自定义 MCP

**8 类覆盖 95% 场景**。

## 我自己 2026 年 4 月的 MCP 配置

```json
// .mcp.json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/projects"]
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {
        "POSTGRES_URL": "postgresql://..."
      }
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "ghp_xxxxx"
      }
    },
    "playwright": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-playwright"]
    },
    "sentry": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sentry"],
      "env": {
        "SENTRY_TOKEN": "sntrys_xxxxx"
      }
    }
  }
}
```

**5 个 MCP Server**（在 5-8 个的推荐范围内）。

## MCP 调试技巧

**MCP Server 连不上**：

1. 跑 `claude mcp list` 看哪些 server 加载了
2. 检查 `command` 路径（绝对路径）
3. 检查 `env` 变量（token 是否正确）
4. 单独跑 `npx @modelcontextprotocol/server-postgres` 看是否启动

**MCP 工具不响应**：

1. 检查 MCP Server 进程是否在跑（`ps aux | grep mcp`）
2. 减少同时启用的 server 数量
3. 重启 Claude Code

**MCP 工具"答非所问"**：

1. MCP Server 描述不够清晰——**改 MCP Server 的 tool description**
2. 上下文混乱——**重启 Claude Code**
3. 模型没识别——**手动 mention MCP 工具名**

## 3 个常见错误

**错 1：装太多 MCP Server**

```text
# 错
10 个 MCP Server 一直挂着
# 18K × 10 = 180K token 浪费
```

**改**：**5-8 个常驻**。**用 `/mcp` 临时启用**。

**错 2：MCP Server 用 root token**

```text
# 错
github MCP 用 admin token
# Claude Code 可能 push 到 main
```

**改**：**最小权限 token**。**给 filesystem 加 allow 列表**。

**错 3：MCP Server 自己写得不规范**

```text
# 错
MCP Server 描述模糊
# 模型不知道何时用
```

**改**：**MCP Server description 像 Skill 一样写**——**说清"做什么 + 何时用"**。

下一章讲 slash commands——**自定义 Claude Code 命令**。
