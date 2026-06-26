# 05. Kimi Work 深度：300 子 Agent 集群 + 13 小时长任务 + 开源 K2.6

**月之暗面 6/3-4 公测 Kimi Work** ——这是 15 款产品里**最技术野心**的一个：**300 个子 Agent 并行**、**13 小时长任务**、**4000+ 工具调用**、底层 Kimi K2.6（1 万亿参数 MoE）**完全开源**。这一章深度拆。

## Kimi Work 跟其他产品的根本差异

先讲清楚 Kimi Work 在 15 款里的独特定位：

| 维度 | Kimi Work | 其他产品 |
|------|-----------|---------|
| Agent 集群 | **300 个子 Agent** | 5-10 个（多数）|
| 长任务 | **13 小时** | 30 分钟 - 2 小时（多数）|
| 工具调用 | **4000+ 次/任务** | 50-200 次/任务 |
| 底层模型 | **Kimi K2.6 1T MoE 开源** | 闭源大模型为主 |
| 浏览器操作 | Kimi Claw（基于 OpenClaw 协议）| Computer Use（API 模拟）|
| 自我开发 | **5 万行代码 92% AI 自主** | 100% 人工开发 |

**Kimi Work 是"集群式" Agent**——不是单 Agent 升级，是**一群 Agent 协作**。

## Kimi K2.6：1 万亿参数开源 MoE

先讲底层模型。K2.6 是 1 万亿参数（1T）混合专家（MoE）架构，**完全开源**——Hugging Face 上能直接下载权重自己部署。

### 关键数据

- **参数量**：1T（1 万亿）
- **架构**：MoE（混合专家）
- **开源**：Hugging Face 可下载权重
- **支持自部署**：本地跑推理服务

### 为什么开源

月之暗面的战略：

- **让 Kimi Work 自己能用**——Kimi 工程师用 Kimi Code 跑出 5 万行代码 92% AI 自主生成
- **让开源社区用**——开发者可以基于 K2.6 跑自有应用
- **形成生态壁垒**——跟 Llama 类似的玩法

**Kimi 的野心**：通过开源 K2.6 + Kimi Work 客户端，**让"AI Agent 操作电脑"成为新一代 OS 范式**。

## Kimi Code CLI：终端里的编码 Agent

Kimi Work 装完后，**终端里自动多一个 `kimi` 命令**——这是 Kimi Code CLI。

### 4 种用法

**用法 1：交互模式**

```bash
$ kimi code
⠋ Kimi Code CLI 已就绪，当前目录: /home/user/project
输入你的编码任务 >
```

**用法 2：单次任务**

```bash
$ kimi code "重构这个文件中的路由逻辑，改用 React Router v7 的 loader 模式"
```

**用法 3：批量任务**

```bash
$ kimi code --batch tasks.json
```

**用法 4：Docker 部署**

```bash
$ docker run -d \
  --name kimi-work \
  -v /path/to/projects:/workspace \
  -e KIMI_API_KEY=your_key \
  moonshot/kimi-work:latest
```

### 关键能力

**项目知识图谱**：

不是简单把文件内容塞进 prompt，**会先分析 package.json、tsconfig、目录结构，建立项目知识图谱，然后才动手**。

**风格记忆**：

> 检测到你偏好使用函数组件而非类组件，是否在下一次任务中保持这个风格？

**首次配置后**——它会**永远遵守你的风格偏好**。

**改前 diff 预览**：

不会直接改文件，**先打印 diff 让你确认**——避免误改。

## Agent Swarm：300 个子 Agent 同时跑

**这是 Kimi Work 最具技术野心的能力**。

### Swarm 模式

当你提交复杂任务时，Kimi Work 的调度器会：

1. 把任务拆解为多个子任务
2. **动态派生子 Agent 并行执行**
3. 最多 300 个子 Agent 同时运行
4. 协作步骤超过 4000 步

### 实测场景：13 小时不间断编码

**任务**：

> 从零实现一个完整的小型项目——带用户认证、文章 CRUD、Markdown 编辑器的技术博客系统，前后端分离，React + Node.js + SQLite。这大概是一个中级前端工程师 3-5 天的工作量。

**设置**：

- 模式：Agent Swarm
- 最大子 Agent 数：50
- 然后睡觉

