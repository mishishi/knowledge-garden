# 14. Codex vs Claude Code vs Cursor：三种哲学 + 组合策略

国外独立开发者 2026 年的真实状态：**不再问"哪个最好"，而是"我该怎么组合"**。这一章讲清楚三种工具的根本差异、场景选择、组合策略。**这是 Codex 实战最关键的一章**——选错工具，再多技巧都没用。

## 三种哲学

### 哲学 1：Cursor = 编辑器即 AI

**产品形态**：基于 VS Code 深度改造的 AI-first IDE。

**核心哲学**：编辑器就是 AI，AI 就是编辑器。

**交互方式**：

- Tab 补全：预测下一行代码
- Cmd+K 内联编辑：选中代码，输入需求，AI 直接改
- Cmd+L 聊天：侧边栏对话

**默认假设**：你的大部分开发时间在 IDE 里。

### 哲学 2：Claude Code = 终端即智能体

**产品形态**：命令行 CLI 工具。

**核心哲学**：终端就是 agent，可嵌入任何工作流。

**交互方式**：

- claude "..."：直接给自然语言
- /review /plan /test：slash commands
- 100% 终端，0% GUI

**默认假设**：你的工作流以终端为中心。

### 哲学 3：Codex = 全平台覆盖

**产品形态**：4 条入口线（CLI / Desktop / VS Code / Web）。

**核心哲学**：在不同场景用不同入口，**统一账号 + 同步 + 多 Agent 协作**。

**交互方式**：

- CLI（终端党）
- Desktop（多 Agent 党）
- VS Code（IDE 党）
- Web（远程异步党）

**默认假设**：开发者是多场景的，**工具要适应人，不是人适应工具**。

## 8 个核心维度对比

### 维度 1：代码库理解能力

| 工具 | 方式 | 大型项目 | 未知项目 |
|------|------|---------|---------|
| Cursor | 扫描整个项目建向量索引 | 强（精准）| 中（@ 文件名引用）|
| Claude Code | 启动时扫描项目，生成 CLAUDE.md | 中（200K 上下文）| 强（自主探索）|
| Codex | 启动时扫描项目，读 AGENTS.md | 中（200K 上下文）| 强（自主探索 + Desktop 多 worktree）|

**胜者**：

- 大型代码库理解：**Cursor 略优**（向量索引精准）
- 自主探索未知代码库：**Claude Code / Codex 明显更强**

### 维度 2：代码生成质量

测试任务：实现"支持断点续传的文件上传服务"。

**Cursor 生成**：

```python
from fastapi import FastAPI, UploadFile
import aiofiles

app = FastAPI()

@app.post("/upload")
async def upload(file: UploadFile):
    # 简单实现：一次写完
    async with aiofiles.open(f"./uploads/{file.filename}", 'wb') as f:
        await f.write(await file.read())
    return {"status": "ok"}
```

**Claude Code / Codex 生成**：

```python
from fastapi import FastAPI, UploadFile, HTTPException
import aiofiles
import hashlib
import os
from pathlib import Path

app = FastAPI()

UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
CHUNK_SIZE = 1024 * 1024  # 1MB

@app.post("/upload/chunked")
async def chunked_upload(
    file: UploadFile,
    chunk_index: int,
    total_chunks: int,
    file_hash: str
):
    """支持断点续传的分块上传"""
    if chunk_index >= total_chunks:
        raise HTTPException(status_code=400, detail="Invalid chunk index")
    
    # 用 hash 分目录，避免单目录文件过多
    target_dir = UPLOAD_DIR / file_hash[:2]
    target_dir.mkdir(exist_ok=True)
    chunk_path = target_dir / f"{file_hash}.part{chunk_index}"
    
    async with aiofiles.open(chunk_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    # 所有分块上传完成
    if chunk_index == total_chunks - 1:
        final_path = UPLOAD_DIR / file_hash
        async with aiofiles.open(final_path, 'wb') as out:
            for i in range(total_chunks):
                chunk = target_dir / f"{file_hash}.part{i}"
                async with aiofiles.open(chunk, 'rb') as f:
                    await out.write(await f.read())
                chunk.unlink()
        return {"status": "complete", "hash": file_hash}
    
    return {"status": "chunk_uploaded", "next": chunk_index + 1}
```

