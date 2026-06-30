# 12. 未来 12 个月: Agent 会怎么变

---

写这一章的晚上,我刚跑完一个 benchmark, 把一个开源 agent 从 0.62 的任务完成率调到 0.79. 调完没觉得兴奋, 反而坐在那想: 这已经是 2025 年底了, 我们到底在干什么?

2024 年初我刚开始认真做 agent 的时候, 整个圈子还在争论 ReAct 跟 BabyAGI 哪个对. 12 个月过去, 这两个名字都变成了历史脚注. Anthropic 把 tool use 变成 first-class, OpenAI 把 Assistants 推上线又下线, LangChain 从 v0.1 写到 v0.3, LangGraph 半路杀出来. 整个市场烧了几十亿, 留下的最大共识大概是: 这个东西能赚钱, 但没人知道边界在哪.

我今天不想预测未来, 我想把这一年我看清楚、踩过的、到现在还有点想不通的东西摊开讲. 不是综述, 是年终复盘.

## 一年之后再回看, 我们到底进化了什么

先说个让我自己意外的事. 年初我跟实习生说"agent 是一个会调工具的 LLM", 他点头. 现在我跟新人说同样的话, 他们会反问"哪种 agent, ReAct 还是 plan-and-execute? 用 MCP 还是 function calling? 单 agent 还是 multi-agent?"

词汇爆炸了, 但底下那层最核心的东西, 老实讲, 进化没那么夸张.

2024 年初, 一份 prompt 加一个 tool list 加一个循环, 就能跑起来一个 agent. 我当时写过一个内部 demo, 调十几个 SaaS API, 准头一般, 但能跑. 现在, prompt 还在, tool list 更长, 循环更复杂, 中间塞了 reflection、planning、self-critique, 外面再套一层 supervisor. 看起来高大上, 我跑了一段时间发现, 在我们这种业务上, 0.62 到 0.71 的提升里, 模型升级本身贡献了差不多三分之二. 框框的功劳远没有我们想的那么大.

这不代表工程没用. 工程的价值是在模型的波动里稳住下限. 我见过一个 0.85 → 0.52 的崩塌, 就是因为一次模型升级把 JSON 输出习惯改了, 一个 tool 解析挂了, 整条链路沉默了. 没人看日志, 周一才发现.

说几个我没在年初看清楚的点.

第一, context engineering 比 prompt engineering 更重要. 年初大家还在卷 prompt: "You are a helpful assistant that..." 写六十行 system prompt. 现在我自己的默认做法是, system prompt 留五行, 其他全靠工具拉、靠 memory 装、靠结构化压缩. 详细的 context 管理策略我单独写在 context-engineering 那系列, 这里不展开. 但我得说, 2025 年里我们项目提升最大的几次, 没一次是改 prompt 改出来的, 全是 context 结构调整.

第二, eval 不是 nice-to-have, 是 plumbing. 年初我以为 eval 就是跑个测试集看看分数. 现在我们组有个三人的 eval squad, 每天看 case, 每周跑 regression, 每月跟业务方过 rubric. 这块的方法论我也单独写在 AI Evals 那系列. Agent 没有 eval 等于裸奔, 这件事我是被坑过一次才认的.

第三, multi-agent 不是默认选项. 我们试过 supervisor、试过 peer-to-peer、试过 hierarchical, 大部分场景下, 单 agent + 好工具 + 强 context 比 multi-agent 强. multi-agent 那套东西真正适用的场景没想象中多. 工程怎么搭, 我写在 multi-agent in practice 那系列, 不在这重复. 但我得留一句忠告: 看到任何方案上来就搞 multi-agent 的, 我第一反应是他在 over-engineer.

这三个点, 就是这十二个月我交过最多学费的地方.

## 几个我盯着看的方向, 和我为什么没下注

接下来说几个我周围声音很大的方向, 以及我这边的判断.

第一个, Multi-modal Agent. 这个方向不用解释, 大家都在做. Anthropic 的 Claude 早就支持图像, OpenAI 把语音、视频、图像全塞进去了, Gemini 本身就是 multi-modal 训练. 我自己测下来, 对工程师最重要的是: tool 调用从 text-only 变成能"看到"屏幕、能"听到"声音. 我们有个内部 case, 让 agent 看着 Figma 截图调 UI, 准头比纯 description 高一截. 但这里有个坑我得提醒: multi-modal 看起来是能力扩展, 实际是 cost 翻倍. 我们有一段时间跑多模态评估, 一晚上烧掉 800 美金, 第二天被财务追着问. 跑 multi-modal agent 之前, 先算你钱包和你的延迟预算答不答应.

第二个, Agent Marketplace. 这是我相对乐观的方向. 想象一个 GitHub Actions 或者 Vercel 的 marketplace, 你能直接拉别人做好的 agent skill, 接进自己 agent. 我已经在用了, 类似 Anthropic 推的那套 skills 体系, 我们组内部也搞了个小 marketplace, 二十几个 skill, 谁都能引. 工程上, 这事的难点不是技能本身, 是技能发现的体验、版本管理、权限控制. 我自己的预期是, 2026 年这块会变成标配, 但 80% 的所谓 marketplace 都是泡沫, 真正有用的就那么十几二十个.

第三个, Agent OS. 这个词被滥用得我想打人. 不同人说的不是一个东西. 有人把它当 Copilot 的升级, 有人当 OS-level 的 agent shell, 有人拿去包装底层的 context + memory + tool 栈. Anthropic 的 Computer Use、OpenAI 的 Operator、Anthropic 的 Skills, 都被人贴过 Agent OS 的标签. 我个人的看法是: 真正的 Agent OS 还没出现. 现在所有号称 Agent OS 的东西, 要么是上面套壳 (在已有的 OS 上跑 agent), 要么是下面偷换 (拿 LLM 框架包装概念). 我赌的是, 真正有意思的 Agent OS 形态, 大概率不是从 agent 圈子里长出来, 是从 Apple、Google、Microsoft 这种 OS 厂商手里长出来. 我们这些 agent 工程师, 把它当个中间件栈用就好, 别当信仰.

