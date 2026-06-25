# 01. 什么是 vibe coding

2025 年 2 月，Andrej Karpathy 在 X 上发了一条推：**"There's a new kind of coding I call 'vibe coding', where you fully give in to the vibes, embrace exponentials, and forget that the code even exists."**

他说的 vibe coding 不是"用 AI 辅助编程"那种程度——是**完全不读代码**。你描述想要什么，AI 写；AI 写完你看一眼，跑得起来就 commit，跑不起来把报错贴回去，让 AI 改。

听起来离谱。但 2026 年这件事变成了主流。字节跳动 6 月办的 TRAE AI 创造力大赛，4 万人报名，初赛 30 万冠军奖金。小红书"vibe coding"标签笔记 6 万 + 篇。GitHub 上周新增的 repo 里大约 38% 是用 vibe coding 写的（Stack Overflow 2026 调研口径）。

## vibe coding 和传统 AI 辅助编程的边界

传统 AI 辅助（Copilot 那种）你写函数签名，AI 补全函数体——你**逐行读、逐行审**。vibe coding 你**不读函数体**，只读 commit message 和跑出来的日志。

边界其实在**你愿不愿意接受"我没看这段代码"**。Copilot 用户每天读 800 行 AI 写的代码，vibe coding 用户一周才读 200 行。

## 为什么 2026 突然爆发

三个原因叠在一起。模型层面，o1 / o3 / Claude extended thinking 这一波 reasoning 模型在 2025 年底到 2026 年初成熟，能把"模糊需求"翻译成"可执行代码"，中间不用人干预。工具层面，Claude Code 2025 年下半年、TRAE 2026 年初、Windsurf / Cline / Roo Code 全员到位，IDE / 终端 / 浏览器三类载体都有人做。生态层面，CSDN / 腾讯云 / 知乎上"vibe coding 实战"类文章单篇 10w+ 阅读比比皆是，2026 内容创作者用 AI 比例从 15% 涨到 78%，工具市场自然跟上。

## 谁适合 vibe coding

**适合**：原型阶段（半天出 MVP）、独立项目（owner 就是自己）、遗留项目批量重构（接手别人代码不想逐行读）、一次性脚本（用完就扔）、教学 / 内部 demo（代码不需要长期维护）。

**不适合**：金融 / 医疗 / 政企（合规要求逐行审计）、开源核心库（社区要 review）、高频性能路径（必须人写人调）、安全敏感模块（鉴权 / 加密 / 支付）。

## 我自己用 vibe coding 的边界

写个人工具、写 demo、写内部自动化脚本——全 vibe，不读代码。

写知识花园这种长期项目——vibe 出初版，逐行读 + 修，再 commit。

写客户项目——vibe 出原型，但交付前必须人工读 + 改 + 补测试 + 补文档。

下一章聊工具。Claude Code / Cursor / TRAE / Windsurf / Cline / Roo Code / Copilot 七款主流怎么选。