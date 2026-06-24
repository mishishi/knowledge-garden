# Knowledge Garden

[![Deploy](https://github.com/mishishi/knowledge-garden/actions/workflows/deploy.yml/badge.svg)](https://github.com/mishishi/knowledge-garden/actions/workflows/deploy.yml)

A personal knowledge garden. Multiple Markdown book series compiled into a single-file immersive HTML reader with notes, highlights, ambient music, and PWA offline support.

我自己的个人知识库。写了 5 个 AI/Agent 工程系列的笔记，每一本都能做笔记、画高亮、配背景音乐。手机可加到主屏幕离线阅读。整套部署在 GitHub Pages，访问 [mishishi.github.io/knowledge-garden](https://mishishi.github.io/knowledge-garden/)。

## 为什么做这个

我 2024 年开始系统学 AI agent 工程。读了论文、刷了 Hacker News、看了 Claude Code / Devin / LangGraph 的源码，也自己写了好几个 production agent。

最大的问题是：**这些知识散落在博客、推特、文档、代码注释里**，找一个具体细节要翻十几个 tab。Notion / Obsidian 也试过，但太重——打开 3 秒，弹窗一堆，专注力 0。

所以做了这个：一个**纯单文件 HTML 阅读器**（一个 index.html，657KB，包含全部 CSS / JS / 内容），打开就是阅读，没有 chrome 干扰，能做笔记画高亮，背景白噪音帮我专注。

## 当前书目

5 个系列 / 50 章节 / 5 万字。

**Multi-Agent in Practice（10 章）**——从零到 production 的 multi-agent 系统。第一章讲为什么需要 multi-agent（单 agent 的 3 个真实局限），最后一章讲 prod checklist（性能 / 质量 / 安全三维度）。中间 8 章拆解 5 个抽象、orchestration 模式、state / communication、failure handling、框架对比、observability。

**LLM Prompt 实战（10 章）**——prompt 工程的工程视角，不只是"few-shot + chain-of-thought"。涵盖 role 设计、约束注入、structured output、function calling、reasoning 控制、稳定性调优。

**CrewAI 入门到实战（10 章）**——单框架深度教程。crew / agent / task / tool 四个核心概念拆到每个细节，CrewAI 内部 workflow 源码级讲解，5 个真实项目从 prototype 到 deploy。

**RAG 实战（10 章）**——检索增强生成的工程化路径。从为什么 RAG（不是 fine-tune）开始，覆盖 embedding 模型选型、向量数据库、chunking 策略、retrieval + reranking、prompt 设计、hybrid search、evaluation、advanced patterns、production checklist。

**Harness Engineering（10 章）**——包裹 LLM 的整套工程基座。第 1 章讲"什么是 harness"（用我自己写 agent 翻车的 3 个真实事故开场），第 2-10 章拆 9 个核心组件：agent loop 8 种变体、tool 设计原则、context 管理、permissions / sandbox、observability、memory 分层、failure recovery、eval-driven development、从零造一个 harness。每一章都有我自己的生产数据（failure rate 22% → 8%、cost 翻 3 倍但稳定性翻 3 倍这种）。

每个系列的 meta 写在 `books/<series>/_meta.json`，章节顺序按 `order` 数组排，priority 数字越小越靠前。

## 读者体验

打开 `index.html` 看到左侧书架列出 5 个系列，点进任一系列展开章节列表。

主阅读区支持：选中文字弹笔记 / 高亮按钮（localStorage 存）、drop cap + 米白护眼底色、暗色模式（D 键切换）、字号调节（+/-）、背景白噪音（M 键打开面板）、章节进度自动追踪（每章阅读时间 + 完成度）、Cmd+K 全局搜索 + 系列 filter、聚焦模式（F 键隐藏侧栏 + 工具栏）、段落书签（点击书侧栏 bookmark 跳回 + 高亮 4 秒）、笔记 + 书签一键导出为 Markdown。

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

单 HTML 文件，656 KB。CSS / JS / SVG icon / PWA manifest / Service Worker 全部内嵌，没有外部依赖（除了 Google Fonts 的思源宋体）。

Markdown 解析用 Python `markdown` 库 + `pygments` 做代码高亮。音频用 Web Audio API 实时合成（白噪音 / 雨声 / 暖调 / 火焰），零音频文件。笔记 / 高亮 / 进度 / 偏好 / 背景音设置全部 `localStorage`。

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

## License

MIT

## 致谢

[Source Han Serif](https://github.com/adobe-fonts/source-han-serif) 思源宋体。[python-markdown](https://python-markdown.github.io/) Markdown 解析。[Anthropic](https://www.anthropic.com/) / [Cognition](https://www.cognition.ai/) / [Anysphere](https://anysphere.inc/) / [LangChain](https://www.langchain.com/) 的开源项目和工程博客，是 Harness Engineering 系列的主要参考来源。