**Cursor 的代码更短但更糙**。**Claude Code / Codex 的代码更长但更工程化**——有错误处理、目录组织、断点续传。

**原因**：Cursor 默认假设你"接下来会自己改"，生成的是**起点**。Claude Code / Codex 默认假设你"需要可直接用的代码"，生成的是**接近完成的方案**。

### 维度 3：多文件修改能力

| 工具 | 能力 | 适用场景 |
|------|------|---------|
| Cursor | 一次改 5-10 个文件 | 中型重构 |
| Claude Code | 200K 上下文，跨文件 | 大型重构 |
| Codex CLI | 200K 上下文 + exec | 大型任务 |
| Codex Desktop | worktree 隔离 + 多 agent | **多 feature 并行** |

**真实场景**：

- 120 个文件的重构任务：
  - Cursor 写 2 小时，只能改 30 个文件，**上下文不够用**
  - Claude Code 一晚上搞定，**200K 上下文优势**
  - Codex Desktop 3 个 worktree 并行，**1 小时搞定**

**胜者**：

- 多文件单次：**Claude Code / Codex CLI**
- 多 feature 并行：**Codex Desktop**

### 维度 4：异步 / 后台执行

| 工具 | 能力 | 适用场景 |
|------|------|---------|
| Cursor | Background Agents（云端）| 中等任务 |
| Claude Code | 需自建（tmux + 后台）| 灵活但 DIY |
| Codex Web | 原生 8 小时长任务 | **开窗扔任务走人**|
| Codex CLI | exec 模式 + cron | 定时任务 |

**实测**：

- Notion 资深工程师：**Codex 跑 8 小时长任务**——Claude Code 至今没原生支持这么长
- Claude Code 优势：**跨会话目标追踪**——可以"明天接着干"

**胜者**：

- 8 小时长任务：**Codex Web**
- 跨会话持续：**Claude Code**

### 维度 5：价格成本

| 工具 | 个人版 | 团队版 | 实测月成本 |
|------|--------|--------|----------|
| Cursor | $20/月 | $40/月 | $20-40 |
| Claude Code | $20-200/月 | API 计费 | **$100-200** |
| Codex | ChatGPT Plus $20 / Pro $200 | 企业 | **$20-200** |
| Codex + Codex++ + DeepSeek | $20 + $15 | - | **$35-50** |

**关键发现**：

- **Claude Code 实测月成本最高**（$100-200）——按 API 用量，**没有固定低价套餐**
- **Codex + Codex++ + DeepSeek 最便宜**（$35-50）——订阅 + 国产 API 混合
- Cursor 中等——$20/月固定，但**功能阉割**（免费版 Agent 能力受限）

**胜者**：**预算敏感 → Codex++ + DeepSeek**。**功能优先 → Codex Pro**。

### 维度 6：上下文与记忆

| 工具 | 短期记忆 | 长期记忆 | 跨会话 |
|------|---------|---------|--------|
| Cursor | @codebase + 200K | 手动 CLAUDE.md 风格 | 需手动 |
| Claude Code | 200K + 自动压缩 | CLAUDE.md + dreaming | 跨会话目标 |
| Codex | 200K + AGENTS.md | AGENTS.md + 持久线程 | persistent threads |

**关键技术差异**：

**Claude Code 的 "dreaming" 机制**（2026 年 5 月）：分析历史会话实现自我优化。**通过离线复盘历史任务来优化未来的输出**。

**Codex 的"持久线程"**（persistent threads）：跨多次会话保留工作上下文。**置顶线程**是把持久线程放在手边的快捷方式。

**胜者**：

- 长期记忆：**Claude Code dreaming**
- 跨会话便利：**Codex 持久线程**

### 维度 7：生态与集成

| 工具 | MCP 支持 | Skill 数量 | IDE 集成 | 第三方工具 |
|------|---------|-----------|---------|----------|
| Cursor | ✅ | 中 | ✅ VS Code | 多 |
| Claude Code | ✅ | 多 | ❌ | 多 |
| Codex | ✅ | 多 | ✅ VS Code + Desktop | 多（OpenCode / OpenClaw）|

**生态上三家差距不大**——MCP 是通用协议，三家都支持。

**差异点**：

- Cursor 依赖 VS Code 插件生态
- Claude Code 跟 AWS Bedrock 集成最紧
- Codex 跟 ChatGPT 账号体系集成最紧