**第二天早上醒来**：

```
📊 任务完成报告
总耗时：13 小时 18 分钟
子 Agent 峰值：47/300
总协作步骤：4127
生成代码行数：4386
创建文件：24
自愈次数：7
```

**项目结构**：

```
tech-blog/
├── client/
│   ├── src/
│   │   ├── components/  (Layout, Editor, ArticleList, Auth)
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── App.tsx
│   └── package.json + tsconfig.json
├── server/
│   ├── src/
│   │   ├── routes/
│   │   ├── middleware/
│   │   └── models/
│   └── package.json + tsconfig.json
├── .env.example
├── docker-compose.yml
└── README.md
```

**验证**：

- `npm install && npm run dev` 直接跑
- 注册、登录、写文章、保存、列表展示——**功能全通**
- **不是 Demo 水平，是可以直接上线的项目骨架**

**自愈记录**：

- 7 次自愈
- 1 次 SQLite 语法错误 → 调度器派 debug 子 Agent 修
- 1 次 React Router 版本兼容 → Agent 自己降级处理

### Swarm 可视化

Agent Swarm Dashboard 实时显示：

```
活跃：47/300
- planner
- researcher-1, researcher-2, researcher-3, researcher-4
- coder-1, coder-2
- designer
- reviewer
- writer

协作步骤：2834/4000+
预计剩余：12 分钟
已生成：14/20 页
```

**每个小方块 = 一个子 Agent**：

- 绿色：运行中
- 灰色：已完成
- 红色：遇到错误（自动重试 3 次）

**点击任一子 Agent 看详细日志**：

```json
{
  "sub_agent_id": "researcher-3",
  "status": "running",
  "tools_in_use": ["browser", "filesystem"],
  "current_action": "正在读取 arXiv:2506.xxxxx 论文摘要",
  "memory_used": "2.3MB",
  "steps_completed": 14,
  "parent": "planner",
  "dependencies": ["researcher-1", "researcher-2"]
}
```

**关键设计**：**子 Agent 之间有依赖管理**——`researcher-3` 依赖 `researcher-1` 和 `researcher-2` 先完成搜索，调度器自动处理拓扑排序，**不会出现 Agent 在等另一个还没产出结果的数据**。

## Kimi Claw：基于 OpenClaw 协议的浏览器操作

**Kimi Claw 是 Kimi Work 的浏览器操作能力**——基于 **OpenClaw 协议**实现。

### OpenClaw 是什么

OpenClaw 是**开放的"数字操控层"协议**——定义了一套标准化接口，让 AI Agent **像人一样操作任何网页应用**：

- 点击
- 输入
- 滚动
- 截图
- 读取 DOM

**Kimi Claw 是 OpenClaw 的首个完整实现**。

### 实战场景

**任务**：

> 登录公司 Jira，提取本月所有"进行中"的任务，按优先级排序，生成一个 Markdown 周报，发到钉钉群。

**执行流程**：

1. 打开浏览器 → 导航到公司 Jira URL
2. 定位登录框 → 输入用户名密码（**从本地密钥链读取**）
3. 导航到"进行中"筛选视图
4. 读取任务列表（通过 DOM 解析）
5. 按优先级排序 → 生成 Markdown
6. 打开钉钉网页版 → 找到对应群聊
7. 粘贴内容 → 发送

**每一步你都可以在可视化面板里实时看到**。

**如果登录需要短信验证码**——**它会暂停等你手动输入**，然后从中断处继续。

### 配置文件

通过 `~/.kimi/claw/profiles.yaml` 管理：

```yaml
profiles:
  work-jira:
    url: "https://company.atlassian.net"
    auth:
      type: "keychain"  # 从系统密钥链读取，不存明文
      key: "jira-token"
    workflows:
      - name: "daily-report"
        steps:
          - navigate: "/issues/?filter=active"
          - wait_for: ".issue-list"
          - extract:
              selector: ".issue-row"
              fields: ["key", "summary", "priority", "status"]
          - sort: "priority"
          - export: "markdown"
```

**可以自己定义 workflow 模板**，也可以从 Kimi Work 的**社区模板库**一键导入。

