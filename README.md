# Knowledge Garden

[![Deploy](https://github.com/mishishi/knowledge-garden/actions/workflows/deploy.yml/badge.svg)](https://github.com/mishishi/knowledge-garden/actions/workflows/deploy.yml)

A personal knowledge garden. Multiple Markdown book series compiled into a single-file immersive HTML reader with notes, highlights, ambient music, and PWA offline support.

我自己的个人知识库。写了 17 个 AI/Agent 工程系列的笔记（Multi-Agent / LLM Prompt / CrewAI / Context Engineering / RAG / Harness / Agent Skills / Agent Cost / Claude Code / Vibe Coding / A2A 多 Agent 互操作 / 长期记忆 / 具身智能 / AI 内容创作经济 / Indie + AI / Codex 实战案例 / 中国版 Codex 大乱斗），每一本都能做笔记、画高亮、配背景音乐。手机可加到主屏幕离线阅读。整套部署在 GitHub Pages，访问 [mishishi.github.io/knowledge-garden](https://mishishi.github.io/knowledge-garden/)。

## 为什么做这个

我 2024 年开始系统学 AI agent 工程。读了论文、刷了 Hacker News、看了 Claude Code / Devin / LangGraph 的源码，也自己写了好几个 production agent。

最大的问题是：**这些知识散落在博客、推特、文档、代码注释里**，找一个具体细节要翻十几个 tab。Notion / Obsidian 也试过，但太重——打开 3 秒，弹窗一堆，专注力 0。

所以做了这个：一个**纯单文件 HTML 阅读器**（一个 index.html，2.3MB，包含全部 CSS / JS / 内容），打开就是阅读，没有 chrome 干扰，能做笔记画高亮，背景白噪音帮我专注。

## 当前书目

17 个系列 / 175 章节 / 22.4 万字。包含 RAG、多 Agent、Harness、Indie + AI、Agent Skills、Claude Code、Vibe Coding、A2A、长期记忆、具身智能、AI 内容创作经济、Codex 实战案例 (15 章)、中国版 Codex 大乱斗 (10 章) 等系列。

**Multi-Agent in Practice（10 章）**——从零到 production 的 multi-agent 系统。第一章讲为什么需要 multi-agent（单 agent 的 3 个真实局限），最后一章讲 prod checklist（性能 / 质量 / 安全三维度）。中间 8 章拆解 5 个抽象、orchestration 模式、state / communication、failure handling、框架对比、observability。

**LLM Prompt 实战（10 章）**——prompt 工程的工程视角，不只是"few-shot + chain-of-thought"。涵盖 role 设计、约束注入、structured output、function calling、reasoning 控制、稳定性调优。

**CrewAI 入门到实战（10 章）**——单框架深度教程。crew / agent / task / tool 四个核心概念拆到每个细节，CrewAI 内部 workflow 源码级讲解，5 个真实项目从 prototype 到 deploy。

**RAG 实战（10 章）**——检索增强生成的工程化路径。从为什么 RAG（不是 fine-tune）开始，覆盖 embedding 模型选型、向量数据库、chunking 策略、retrieval + reranking、prompt 设计、hybrid search、evaluation、advanced patterns、production checklist。

**Harness Engineering（10 章）**——包裹 LLM 的整套工程基座。第 1 章讲"什么是 harness"（用我自己写 agent 翻车的 3 个真实事故开场），第 2-10 章拆 9 个核心组件：agent loop 8 种变体、tool 设计原则、context 管理、permissions / sandbox、observability、memory 分层、failure recovery、eval-driven development、从零造一个 harness。每一章都有我自己的生产数据（failure rate 22% → 8%、cost 翻 3 倍但稳定性翻 3 倍这种）。

**Claude Code 实战（10 章）**——终端原生 AI 编程 agent 深度。安装配置、CLAUDE.md 项目记忆、Skills/Hooks、SubAgent、Worktree、MCP 集成、Slash Commands、10 个真实场景、成本调优、和 Cursor / Codex / TRAE 的对比。

**Vibe Coding 实战（10 章）**——2026 最热的编程范式。Karpathy 的原始定义、工具全景（Claude Code / TRAE / Cursor / Windsurf / Cline / Roo Code 横评）、三段式口述方法（初始需求 / AI 生成 / 精准修正），3 个真坑复盘（EC-MINI-2026 N+1 性能雪崩 / LOGISTICS_V2 字段割裂 / Gin JWT 安全硬编码），TRAE Work 模式 vs Claude Code 迁移，中文需求理解的本地化优势，vibe coding 的边界（一句话：所有代码 70 分 AI 写、100 分人改），个人一整套工作流模板。

**A2A + 多 Agent 互操作（10 章）**——2026 agent 互操作协议。A2A 协议 vs MCP 的分工（一个管工具、一个管 agent 团队）、Agent Card 设计（"agent 世界的 OpenAPI"）、4 种协作范式（管道 / 辩论 / 分层 / 市场）的实战代码骨架、Pipeline / Debate / Hierarchical / Market 各自的适用场景与成本、5 类安全威胁（恶意 agent / 数据泄露 / 权限提升 / DoS / 合规审计）的防御机制，最后一章讲一个端到端的真实生产架构——某金融客户的风控分析师团队。

**长期记忆系统（10 章）**——超越 context window 的 agent 持续学习。三层记忆架构（工作记忆 / 情景记忆 / 语义记忆）、Working memory 的 3 个关键技术（compaction / pruning / recitation）、Episodic memory 的事件流存储（pgvector / Pinecone 实战）、Semantic memory 的知识提炼（从事件到偏好 / 规则 / 关系的 LLM 提炼流程 + 版本化 + 冲突处理）、向量数据库选型（pgvector vs Pinecone vs Milvus）、知识图谱的关系推理（Neo4j / Memgraph / Nebula Graph）、混合检索（向量 + 关键词 + 图谱的 RRF 融合）、写入策略（什么写、什么不写、怎么避免存储爆炸）、GDPR 合规的可删除设计。

**具身智能实战（10 章）**——AI 大脑装到机器人身体。什么是 embodied agent（大脑 + 身体 + 真实世界交互）、三大支柱（VLM 大脑 / 人形机器人硬件 / 仿真训练平台）、世界模型（agent 在脑子里模拟未来的能力）、仿真训练全流程（Isaac Lab / Genesis / MuJoCo / Habitat / CARLA 五大平台对比）、sim-to-real 的 4 类 gap 和 5 种方法、机械臂操作（抓取 / 装配 / 灵巧手）、导航（SLAM / 路径规划 / 视觉语言导航）、家庭服务机器人（1X Neo / Figure 02 / Tesla Optimus 的 2026 现状与 3-5 年展望）。

**AI 内容创作经济（10 章）**——AI 重塑内容产业。2026 创作者用 AI 比例 78%、AI 内容占互联网 35%（vs 2023 年 5%）、AIGC 工具全景（Claude / GPT / Midjourney / Sora / ElevenLabs / Suno）、内容工作流改造（Newsletter / YouTube / 小红书 / 播客各自的 AI 工作流）、Newsletter 经济（Substack / Beehiiv 平台对比 + 5 个赛道 + 5 个阶段）、6 大变现路径（付费订阅 / 广告 / 产品 / 社群 / 电商 / 投资）、AI 协作创作（人和 AI 怎么配合 + 5 个核心原则）、版权与权利问题（训练数据 / 生成内容 / 平台合规）、未来 3-5 年创作者经济展望。

每个系列的 meta 写在 `books/<series>/_meta.json`，章节顺序按 `order` 数组排，priority 数字越小越靠前。

## 读者体验

打开 `index.html` 看到左侧书架列出 15 个系列，点进任一系列展开章节列表。

主阅读区支持：选中文字弹笔记 / 高亮按钮（localStorage 存）、drop cap + 米白护眼底色、暗色模式（D 键切换）、字号调节（+/-）、背景白噪音（M 键打开面板）、章节进度自动追踪（每章阅读时间 + 完成度）、Cmd+K 全局搜索 + 系列 filter、聚焦模式（F 键隐藏侧栏 + 工具栏）、段落书签（点击书侧栏 bookmark 跳回 + 高亮 4 秒）、笔记 + 书签一键导出为 Markdown。

首页 Overview 集成：本周阅读目标进度环、3 档回顾（本周/本月/今年，已读章节 + 阅读分钟 + 新增笔记 + 涉及系列）、笔记图谱（Fruchterman-Reingold 力学布局，按章节聚合 + 跨书 2-gram 虚线）、**动态学习路径**（老用户 5 策略打分：in-progress / 同系列下一章 / 主题 RELATED / 7 天书签 / 7 天笔记 → top 5；新用户按 priority 取 5 系列首章）、**知识问答**（侧栏按钮 + Ctrl+/ 快捷键，预生成 TF-IDF + dense embedding 双索引 1298 chunks 跨 22.4 万字，浏览器 cosine 相似度 top-5，同义词扩展 + 标题命中加权 + 关键词高亮 + 章节跳转；可选 BGE 中文 dense embedding 混合检索，~24MB int8 模型首次下载后浏览器缓存）、艾宾浩斯间隔重复（简化的 SM-2，ease 1.3-2.5）、Anki 卡片管理、章节 TTS 朗读（Edge TTS + auto-detect 按需显示按钮）。

手机端：浏览器菜单"添加到主屏幕"就变成 PWA，可以离线阅读（Service Worker + 内嵌 manifest），跟原生 App 体验接近。

## 怎么本地跑

不需要任何构建步骤。直接打开 `index.html`：

```bash
# Windows
start index.html

# macOS
open index.html

# Linux
xdg-open index.html
```

或者起本地 server（推荐——避免某些浏览器对 file:// 的限制）：

```bash
python -m http.server 8000
# 然后访问 http://localhost:8000/
```

## 怎么加新书

`books/` 目录下加一个子目录 + `_meta.json` + 章节子目录。具体步骤：

创建目录（slug 用 kebab-case）：

```bash
mkdir books/my-new-series
mkdir books/my-new-series/01-chapter-one
```

写 `_meta.json`：

```json
{
  "title": "我的新系列",
  "description": "一句话讲清这个系列讲什么",
  "icon": "agents",
  "color": "#5b8c85",
  "priority": 6,
  "order": ["01-chapter-one"]
}
```

`icon` 字段必须是 `build_reader.py` 里 ICONS dict 包含的 key（agents / sparkles / bot / bookmark / database / layers / qr / disc 等 25+ 个 SVG icon）。`color` 是系列主题色，sidebar / 进度条 / 章节标题会用。`priority` 数字越小在 sidebar 越靠前。

写章节内容：

```markdown
# 01. 章节标题

章节内容用标准 Markdown 写。可以代码块、表格、列表、引用、链接。

## 小节

更多内容。

[下一章](../02-chapter-two/)
```

跑 build 生成新 index.html：

```bash
pip install markdown pygments qrcode[pil]
python build_reader.py
```

推送 GitHub，Actions 自动部署到 Pages。

## 章节标题约定

`build_reader.py` 自动从 README.md 的第一个 `# xxx` 提取章节展示标题。如果没写一级标题就用目录名。

## 怎么部署到 GitHub Pages

仓库 Settings → Pages → Source 选 GitHub Actions。第一次 push 后 Actions 跑完几分钟就能访问。

`.github/workflows/deploy.yml` 流程：checkout → `pip install markdown pygments qrcode[pil]` → `python build_reader.py` → `actions/deploy-pages@v4` 上传。

`qrcode[pil]` 是 build_reader.py 生成页面二维码用的——别忘了装。

## 快捷键

D 切换暗色模式，S 收起展开书架，M 背景音面板，N 笔记列表，+ / - 字号调节，Ctrl+K 全局搜索，Ctrl+S 搜索下一个，Ctrl+F 笔记内查找，Ctrl+G 跳到章节首/末，Esc 关闭所有弹窗，? 帮助弹窗，F 聚焦模式。

按 ? 弹出完整快捷键 cheat sheet。

## 技术实现

主页 `index.html` 1.25 MB raw / 157 KB gzipped（结构 + CSS + JS + 顶部 TOC + 17 个 book cover），章节正文 lazy load 到 `assets/books/{slug}.json`（每书 60-300 KB），Q&A 索引 lazy load 到 `assets/knowledge_index.json`（1.75 MB） + `assets/knowledge_dense.json`（4 MB，仅启用 AI 语义搜索时）。

CSS / JS / SVG icon / PWA manifest 全部内嵌，没有运行时依赖（除了 Google Fonts 的思源宋体）。Mermaid 渲染按需引入。

Markdown 解析用 Python `markdown` 库 + `pygments` 做代码高亮。音频用 Web Audio API 实时合成（白噪音 / 雨声 / 暖调 / 火焰），零音频文件。笔记 / 高亮 / 进度 / 偏好 / 背景音设置 / 搜索历史全部 `localStorage`。

PWA：内嵌 manifest + 通过 blob URL 注册的 Service Worker，桌面浏览器支持"安装为应用"，iOS Safari 支持"添加到主屏幕"。

GitHub Pages 用 `actions/deploy-pages@v4`，权限 `pages: write` + `id-token: write`。

## 内容风格

每个章节都是我自己写的实战笔记，不是"什么是 X"的概念介绍。具体表现：

**第一人称**——我写 agent 翻车的 3 个真实事故、我跑过的 50 个任务对比数据（32% → 78%）、我自己的第 3 版 harness 实现。

**带代码**——不只是 API 演示，是带翻车点注释的实战代码。比如 `BLOCKED_CMDS` 黑名单不够要加白名单、`subprocess.timeout=10` 不加 LLM 会调 `sleep 999999` 卡死。

**有数据**——任务完成率、cost 翻倍、failure rate 演变、recovery rate 演变，能用数字的地方不用"显著提升"这种抽象概括。

**真实案例**——Anthropic / Cognition / Anysphere / LangGraph 这些团队的工程博客和我从源码里读到的实现细节，每个引用都带日期和团队名。

## 浏览器要求

Chrome / Edge / Safari / Firefox 最新版。iOS Safari 13+，Android Chrome 80+。IE 不支持。

## 2026-06-27 这一波 UX 改进

一口气推了 9 项, 主要是把"内容站"打磨成"个人学习环境". 都已部署到 Pages.

**上手就感受到的 (Tier 一)**
- 首次访问引导, 12 标签选 3 个推 5 章
- 章节内进度条 + 滚到底自动算百分比
- 长章节右侧 sticky TOC (≥ 1200px 才出现)
- 读完底部弹"下一章" CTA
- Cmd+K 状态过滤 (未读 / 有笔记 / 有书签 / 已读完)
- Q&A 跳到章节后 query term 黄闪 2.5s

**用着用着才察觉的 (Tier 二)**
- 章节底部"相关章节"卡片 (复用 dense index)
- Q&A 搜索历史 (localStorage, 最多 8 条)
- 16 周阅读 Streak 热度图 (GitHub-style)
- 继续阅读 carousel (主续 + 同系列 + 主题相关, 横滑)
- 章节顶部面包屑 + 系列色 ribbon
- 读完祝贺 toast (累计 N 章 + 下一章快捷链)
- Q&A 输入时下拉 top-5 章节建议

**性能 (Lazy load)**
- 章节正文 build 时拆到 17 个 `assets/books/{slug}.json` (60-300 KB)
- 主页只剩结构 + 顶部 TOC, IntersectionObserver 600px 距离触发 fetch
- 同本书只拉一次, in-flight 去重
- 初始 gzipped: 843 KB → **157 KB** (5.4x ↓)
- Q&A jump / hash 直跳 / 滚动预加载 全覆盖

主要 commit: `1275ab3` / `f0be3eb` / `a762c84` / `0b7b07d` / `a6efc87` / `bf00e71` / `6f27eed` / `a1797bc` / `43ffa5e`.

## License

MIT

## 致谢

[Source Han Serif](https://github.com/adobe-fonts/source-han-serif) 思源宋体。[python-markdown](https://python-markdown.github.io/) Markdown 解析。[Anthropic](https://www.anthropic.com/) / [Cognition](https://www.cognition.ai/) / [Anysphere](https://anysphere.inc/) / [LangChain](https://www.langchain.com/) 的开源项目和工程博客，是 Harness Engineering 系列的主要参考来源。