### 维度 8：中文支持

| 工具 | 中文理解 | 中文文档 | 国内访问 |
|------|---------|---------|---------|
| Cursor | 中 | 中 | 部分受限 |
| Claude Code | 强 | 中 | 严重受限（封号）|
| Codex | 中 | 强 | 受限（需 ChatGPT 账号）|
| Codex++ + DeepSeek | 强 | 中 | **完全 OK** |

**关键发现**：

- **Claude Code 对国内用户限制最严**——稳定性差、**容易封号**
- **Codex + Codex++ + DeepSeek 是国内独立开发者的最优解**
- 国内替代：TRAE / Qoder / WorkBuddy / Kimi Work / 豆包（**2026 中国版 Codex 大乱斗**）

## 三种工具的"用户分层"

### 初级 / 简单任务 → Claude Code

Notion 工程师的观察：

> 初级工程师或简单任务更常使用 Claude Code。该工具**擅长预判用户意图，无需过多上下文或细节**，即便用户对任务描述不够精准也能较好执行。

**为什么 Claude Code 适合初级**：

- 需求不精准也能执行
- 自动补全上下文
- "用自然语言说一半，它能猜另一半"

### 资深 / 长任务 → Codex

Notion 资深工程师：

> 资深工程师则更偏爱 Codex，他们认为其**更擅长处理复杂、耗时较长的任务**。例如，Notion 工程师常会设置 Codex 智能体在夜间运行处理任务，有时可连续运行长达 8 小时。

**但有警告**：

> 工程师向 Codex 下达指令时必须严谨精确，**因为它容易误解指令、偏离任务目标**。

**Codex 的特点**：

- 长任务能力强
- 需求必须精准（**不容忍模糊**）
- 资深工程师才能驾驭

### 日常 / IDE 党 → Cursor

- 写新组件 / 改样式 / 跑测试
- 实时补全
- 跟 VS Code 习惯无缝衔接

## 24 项功能对比（Elie Bakouch 调研）

开发者 Elie Bakouch 做了个 24 项核心功能对比，**结论**：

> Claude Code 和 Codex 在 24 项核心功能上展现出**高度趋同**的发展轨迹。从命名规范到多智能体协作机制，两者不仅在功能上高度重叠，甚至在发布节奏上也呈现出你追我赶的局面。

**关键数据**：

- 2026 年 2 月至 6 月，**Claude Code 在 18 项功能上抢先发布**
- Codex 仅在 4 项功能上占据先发优势
- **2 项功能同步**

**Claude Code 抢先**：

- 终端优先战略
- Hooks 机制
- 技能插件
- 跨会话目标追踪

**Codex 抢先**：

- 目标模式（2025 年 8 月）
- 持久线程
- 桌面 App
- 8 小时长任务

## 决策树：怎么选

```
Q1: 你在写什么类型的代码？
├─ 新功能 / UI / 前端 → Cursor（编辑器内最佳）
├─ 大型重构 / 跨文件 → Claude Code 或 Codex CLI
└─ 批量 PR / 异步任务 → Codex Web

Q2: 你要跑多长？
├─ 短（< 30 分钟）→ 任意
├─ 中（30 分钟 - 2 小时）→ Claude Code / Codex CLI
└─ 长（> 2 小时）→ Codex Web（8 小时长任务）

Q3: 你需要并行多任务吗？
├─ 否 → 任意
└─ 是 → Codex Desktop（worktree 隔离）

Q4: 你的预算是多少？
├─ < $30/月 → Codex++ + DeepSeek
├─ $30-100/月 → Codex Pro 或 Cursor
└─ > $100/月 → Codex Pro + Claude Code Max

Q5: 你的网络环境？
├─ 国内 + 稳定 → Codex++ + DeepSeek
├─ 国内 + 翻墙 → Claude Code
└─ 海外 → 任意
```

## 组合策略：3 个真实配方

### 配方 1：个人独立开发者（推荐）

**主力**：Codex CLI（auto-edit 模式）

**配套**：

- 日常小改：Codex VS Code 扩展
- 长任务：Codex Web
- 跨文件重构：Codex CLI
- 多任务并行：Codex Desktop

**省钱**：Codex++ + DeepSeek 跑 review / 简单任务

**预算**：$50-100/月