**社区规模**：2 千+ 公开模板，覆盖 Jira、飞书、钉钉、Notion、Google Analytics 等。

## 30 小时实测：我为什么退订 Claude 保留 Copilot

我连续测了 30+ 小时，**Kimi Work 跑通后**：

### 退订 Claude Code

**关键原因**：Kimi Claw 的浏览器操作能力 + 13 小时长任务 + 300 Agent Swarm 集群，**比 Claude Computer Use 强 5-10 倍**。

**Claude Computer Use**：

- 走"模拟人类操作屏幕"路线
- 优势：通用性强（任何软件都能操作）
- 劣势：不够精准、受分辨率影响大

**Kimi Claw**：

- 走"API 调用"路线（基于 OpenClaw 协议）
- 优势：精准、稳定
- 劣势：覆盖面有限（依赖 DOM 结构）

**结论**：**两条路线谁会赢，现在下结论太早**——但 Kimi Claw 短期内领先。

### 保留 Copilot

**关键原因**：**Copilot 跟 Kimi Work 是互补**：

- **Copilot**：行级补全（敲一行补一行）
- **Kimi Work**：整个任务（给目标交付结果）

**两者不冲突**——Copilot 在 IDE 里写单行，Kimi Work 在 Agent 模式跑整个任务。

## Kimi Work 的 4 个真实坑

### 坑 1：300 Agent 全开风扇起飞

M3 Max 跑 Agent Swarm 47 子 Agent，**风扇声像要起飞去火星**。

**根因**：本地 Agent 调度层轻量，但**每个子 Agent 都要和云端模型通信**，网络 I/O 密集时 CPU 30%+。

**建议**：跑大任务时笔记本放通风好的地方。

### 坑 2：浏览器操作偶尔"点歪"

**Kimi Claw 定位精度取决于 DOM 结构**。遇到高度动态 SPA 页面（飞书多维表格的某些编辑视图），**Agent 点击坐标偏移 10 像素，点到隔壁按钮**。

**大部分时候自动重试**，但偶有翻车。

### 坑 3：Token 消耗大

Kimi Work 免费额度**每天能跑 3-4 个普通任务**。

**13 小时编码任务消耗约 30 万 Tokens**（Swarm 模式子 Agent 对话历史累计）。

**建议**：重型任务先买好额度包。

### 坑 4：不能完全代替复杂手工调试

让它修 CSS 响应式布局问题，**尝试 4 种方案都没完全解决**。最后我自己上手改 3 行媒体查询。

**结论**：**Kimi Work 擅长 0-80 分，最后 20 分的人类直觉和专业判断还是得自己来**。

## Kimi Work 实战案例

### 案例 1：30 分钟搭建企业内部数据看板

**任务**：

> 帮我创建一个内部项目进度数据看板，使用 HTML + Tailwind CSS + Chart.js，读取我桌面上的 project_data.csv。

**Kimi Work 跑通**：

1. 读取数据文件（5 个项目记录，包含进度和截止日期）
2. 询问细节（看板风格？图表类型？要不要导出 PDF？）
3. 直接开干
4. 打开浏览器搜 CodePen 参考样式
5. 打开 VS Code 写 HTML
6. 启动本地 HTTP 服务预览

**输出**：

- 4 个统计概览卡片
- 柱状图展示项目进度
- 表格列出所有项目详情
- 已完成绿色标签、逾期红色高亮

**总耗时：30 秒**——比我自己用模板手写快 5 倍。

### 案例 2：18 分钟生成 22 页 Transformer 论文 PPT

**任务**：

> 研究 Transformer 架构在 2025-2026 年的所有重要论文改进，生成 20 页 PPT 报告，包含核心思想、实验结果对比、我个人项目的应用建议。

**Agent Swarm 配置**：深度研究模式。

**结果**：

- **18 分钟完成 22 页 PPT**（比预想快 3 倍）
- 封面渐变蓝色调
- 每一页排版工整
- 参考文献脚注、图表来源标注
- **自动生成演讲备注文件**：

```markdown
# 第 1 页：封面
建议开场："过去 18 个月，Transformer 架构经历了自 2017 年以来最大的一次重构..."

# 第 3 页：Mamba 与线性注意力对比
关键数据：Mamba 在长序列任务上比标准 Transformer 快 5 倍，但困惑度略高 0.3
注意点：听众可能问"为什么不直接全用 Mamba？"——准备好解释混合架构的优势
```

