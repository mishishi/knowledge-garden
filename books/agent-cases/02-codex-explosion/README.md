# 02. Codex 2026 大爆发：6/3 发布会深度拆解

2026 年 6 月 3 日北京时间凌晨，OpenAI 办了一场叫"AI 上岗"的发布会。一个半小时，讲了一件把整个独立开发者生态重新洗牌的事。我把这场发布会所有公开信息 + 后续 24 小时业界反应整理了一遍。

## 发布会核心信息

**Codex 整合进 ChatGPT**。这是整场最大的事。OpenAI 企业产品主管 Alexander Embiricos 宣布，未来几周内 Codex 直接进入 ChatGPT。10 亿 ChatGPT 用户，零门槛调 Codex。

**Codex 周活 500 万**。OpenAI 首席营收官 Denise Dresser 透露，**20% 用户不是程序员**——他们用 Codex 写报告、做研究、整理会议纪要。

**两个新功能 + 6 个行业插件**：

- **批注（Annotations）**：用户可以在 Codex 输出上直接标注修改意见，系统精准定位修改区域。这是 OpenAI 学 Anthropic 的 Artifacts？
- **站点（Sites）**：自然语言描述 → 一键生成可交互的网页应用 → 生成 URL 分享。比如"给我做个对比 GPT vs Claude 的交互页面"，Codex 直接生成可点击的网页。

**6 个行业插件**：数据分析、创意制作、销售、产品设计、上市公司股票投资、投资银行。每个插件打包了岗位特定的工作流 + 技能指令 + 需要的外部 app（110 skill + 62 集成）。

## GPT-5.5 + Codex 的关键数字

OpenAI 企业业务负责人 Alexander Sergian 公布：**使用 GPT-5.5 + Codex 获得相同质量输出所需的 token 数仅为原来的 1/3**。

这个数字独立开发者最该算账。我之前的 vibe coding 系列里讲过 "token 成本是 indie 项目最大杀手之一"，现在 token 单价降 3 倍，相当于把 vibe coding 月成本从 $300 降到 $100。

**企业营收占比**：从 40% 涨到 50%，2026 年底。Sam Altman 现场说："OpenAI 进入第三个发展阶段，目标是让所有人都能用上 AI。"

## 我看完发布会的 3 个反应

**反应 1：Codex 真的不是写代码工具了**

之前我用 Codex = "OpenAI 的 Claude Code 竞品"。现在不是了。**Codex 正在变成 ChatGPT 里的"瑞士军刀"**——每个用户都能用它做日常工作的各种事。这意味着：

- 你做的产品不再假设用户是程序员
- 你做的应用 UX 门槛要降到"会用 ChatGPT 就能用"
- 你做的 skill / agent 可能直接被 Codex 平台分发

**反应 2：插件经济来了**

OpenAI 推 6 个行业插件 + 110 skill + 62 集成。这跟 Claude Code 的 skill 系统、Anthropic 的 MCP 是同方向——**"agent 时代的 App Store"**。

独立开发者的玩法变了。你不再需要做网站、SEO、marketing 让用户找到你。**做 agent skill，挂到大平台**。Substack 之于创作者 = Codex 之于 agent 开发者。

**反应 3：第三方 API + 第三方模型将成主流**

Codex CLI 支持第三方模型接入（之前是 OpenAI-only）。对独立开发者这是个隐藏机会——你可以写 Codex skill，但跑在 Claude / DeepSeek / Qwen 上。这是跨平台 agent 工具的关键能力。

## Codex 当前的 5 种接入方式

我整理的当前 Codex 接入路径，按推荐度排：

**1. ChatGPT 内置（2026 年 6 月起）**

零门槛，10 亿用户可访问。适合非程序员 / 营销 / 销售 / 设计师。劣势：能力受限（不能直接读写你本地文件）。

**2. Codex Desktop App（⭐⭐⭐⭐⭐ 推荐）**

独立桌面客户端，类似 Cursor 但深度集成 ChatGPT 账号体系。**支持读写本地代码 / 文件 / 命令行 + Computer Use**。2026 年 4 月更新后能像真人一样操作你的电脑。

**3. VS Code 扩展（⭐⭐⭐⭐）**

发布者：OpenAI 官方。功能：Agent 模式 + Chat 模式，Diff 预览 + 终端执行。**最像 Claude Code 的 VS Code 体验**。

**4. Codex CLI（⭐⭐⭐）**

终端命令行版，最轻量。`npm install -g @openai/codex`。**支持第三方模型 + 自定义 Provider**（这是穷人玩 Codex 的入口，我之前详细写过怎么接 1/10 价格的 API）。

**5. Codex SDK**

程序化集成到自己的产品里。给独立开发者做 agent 产品用。

## 5 件事独立开发者现在可以做

**1. 重新审视你的应用 UX**

之前假设"用户是开发者"，现在要假设"用户是用 ChatGPT 的人"。**简化 UI、降低门槛、自然语言输入**。

**2. 写 Codex skill**

OpenAI 平台开了 skill 提交通道。你的 domain expertise 可以做成 Codex skill 被分发。Substack 的内容创作者经济拐点会在 agent skill 上重演。

**3. 关注 CodexLoop + CodexLoop 类工具**

下一章我会拆 CodexLoop（开源工具，让 Codex 长任务不偷懒）。这类"工程化 Codex"的开源工具是独立开发者的金矿——你可以基于它做付费 SaaS。

**4. 飞书 CLI / 钉钉 CLI / 企微 CLI 接入**

第 08 章会拆一个真实案例：用飞书 CLI + Codex 做每日 SEO/GEO 检查提醒。**任何重复性办公任务都可以 agent 化**。

**5. 关注 Computer Use**

Codex 4 月更新加了 Computer Use——**Agent 能控制你的电脑光标，像真人一样操作所有 app**。下一章会拆。

## 我的判断

**短期（3 个月）**：ChatGPT 整合让 Codex 用户基数从 500 万冲到几千万。skill 生态开始起来。

**中期（6-12 个月）**：agent 插件经济成熟，Substack 之于创作者的拐点会在 agent skill 上重演。**独立开发者的"做应用"会变成"做 skill"**。

**长期（12+ 个月）**：Computer Use + 多 agent 协作成熟后，"AI 员工"概念会真的落地。一个人 + 一套 agent = 一家公司。

下一章讲 AGENTS.md——Codex 2026 杀手级功能，让你的项目规则自动被 agent 遵守。