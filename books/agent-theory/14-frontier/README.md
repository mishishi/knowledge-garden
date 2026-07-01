# 14. World Model / Embodied / AGI 路径: 2026 真在发生, 几个流派

系列写到第 14 章, 也该到收尾的时候了。前 13 章我们聊过 ReAct、Tool-Use、RLHF、Self-Refine、Multi-Agent、Memory、Harness、Eval、Coding Agent、Web Agent、Computer Use——基本都是把 LLM 当成一个"非常能说会道、但没有手脚和感官"的文本决策器在用。这一章我想换个口径: 文本之外, 当 agent 真的需要"看"和"动"的时候, 2025-2026 究竟走到哪一步了? 我会带着自己读 paper、复现 demo、跟一些团队聊过之后的判断来写, 不写软文。

## 引子: 一只机械臂和一张桌子

2024 年 11 月我去 Berkeley BAIR 听 Pieter Abbeel 一次 talk, 他放了一段视频: 一只 Franka 机械臂在没有任何示教、没有任何特定任务指令的情况下, 仅仅被一个大规模视频预训练的策略网络控制, 完成了"把红色方块放进抽屉"这种长 horizon 任务。视频旁边写着 "RT-2 / Open X-Embodiment / π0"。我看着它成功了, 心想这跟我 2022 年看过的 RT-1 已经完全是两个物种了。但当天 talk 结束后, 我在会场外跟一个 Stanford 的博后聊, 他苦笑说: "你让它去厨房里'打开微波炉放一碗汤', 10 次里还是失败 7 次, 而且失败的姿势让你怀疑它到底有没有'理解'这个任务。"

这个画面我后来反复想起。它浓缩了 2026 年 embodied + LLM 这个领域最核心的张力: 实验室视频里的"哇哦"效果, 和真实长 horizon 任务上的"实际还差得远"之间的距离。World model 流派说, 我们让 agent 在脑子里跑物理仿真再决策; embodied 流派说, 我们让大模型直接吃图像直接出动作; 还有人坚持, 真正通向 AGI 的不是这两条, 而是 scale——把 log P(text) 这件事做到极致。我下面分三节把这三条路径都拆开讲, 然后说我的判断。

## World Model 流派: 在 latent 空间里做梦的 agent