第四个, 通用 Agent (General Agent / AGI Agent). 这个我不想多讲, 讲了就是站队. 我只说我看到的: 这两年最被吹的几个"通用 agent", 没有一个真通用. 都是某个领域的强项 + 一堆 fallback. 我自己的标准是, 一个 agent 是不是真的"通用", 看它在三个全新领域, 没有特别调优的情况下, 能不能跑过 0.5 的完成率. 目前的公开数据我没看到谁做到了. 我也没下注.

好, 我说一下我下注了什么. 一是 eval 体系, 二是 context 工程, 三是垂直 agent (而不是通用). 我身边做得比较稳的几个团队, 都在这三个点上. 至于那些把 banner 写满 AGI 的, 我看他们做项目没问题, 投钱我不跟.

## 我对 AGI 的看法, 和为什么不站队

我之前在 Reddit 跟一个老外吵过一架, 他说 2026 年 AGI 就到, 我说他想多了. 后来他想通了, 我也没改主意.

我自己的判断标准很工程师, 也很土: AGI 不是某个 benchmark 跑满分, 是它在没有专门 fine-tune 的情况下, 能拿到一个新领域的核心 KPI. 比如我现在抛一个我都没见过的小业务: 帮一家小律所审 100 个合同, 标出关键风险, 让真人律师过一遍, 准头多少. 如果通用 agent 真到了, 这种 case 准头应该自动上 0.85 以上, 不需要专门训练. 我赌现在做不到. 2026 年底? 我赌还做不到.

但这不耽误我吃饭. AGI 是不是 2026 年来, 跟我要不要现在好好做 agent, 是两件事. 说白了, AGI 来之前, agent 已经是一笔好生意. AGI 真来了, 我们的 skill 也不会贬值. 这是我不太参与"AGI 时间表"讨论的原因. 吵这事跟吵"明年房价"一样, 大多数人能押对的概率比抛硬币好不了多少.

我对 AGI 这事的态度, 是工程师对"还有点远的东西"的态度: 留个口子, 别押筹码.

我也想顺便说一个我越来越烦的毛病. 现在圈子里说话, 动不动就"这是 AGI 的一步", "这是走向 ASI 的里程碑". 工程师视角看, 这些话对做产品没用. 一个版本号提升 0.02, 在他们嘴里就变成了"质变". 我们做项目的, 应该按我们的本子过, 按 case 看, 按钱进帐看. 别被那帮人把心智带跑.

## 给工程师, 几条我现在能给的建议

我不会假装能给你未来一年的 roadmap, 但我有几条这十二个月我自己攒下来的, 你可以现在就用.

第一条, 把 eval 当 plumbing, 别当项目. 意思是, 别等"做完大模型升级"再想 eval. 第一天就铺, 哪怕手动跑 50 条 case. 一个 50 条的人工标注 set, 加上一个简单的 pass/fail, 比任何 fancy framework 都管用. 具体的 rubric 设计、怎么避免 overfit 到 eval set、怎么组 regression suite, 我写在了 AI Evals 那系列. 这里就一句: 你的 agent 没有 eval, 别上线.

第二条, 练 context engineering, 别在 prompt engineering 上死磕. 我不是说不写 prompt, 是说别指望 prompt 救你. context engineering 是 2025 年里回报率最高的工程投入, 没有之一. 怎么压、怎么切、怎么滑、怎么 loa, 我都写在 context-engineering 那系列了. 这里只说一个原则: 别写超过十行的 system prompt, 把剩下的交给结构化机制.

第三条, multi-agent 是高级工具, 不是默认值. 一上来就 supervisor + worker + critic, 大概率 over-engineer. 单 agent + 好工具 + 强 context, 能解决 80% 你想用 multi-agent 解决的场景. 什么时候才上 multi-agent? 问自己两个问题: 这事有没有天然的"边界"或"角色"可以切? 切完之后, 通信成本能不能被收益抵消? 两个都 yes, 上; 一个 yes, 再想想; 都是 no, 别上. 这块我整个 multi-agent in practice 系列都在讲, 这里不重复.

第四条, 学 MCP, 别只学 function calling. MCP 看起来是个协议, 实际是 2024 到 2025 之间最被低估的变化. Anthropic 推 MCP, 我一开始没当回事, 后来发现, 用 MCP 接工具跟手写 function calling 的差别, 像 Excel 跟 SQL 的差别. 我们把十几个内部工具统一改成 MCP server 之后, agent 接入新工具的开发时间从平均两天缩到两小时. 这个就是我下注的下一个标的方向.

第五条, 留个 note, 写着: 下一个版本号升级, 可能让我 agent 崩. 我自己摔过, 我们组的同事摔过, 每次升级都要做 regression, 都要做 prompt 锁版本, 都要做 A/B. 这个习惯比任何"prompt 技巧"都值钱.

最后说一句不那么技术的话. 我做 agent 这一年, 最大的感受是, 这个圈子是"未来已来"和"啥也不是"同时存在的地方. 一边是有人拿 agent 干实事赚钱, 一边是有人拿 AGI 讲故事融资. 我们这些工程师的位置, 是前者, 别跟后者跑.

我们这是这个系列的最后一章. 我后面会继续写下去, 但系列先到这. 下一系列叫 multi-agent in practice, 专门讲怎么把这个系列里讲的那些东西搭起来. 我们下一章见.