### 配方 2：前端 / 设计党（推荐）

**主力**：Cursor（IDE 内最佳体验）

**配套**：

- 跨文件重构：Claude Code / Codex CLI
- 设计稿转代码：Codex + Figma MCP
- 视觉验证：Codex + Playwright MCP

**预算**：$50-100/月

### 配方 3：资深 / 长任务为主（推荐）

**主力**：Codex CLI + Codex Web

**配套**：

- 夜间长任务：Codex Web
- 日常写代码：Codex CLI
- 偶尔 IDE：Codex VS Code

**预算**：$50-200/月（Codex Pro $200）

## Notion 工程师的共存策略

**Notion 内部观察**：

- 初级 → Claude Code
- 资深 → Codex
- 共存，**不绑定单一**

**我的理解**：

**不要追求"一个工具搞定所有"**。**这是独立开发者的最高 ROI 策略**。

**具体怎么共存**：

- **任务类型决定工具**，**不是工具决定任务**
- 写新组件 → Cursor
- 跨文件重构 → Claude Code
- 长任务 / 异步 → Codex Web
- 多任务并行 → Codex Desktop
- **任何时候不强制**

## 2026 工具市场变化

**6 月 3 日 OpenAI 发布 Codex 整合 ChatGPT 后**，中国版 Codex 集体上线：

| 时间 | 产品 | 厂商 |
|------|------|------|
| 1 月 30 日 | QoderWork | 阿里 |
| 3 月 9 日 | WorkBuddy | 腾讯云 |
| 5 月 20 日 | Marvis | 腾讯应用宝 |
| 6 月 3 日 | Kimi Work (Beta) | Kimi |
| 6 月 9 日 | TRAE Work | 字节 |
| 6 月 12 日 | 豆包任务模式 | 字节 |
| 6 月 24 日 | 豆包专业版 | 字节 |

**15 款产品集体入场**。**桌面 Agent 战场已经开打**。

**对独立开发者的意义**：

- **海外**：Codex / Claude Code / Cursor 三分天下
- **国内**：TRAE / Qoder / WorkBuddy / Kimi Work 多家可选
- **不要绑死任何一家**——**3-6 个月后赢家未定**

## 我自己的最终组合

**主力**（80% 时间）：

- **写代码**：Codex VS Code 扩展（IDE 内最佳）
- **跨文件重构**：Codex CLI（auto-edit 模式）
- **长任务**：Codex CLI exec + cron
- **多任务**：Codex Desktop（3-5 worktree）

**辅助**（20% 时间）：

- **大改 / 不熟的项目**：Claude Code（自主探索强）
- **设计稿转代码**：Codex + Figma MCP
- **远程布置**：Codex Web
- **省钱场景**：Codex++ + DeepSeek

**核心原则**：

- 单一任务用最轻量工具
- 复杂任务用最强工具
- 不同模型用不同工具
- **永远不绑死单一**——**Notion 工程师的共存策略是正解**

## 1 个我自己的真实心得

我 6 个月前坚定用 Claude Code，因为"它最强"。**但 3 个月后我转 Codex 主力 + Claude Code 辅助**——原因：

- Claude Code 按 API 用量，**月成本不可控**（$200+）
- 国内访问稳定性差
- **Codex 的 ChatGPT 订阅自带额度** + Desktop 多 Agent 协作更符合我的工作流

**但 Claude Code 仍是"探索未知代码库"的最佳**——**新项目 / 接手别人代码时，Claude Code 第一**。

**最终策略**：**不是选哪个，是怎么用**。

## 我的判断

**短期（3-6 个月）**：

- 三家功能继续趋同，**24 项对比会变成 30+ 项**
- Codex 在多 Agent / 桌面 / 异步跑赢
- Claude Code 在跨会话 / 长期记忆跑赢
- Cursor 在 IDE 内体验跑赢

**中期（6-12 个月）**：

- 独立开发者会形成"主力 + 辅助"的组合策略
- 单一工具用户减少
- **MCP / Skill / Plugins 成为差异化关键**

**长期**：

- 工具品牌淡化，**MCP / Skill 生态成为竞争主战场**
- 独立开发者的护城河从"会用工具" → "会组合工具" → "会写 skill"

下一章是系列最后一章：独立开发者 Codex 工作流模板——5 套真实可复制的日常工作流。