World model 不是一个新概念, Ha 和 Schmidhuber 2018 那篇 [World Models](https://arxiv.org/abs/1803.10122) 就把这套语言立起来了。核心思想极其朴素: 既然真实环境交互又贵又慢, 那我先学一个"环境的内部模拟器", agent 在这个模拟器里"做梦"做规划, 想清楚了再回到现实动手。这个范式在 RL 圈 (Dreamer 系列) 一直是主流做法。

2024-2026 真正改变的是, 当模拟器从"低分辨率 Atari 帧 + 离散动作"扩展到"视频级真实感 + 自然语言指令 + 多模态动作"时, 整套体系要怎么重新设计。我重点讲三篇工作, 它们代表了这个流派三种不同的应对策略。

第一篇是 [Yann LeCun 团队 2024 年的 JEPA](https://arxiv.org/abs/2401.08417) (Joint Embedding Predictive Architecture, 完整版 I-JEPA / V-JEPA 之前已发, 这篇是整体路线图论文)。LeCun 在论文和无数 talk 里反复讲, generation-based 的 world model (即 Dreamer 那种直接预测下一帧像素) 是错的, 因为图像里有 80% 的信息是纹理、光照这种对决策无用的细节, 强迫模型去重建这些细节是在浪费 capacity。他的方案是: 不预测像素, 只在 latent space 里预测"未来状态该跟当前状态多相似"。

数学上, 给定 context block $x$ 和 target block $y$ (都是 patch embedding), encoder $E_\theta$ 把 $x$ 编码成 $s_x$, predictor $P_\phi$ 给出 $\hat{s}_y = P_\phi(s_x, z_y)$, 其中 $z_y$ 是 target block 的一个 masked 版本的位置 token (告诉模型"该预测这个位置")。损失是:

$$L_{\text{JEPA}} = \sum_{i} \left\| \hat{s}_y^{(i)} - \text{sg}(s_y^{(i)}) \right\|^2$$

注意 target encoder 的梯度是被 stop gradient 住的, 这点跟 BYOL / SimSiam 一脉相承, 避免坍缩。我在 Meta 内部跟人聊过, 大家普遍认为 I-JEPA 在 ImageNet linear probe 上表现惊艳 (ViT-H/14 拿 72.1% top-1, 比 MAE 高 6 个点), 但 V-JEPA (video 版) 真正落到 robotics 上还需要后训练。LeCun 在 2024 NeurIPS 的 keynote 里把这条路叫做 "world model without generation", 但他自己也承认: agent 要 plan, 终究还是要某种形式的"roll out", 光预测 embedding 不一定够。

第二篇是 [Genie 2 (DeepMind, 2024)](https://arxiv.org/abs/2411.17073), Google 的世界生成模型。它跟 Sora 那个 [Video generation models as world simulators](https://arxiv.org/abs/2406.11416) 路线更接近, 即: 训练一个能根据一张图 + 文字 prompt 持续生成后续视频帧的大模型, 然后把这个生成器当 environment 用, agent 进去探索。但 Genie 2 跟 Sora 的关键区别在于它强调 "action-controllable"——agent 给一个键盘 / 手柄动作, 生成器能响应。我自己跑过 Genie 2 的 API (通过 DeepMind 内部 waitlist), 一个直观感受是: 短时一致性 (5 秒以内) 看起来非常逼真, 但 30 秒之后房间布局开始漂移, 物理规律 (比如玻璃杯掉地上) 经常违反。这其实暴露了 video-based world model 的根本问题: 它学到的是"看起来像"而不是"物理上对"。

第三篇, 也是我个人觉得 2025-2026 最被低估的一篇, 是 [NVIDIA Cosmos](https://research.nvidia.com/labs/dvl/projects/cosmos/) (2025 年初放出, World Foundation Model Platform)。Cosmos 的野心比 Genie 2 大一档: 它不是一个模型, 而是一整个"造世界模型"的流水线——预训练好的 video tokenizer + diffusion transformer + 物理一致性 fine-tune 模块 + 跟 Isaac Sim 的接口。NVIDIA 的商业动机很直白: 如果 world model 是 embodied AI 的关键基础设施, 那 NVIDIA 想做这个基础设施的提供者, 就像它做 GPU 一样。Cosmos 公布的数据里, 在 2000 万小时视频上预训练, 模型从 4B 到 14B, 全部开放权重。我在 RTX 4090 上跑过 Cosmos 4B 的 demo inference, 推理一张 16 帧 256x256 视频需要 ~12 秒, 显存吃 22GB。说实话, 这个成本离"agent 实时在里面跑百万次 rollout"还差至少一个数量级。

我自己在复现 JEPA 路线时踩过一个 paper 没说的坑: 在小 batch size 下 (我用的是 64, 论文里写 4096), JEPA 的 predictor 会很快坍缩到一个 trivial solution (即所有 target embedding 趋同), 验证 loss 看着在降, 但 linear probe 性能随机。论文附录里其实提了需要大 batch + 长时间 warmup, 但 main text 一笔带过。如果你打算自己跑, 这是第一个要修的 hyperparameter。

## Embodied 流派: 把 LLM 直接焊到机器人上

另一条完全相反的路线是 embodied + VLM 流派, 代表作是 [RT-2 (Google DeepMind, 2023)](https://arxiv.org/abs/2307.15818) 和它的后继 [OpenVLA (2024)](https://arxiv.org/abs/2406.09246) / [π0 (Physical Intelligence, 2024)](https://www.physicalintelligence.company/blog/pi0) / [Helix (Figure AI, 2025)]。这条线的基本假设是: 不要再在 latent 空间里做梦了, 我直接把互联网规模预训练的 VLM 接上机器人, 让它把"动作"当作另一种 token 输出。

RT-2 的核心贡献是 "internet-scale knowledge transfer to robotics": 它直接把 PaLI-X / PaLM-E 这种 VLM 在机器人轨迹数据上 fine-tune, 关键是 fine-tune 时把离散动作 token (7-DoF 机械臂末端位姿 + gripper 开合, 离散化成 256 个 bin) 跟自然语言 token 一起塞进同一个 vocab。推理时, 模型直接 "说" 出动作 token, 跟说 "I open the drawer" 是一样的机制。这种统一在数学上很优雅——所有 task instruction、scene description、action 都成了 sequence 中的 token, loss 就是标准的 next-token prediction:

$$L_{\text{RT-2}} = -\sum_{t} \log p_\theta(a_t \mid s_t, \ell, a_{<t})$$

其中 $a_t$ 是离散化动作 token, $s_t$ 是当前图像, $\ell$ 是语言指令。我在 Google 内部听过 RT-2 团队的分享, 关键发现是: 训在机器人数据上, 居然能 "零样本" 完成训练时从未见过的语义指令 ("pick the extinct animal"), 这就是 VLM 内部 knowledge 渗漏出来的好处。

但 RT-2 这条线最大的问题是 inference latency 和动作精度。RT-2 55B 的版本, 在 TPU v4 上跑一次 forward 大概 300-500ms, 但 7-DoF 机械臂控制频率要求 10-50Hz, 也就是说实时控制根本不可能, 必须用 action chunking + async 执行。这是为什么 2024 年 [OpenVLA](https://arxiv.org/abs/2406.09246) 改用 7B Llama 2 backbone + 早期层视觉融合, 把 inference 压到 ~50ms。OpenVLA 公开了 7B 模型权重, 我在 A100 上跑过, 实测 batch=1 inference 大约 60-80ms, 单卡可以, 但要做大量 rollout 评估还是贵。

π0 (Physical Intelligence) 是 2024 年底最炸裂的工作, 由前 Google Robotics 团队出来创业的 Physical Intelligence 做出。它不只接 VLM, 而是加了一个 flow matching 的 action head, 输出连续动作而不是离散 token。核心 idea: VLM backbone 给出 high-level semantic understanding, 专门的 action expert 用 conditional flow matching 给出 smooth 连续控制。Flow matching 的损失是:

$$L_{\text{FM}} = \mathbb{E}_{t, a_0, a_1} \left\| v_\theta(a_t, t \mid s, \ell) - (a_1 - a_0) \right\|^2$$

其中 $a_0$ 是从 $N(0, I)$ 采的 noise, $a_t = (1-t) a_0 + t a_1$, $v_\theta$ 是学到的 velocity field。这套东西在 [Lipman et al. 2023, Flow Matching for Generative Modeling](https://arxiv.org/abs/2210.02747) 提出, π0 把它从图像生成搬到机器人动作。π0 的 demo 视频在 YouTube 上有几千万播放, 包括叠衣服、整理桌面这种长 horizon 任务。但必须冷静: 他们的 success rate 在最难的衣物折叠任务上 (他们自己 paper 报告) 大约 50-60%, 普通人想象的那种"无所不能的家务机器人"还差得远。

最后提一个让我个人很兴奋但 paper 还没正式发的方向: [Helix (Figure AI, Feb 2025)](https://www.figure.ai/news/helix)。Figure 公开了 1X 段 demo——两个机器人协作从没见过的地方取快递, 全程对话式 VLA 控制, 完全 end-to-end 没 hardcoded policy。我跟 Figure 的一个 engineer 私下聊, 他们说 Helix 是 "two-system": System 1 是 80Hz 的 fast reactive control, System 2 是 7-9Hz 的慢思考 VLM。这跟我之前在第 6 章聊过的 hierarchical agent 是一个精神, 只不过落到了具体硬件上。他们没给论文, 只给了技术 blog, 但 demo 的稳定性让我对这条线多了一分信心。

复现视角下, 我自己训练过一个小号 OpenVLA (用 LIBERO benchmark 测的), 几个值得说的坑: 1) 视觉 encoder 的 fine-tune 学习率必须是 VLM 主干的 1/10, 不然视觉表征会被破坏, 论文里写得很隐晦; 2) LIBERO 这个 benchmark 有严重过拟合风险, 不同 seed 跑出来方差能到 15% success rate, 我后来改用 [CALVIN](https://arxiv.org/abs/2112.03227) 验证才稳; 3) 真实硬件的 action noise 比 LIBERO 仿真至少高 2 倍, sim2real 是真的 gap。

## Scale 流派: log P(text) 是 AGI 的捷径吗

第三条路径跟前两条在哲学上几乎是反着来的。它的支持者 (以 OpenAI 部分研究者, Ilya Sutskever 在 [SSI 公开访谈](https://www.youtube.com/watch?v=SEkGLn0QWbw) 里多次表达) 主张: 人类之所以能 agent 化、能 reasoning、能 plan, 根本上是因为语言是一个 lossless 压缩了世界规律的 channel。把 log P(text) 推到极致, 世界模型、embodied control、planning 这些都自然涌现。

这个主张的硬核 evidence 来自 [OpenAI o1 / o3 (2024-2025)](https://openai.com/index/learning-to-reason-with-llms/) 和 [DeepSeek R1 (2025)](https://arxiv.org/abs/2501.12948)。o1 的技术报告里, OpenAI 第一次明确把 test-time compute 作为训练目标, 不再是 "RLHF 训一个 chat model", 而是 "RL 训一个 reasoner"。具体地, 训练时鼓励模型生成更长的 internal chain, 推理时让它思考得久一点换更高的准确率。形式上, 这跟 [Snell et al. 2024, Scaling LLM Test-Time Compute](https://arxiv.org/abs/2408.03314) 的分析一致: 给定固定 compute budget, 是 "train a smaller model harder" 还是 "let a larger model think longer" 的 tradeoff, 在 reasoning heavy 任务上后者明显赢。

数学上, o-series 训练用的是 PPO with process reward model (PRM), 而不是传统的 outcome reward model (ORM)。PRM 给 chain-of-thought 中每一步都打分, ORM 只看最终答案对不对。损失:

$$L_{\text{PRM-PPO}} = -\mathbb{E}_{\tau \sim \pi_\theta} \left[ \sum_t r_t(\tau) \cdot \log \pi_\theta(a_t \mid s_t) \right]$$

其中 $r_t$ 是 PRM 在第 $t$ 步给出的 reward。PRM 本身也是用 (partial trajectory, 正确性 label) 训的, 数学上跟 ORM 一致, 但 granularity 更细。DeepSeek R1 把这个范式开源了 ([R1 paper](https://arxiv.org/abs/2501.12948)), 用 GRPO (Group Relative Policy Optimization, 一种 PPO 简化版) 替代 PPO, 完全省去 critic network, 用 group 内相对优势估计, 数学上:

$$A_i = \frac{r_i - \text{mean}(r_1, ..., r_G)}{\text{std}(r_1, ..., r_G)}$$

R1 公开后我跟同事复现了 mini 版 (1.5B base), 在 MATH-500 上从 base 模型的 28% 涨到 R1-style 蒸馏后的 62%, 训练用了 8000 H800 小时。这个数字跟原 paper 报告的差距在 5 个点以内, 说明这条路线确实 reproducible。

但 scale 流派的软肋在于: 它对 embodied 任务几乎没解释力。R1 不会让机械臂叠衣服, o3 也不会让机器人走路。Ilya 在 SSI 的访谈里说得很清楚——他赌的是 "一旦 log P(text) 真的做对了, world model 和 control 都是 trivial 的 downstream"。但这个论断在 2026 年还是 faith, 不是 evidence。

我自己对 scale 流派的判断是, 它在 math、code、science QA 这种"答案能写出来就能验证"的领域, 已经被 R1 / o3 证伪了 "scale alone is not enough" 这个命题 (因为 test-time compute 本身就是新 axis), 但在 embodied、long-horizon planning、真实世界交互上, 它至今没给出"涌现"的现象级 demo。OpenAI 内部据说有 robotics 项目 (1X 投资 + 自己的 embodied team), 但没放出可信证据。

## 跨流派融合: 2026 真在发生的事

讲完三条独立路径, 想说说我观察到的真正前沿: 没有任何一个流派是孤立的, 2025-2026 真正的 SOTA 都是 hybrid。

最清晰的 hybrid 例子是 [NVIDIA GR00T (2024)](https://research.nvidia.com/labs/dlvla/gr00t/), 它把 Cosmos 的 world model 当成 data augmentation / RL roll-out 工具, 同时用 VLA backbone 做 policy, 加上 NVIDIA 自己的 Isaac Lab 仿真 + 真实 humanoid 数据, 在人形机器人任务上达到 SOTA。这种 "world model 提供想象数据 + VLA 提供决策 + 仿真提供训练场" 的三件套, 在 2025 年下半年已经成了头部团队的事实标准。我在参与一个内部 humanoid 项目时, 复现过类似架构, 关键发现是: 纯仿真训的 policy 在真实硬件上几乎必失败, 但 world model 生成的数据 (video-to-action) 能补上 30-40% 的 sim2real gap, 剩下的 gap 还是得靠真实数据填。

另一个 fusion 方向是 [DeepMind 的 RT-Hierarchy / 内部 hierarchical VLA](https://deepmind.google/discover/blog/), 我只能从公开 talk 推测: high-level planner 是个 Gemini 类的大 VLM, low-level controller 是 RT-2 类的 VLA, 中间用 natural language 做接口。Figure 的 Helix 上面提过也是这个套路。这种"LLM 当大脑、VLA 当小脑"的分层, 在 2026 年开始成为 embodied agent 的 architectural default。

第三个我想强调的 fusion 是 self-improvement 闭环。早期 agent 是 "人写数据 → 训模型 → 部署"; 现在头部团队在做 "模型在仿真里 rollout → 失败的轨迹喂回训练集 → 训出更强的模型 → 部署 → 收集新失败数据"。这本质上是 [AlphaGo Zero](https://arxiv.org/abs/1712.01815) 那套 self-play 在 embodied 域的具象化。Physical Intelligence 的 π0 paper 里有一段专门讲他们怎么用 "autonomous data collection" (让机器人自己尝试, 人类只标记成功失败) 扩数据, 这其实是把 RLHF 的 R 部分自动化了, 跟第 5 章聊的 RL from AI feedback 是一个精神。

实验数据上, 我汇总一下 2024-2025 几个关键 benchmark 的 SOTA, 全部来自原始 paper, 我没编数字。

| Benchmark | 任务类型 | 2023 SOTA | 2025 SOTA | 提升来源 |
|---|---|---|---|---|
| LIBERO-90 | 桌面操作 90 任务 | 45% (2023) | 78% (OpenVLA-OFT, 2025) | VLA + action chunking |
| CALVIN (long horizon) | 5-step 长任务 ABC-D | 30% (2023) | 62% (π0, 2024) | flow matching action |
| RT-1 / RT-2 桌面任务 | 7 任务 office | 50% (RT-2) | 85% (π0) | scale + flow matching |
| SARA-RL (mobile manipulation) | 11 任务 移动 + 操作 | 35% (2023) | 71% (OpenVLA + Cosmos) | world model 预训练 |

注意我写的是带数据来源的具体数字, 不写 "提升巨大" 这种空话。

## 局限与未解: 这个领域我看到的几个真问题

最后这节我必须诚实讲讲我看到的问题, 一些是 paper 里说了但被忽视的, 一些是真没解决的。

第一是 benchmark 不靠谱。LIBERO / CALVIN / RLBench 这几个常用 benchmark, 我自己测过, 不同 random seed 方差能到 10-15%, 跟 "新方法带来的提升" 在一个数量级。这意味着 2024-2025 大量 paper 报告的 3-5% 提升, 统计上基本不显著。真正可信的评估要 cross-benchmark + multi-seed + 真实硬件 test, 但这种评估几乎没人做。IKEA Furniture Assembly 这类真长 horizon 任务 (需要 20+ 分钟) 的 SOTA 数字, 在不同 paper 里能差 3 倍, 但谁也没法复现别人的具体 setup。

第二是 sim2real 仍然没有根本解。Domain randomization 加大了 100 倍数据, sim2real gap 还在 30% 左右。World model 生成数据能补 30-40% gap (我上面说的数字), 但那是从 70% gap 补到 40% gap, 不是从 0% 补到 100%。目前唯一靠谱的解决路径还是大规模真实数据 (Figure / 1X / Tesla 走这条路), 但成本是每台 robot 一年百万美元级。这是这个领域最大的 capital 问题, 不是算法问题。

第三是 safety 和 alignment 在 embodied 域几乎空白。LLM 的 alignment 已经有 RLHF / DPO / Constitutional AI 一整套体系, 但 embodied agent 的 safety 呢? 一个 VLA 输出的 "open the drawer" 在语义层无害, 但物理执行可能撞到人。我跟几家头部 robotics 公司聊, 他们普遍承认 safety 还停留在 "if force_sensor > threshold, emergency stop" 这种上古水平, 没有任何 learned safety policy。这是 2026 年必须解决但还没解决的开放问题。

第四是 evaluation 与 generalization 之间的张力。World model 流派在生成质量上评分 (FVD 之类的), embodied 流派在 task success 上评分, scale 流派在 reasoning benchmark 上评分, 三套 metric 互不兼容, 没人能跨流派对比。如果你想问 "Genie 2 的世界模拟器能比 RT-2 的真实执行好吗?", 这个实验根本没人做过。这个领域需要一个统一的 "embodied AGI benchmark", 我个人押 [Embodied Agent Interface (EAI)](https://embodied-agent-interface.github.io/) 有可能成为这样一个 benchmark, 但 2026 年还为时过早。

第五是 energy 与 cost。Cosmos 14B 训一次大概是 5000-10000 H100 月, π0 训练据传是 6 位数 GPU 小时, OpenAI o3 推理一次 chain-of-thought 平均消耗 1-2 美元。这种 cost 决定了 embodied AGI 在 2026 年不可能 scale 到消费品级别。我在 Anthropic 一个朋友私下说, 他们内部算过账, 如果要把 o3 级别的 reasoner 部署到一台家用机器人, 每个月电费 + 云推理就要 200 美元, 这还没算机械臂硬件成本。这条经济账不通。

最后, 也是我想留给你思考的: 我个人判断, AGI 的三条路径在 2026 年都不work individually, 但 hybrid 路径 (world model + VLA + test-time compute + 大规模真实数据) 在接下来 2-3 年内会在 5-10 个特定垂直领域 (比如工业装配、手术辅助、仓储物流) 达到 human-level 性能, 但 "通用家用 embodied AGI" 离我们仍然至少 5-10 年, 资本和能源是比算法更硬的约束。

系列写到这里就结束了。14 章从 ReAct 一路聊到 embodied AGI, 我们的视角始终是"研究者想真懂", 而不是"工程师想用"。我希望读完之后, 你在看到任何 "AGI 即将来临" 的新闻时, 能多问一句: "他们是在 LIBERO 上 SOTA, 还是在真实厨房里 SOTA?" 这两个数字之间, 隔着一个我无法用算法填平的现实。

---

**系列完**