**这是带着研究助理、设计师、文案、校对员的团队在帮你干活**。

### 案例 3：真实生产项目 - 13 小时博客系统

前面 13 小时不间断编码的案例就是真实生产项目——**不是 demo，是可以直接上线的项目骨架**。

## Kimi Work 适合谁

| 用户 | 适合度 | 原因 |
|------|--------|------|
| 重度开发者 | 极高 | 13 小时长任务、Swarm 集群 |
| 研究人员 | 极高 | 学术论文研究、跨学科任务 |
| 复杂任务派 | 极高 | 多 Agent 协作、动态调度 |
| 中小开发者 | 中等 | 简单任务用 Copilot 更轻 |
| 普通白领 | 较低 | 界面不如 QoderWork 友好 |
| 简单写代码 | 不适合 | 杀鸡用牛刀 |

## 独立开发者用 Kimi Work 的 3 种姿势

### 姿势 1：Swarm 模式做"周末项目"

周末有空了，开个 13 小时长任务——**周末晚上睡觉、跑 Swarm、周一早上 review PR**。

**适合**：重构老项目、迁移框架、写完整 demo。

### 姿势 2：Kimi Code CLI 做日常编码

VS Code / Cursor 之外，**用 `kimi code` 跑单次任务**。

**适合**：复杂 bug 排查、跨文件重构、自动化脚本。

### 姿势 3：Kimi Claw 做浏览器自动化

**替代 RPA 工具**——写一次 workflow（YAML），以后自动跑。

**适合**：Jira 周报、钉钉日报、Notion 数据更新。

## 我自己的 Kimi Work 用法

- **周末长任务**：重构老项目、跑 Swarm 集群
- **日常编码**：Kimi Code CLI（Copilot 之外补充）
- **办公自动化**：Kimi Claw 写 workflow，**替代 UiPath 类 RPA**

**月成本**：$30-50（Token 包 + Pro 订阅）。

## 跟其他厂商的对比

| 维度 | Kimi Work | 字节系 | 阿里系 | 腾讯系 |
|------|-----------|--------|--------|--------|
| Agent 集群规模 | **300（最大）** | TRAE 主-子 | Qoder 专家团 | WorkBuddy 三层 |
| 长任务 | **13 小时（最长）** | 数小时 | 数小时 | 8 小时 |
| 开源 | **K2.6 完全开源** | 闭源 | 闭源 | 闭源 |
| 浏览器操作 | **Kimi Claw（基于 OpenClaw）** | Computer Use | Computer Use | Marvis API 调 |
| C 端用户 | Kimi 网页版 | 豆包（最大）| 钉钉 AI | 微信（潜在）|
| B 端企业 | 弱 | 弱 | Qoder CN 强 | **WorkBuddy 最强** |

**Kimi Work 的优势**：

- **技术最深**（Agent Swarm 集群、长任务）
- **模型开源**（K2.6 1T MoE 完全开源）
- **OpenClaw 协议**（浏览器操作开放标准）

**Kimi Work 的劣势**：

- **C 端用户基数小**（豆包 vs Kimi 网页版）
- **B 端企业弱**（vs WorkBuddy 腾讯生态）
- **界面不如 QoderWork 友好**

## 我的判断

**Kimi Work 是 15 款里最具技术野心的**——但**也是商业化最不确定的**。

- **技术领先 6-12 个月**——Agent Swarm 集群、开源 K2.6、OpenClaw 协议都是行业第一
- **但产品体验、用户基数、企业生态都落后**

**6 个月后见分晓**：

- 如果 Kimi Work 能在产品体验 + C 端用户上追上来，**它就是 agent OS 的"Linux"**——开源生态 + 技术领先
- 如果追不上，**它就是"另一个 VS Code"**——好产品但用户基数小

下一章拆专业派——**百度文心快码 Comate 4.0**（C++ 第一、政企市场）、**智谱 CodeGeeX**（完全开源 + 130 语言）、**华为云 CodeArts**（鸿蒙 + 嵌入式）。这 3 款不是"大众产品"，但在各自细分市场**有真功夫**。