# 📚 Knowledge Garden

> A personal knowledge garden · multi-series Markdown books rendered as a single-file immersive HTML reader with notes, highlights, ambient music & PWA offline support.

[中文简介]
个人知识库。多本 Markdown 系列自动合成一个沉浸式阅读器：每一章都能做笔记、画高亮、配背景音乐，手机可加到主屏幕离线阅读。

## ✨ 特性

- **多书结构** — 一个仓库装多个系列，每本独立可读
- **单文件输出** — 整个阅读器是一个 `index.html`，没有构建依赖
- **沉浸式阅读** — 思源宋体 + 米白护眼底色 + drop cap + 暗色模式
- **笔记 + 高亮** — 选中文字即可高亮 / 写笔记，本地存储
- **背景音 + 翻页音效** — Web Audio API 实时合成，零外部文件
- **PWA 离线** — 推到 GitHub Pages 后，手机可加到主屏幕像 App 一样用
- **响应式** — 桌面 / 平板 / 手机自适应

## 🚀 在线访问

部署到 GitHub Pages 后：

```
https://<你的用户名>.github.io/knowledge-garden/
```

## 📁 目录结构

```
knowledge-garden/
├── books/                          # 书架根目录
│   ├── multi-agent/                # 一本书 = 一个子目录
│   │   ├── _meta.json              # {"title", "description", "priority", "order"}
│   │   ├── 01-your-first-agent/
│   │   │   └── README.md
│   │   ├── 02-why-multi-agent/
│   │   │   └── README.md
│   │   └── ...
│   └── llm-prompt/                 # 另一个系列
│       ├── _meta.json
│       └── ...
├── build_reader.py                 # 把 books/ 编译成 index.html
├── index.html                      # 生成的单文件阅读器
├── .github/workflows/deploy.yml    # GitHub Pages 自动部署
└── README.md
```

## ➕ 添加新书

### 步骤

1. 在 `books/` 下创建一个子目录（slug 用 kebab-case，比如 `crewai-life`）：

   ```bash
   mkdir books/crewai-life
   ```

2. 创建 `_meta.json`：

   ```json
   {
     "title": "CrewAI 实战",
     "description": "用 CrewAI 构建生产级 Multi-Agent 系统",
     "priority": 3,
     "order": ["01-quickstart", "02-patterns"]
   }
   ```

   - `priority` — 数字越小越靠前
   - `order` — 章节顺序列表，不填则按目录名排序

3. 创建章节子目录 + `README.md`：

   ```bash
   mkdir books/crewai-life/01-quickstart
   ```

   ```markdown
   # 快速上手

   本章介绍 CrewAI 的基本概念...

   ## 下篇

   [02. 常用模式](../02-patterns/)
   ```

4. 重新生成阅读器：

   ```bash
   pip install markdown pygments
   python build_reader.py
   ```

5. 推送到 GitHub，Actions 会自动部署到 Pages。

### 章节标题

章节的展示标题默认取 `README.md` 的第一个一级标题（`# xxx`）。如果没写一级标题，则用目录名。

## 🛠 本地运行

不需要任何构建步骤，直接打开 `index.html` 即可：

```bash
# 方式 1：浏览器打开
start index.html       # Windows
open index.html        # macOS

# 方式 2：本地起服务（推荐，避免某些浏览器 file:// 限制）
python -m http.server 8000
# 然后访问 http://localhost:8000/
```

## 📦 部署到 GitHub Pages

### 一次性配置

1. 在 GitHub 仓库 → **Settings** → **Pages**
2. **Source** 选 **GitHub Actions**
3. 第一次 push 后 Actions 会自动部署

### 自动部署

`.github/workflows/deploy.yml` 会在每次 push 到 `main` 分支时：

1. Checkout 代码
2. 安装 `markdown` 和 `pygments`
3. 跑 `python build_reader.py` 生成 `index.html`
4. 部署到 GitHub Pages

几分钟后访问 `https://<用户名>.github.io/knowledge-garden/` 即可。

## ⌨️ 快捷键

| 键 | 功能 |
|---|------|
| `D` | 切换暗色模式 |
| `S` | 收起/展开书架 |
| `M` | 背景音面板 |
| `N` | 笔记列表 |
| `+/-` | 字号调节 |
| `Esc` | 关闭所有弹窗 |

## 📝 技术细节

### 阅读器架构

- 单 HTML 文件，所有 CSS / JS / 图片 base64 内嵌
- 解析：Python `markdown` 库 → HTML
- 字体：思源宋体（Source Han Serif）+ Georgia
- 音频：Web Audio API 实时合成（白噪音 / 雨声 / 暖调）
- 笔记存储：`localStorage`，刷新不丢
- PWA：内嵌 manifest + Service Worker（blob URL）

### 浏览器要求

- Chrome / Edge / Safari / Firefox 最新版
- iOS Safari 13+
- Android Chrome 80+

## 🌱 当前书目

- 📕 **Multi-Agent in Practice**（10 章）— 从零到生产构建 Multi-Agent 系统
- 📗 **LLM Prompt 实战**（3 章）— 从基础到高级的 Prompt 工程指南

## 📄 License

MIT

## 🙏 致谢

- [Source Han Serif](https://github.com/adobe-fonts/source-han-serif) — 思源宋体
- [python-markdown](https://python-markdown.github.io/) — Markdown 解析
- [CrewAI](https://crewai.com) / [LangGraph](https://langchain-ai.github.io/langgraph/) / [AutoGen](https://microsoft.github.io/autogen/) — Multi-Agent 框架