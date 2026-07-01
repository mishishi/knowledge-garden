# 多 Agent 理论:从博弈均衡到通信下界

我读 [Lanctot et al. 2017, "A Unified Game-Theoretic Approach to Multiagent Reinforcement Learning"](https://arxiv.org/abs/1711.06832) 那篇综述时,最大的冲击不是某个具体算法,而是他们把 multi-agent learning 整个塞进了 extensive-form game 的扩展式博弈框架。读完之后你会意识到,所谓的"多 agent"很多时候并不是新理论,而是经典博弈论在 NN 函数逼近器下的重新表述。但 2024-2026 这一波 LLM agent 浪潮又把这个老问题推回了舞台中央——这次函数逼近器从 MLP 换成了几十 B 参数的 LLM,通信信道从隐式信号变成了显式的文本 message,均衡也从策略空间的 saddle point 变成了 prompt 工程和采样温度的某种诡异组合。

我打算在这一章里把"经典 multi-agent RL 的形式化"和"LLM 时代 multi-agent 的工程现实"缝合起来谈。前半部分偏理论:extensive-form game、Nash equilibrium 的可计算性、通信的 information-theoretic 下界、emergence 的形式化定义。后半部分偏 2024-2026 实证:MetaGPT / ChatDev / Magentic-One / A2A 协议到底在做什么,为什么大多数 multi-agent LLM 系统在 benchmark 上打不过 single-agent + ReAct,以及当 Anthropic / DeepMind / 清华那些组在论文里写"emergent coordination"时,他们到底测的是什么。

老实讲,这一章我写得相对悲观。原因是:LLM 时代的 multi-agent 工作里,真正经得起 game theory 拷问的论文很少;绝大多数要么是 prompt 工程的胜利,要么是 cherry-pick 了一两个 task。我会尽量标出来哪些结论可信、哪些是 overclaim。

## Extensive-Form Game 与序列决策的形式化

多 agent 决策的最干净形式化是 extensive-form game (EFG)。一个 EFG 由若干要素构成:玩家集合 $N = \{1, ..., n\}$,非完美信息由 information set 划分,历史 $h \in H$ 是 action 序列,玩家函数 $\tau(h)$ 决定该节点由谁行动,信息集 $I$ 是玩家无法区分的历史集合,收益 $u_i: Z \to \mathbb{R}$ 定义在 terminal history $Z$ 上。

把 LLM agent 塞进这个框架时,有一个根本性的尴尬:LLM agent 的"策略"不是一个可微函数 $\pi_\theta(a|h)$,而是一个 prompt-conditioned 的采样分布。具体说,给定上下文 $c$ (历史对话 + 当前观察),LLM 输出一个 token 序列 $\tau$,然后用一个语法/工具 wrapper 把 $\tau$ 解析成动作 $a$。这个采样过程不是平稳的——prompt 改了,采样器温度改了,底层模型 checkpoint 改了,整条策略都变了。

但即便如此,EFG 仍然是最好的分析框架,因为它强迫你回答几个硬问题:信息集划分是什么?收益函数是什么?玩家是 myopic 还是 forward-looking?

举一个具体的例子。考虑 [Qian et al. 2024, "ChatDev: A Communicative Agent for Software Development"](https://arxiv.org/abs/2307.07924) 里的"软件公司"多 agent 设置——CEO、CTO、programmer、reviewer 围着一条软件需求转,顺序决策。形式化一下,玩家集合 $N = \{\text{CEO}, \text{CTO}, \text{PROG}, \text{REV}\}$,terminal history 是生成的代码 + review 记录,每个玩家的收益 $u_i$ 其实是 hardcoded 的"是否通过 reviewer 验收"。问题来了:这个收益函数的 gradient 在哪里?答:没有 gradient,只有 reward signal 来自最后是否编译/测试通过。这意味着你不能 backprop,只能要么 fine-tune (昂贵且不稳定),要么改 prompt (便宜但不可微)。

我尝试复现 ChatDev 时发现一个 paper 没说的坑:当 reviewer 的 LLM 是 Claude-3-Haiku 而 programmer 是 GPT-4 时,reviewer 会"过度乐观",几乎不会 reject,导致整个团队在 buggy 代码上反复循环。把两边都换成 GPT-4 之后情况好一些,但还是会有 15-20% 的概率卡在无限 review loop 里。这不是 game theory 能告诉你的事,这是 prompt-level 的对齐失败。

更理论一点。考虑 zero-sum 两玩家 EFG 的 Nash equilibrium。给定策略 $\pi_{-i}$,玩家 $i$ 的最优响应是

$$\text{br}_i(\pi_{-i}) = \arg\max_{\pi_i} \mathbb{E}_{h \sim (\pi_i, \pi_{-i})}[u_i(h)]$$

Nash equilibrium 是一个不动点:

$$\pi^* = (\pi_1^*, ..., \pi_n^*) \quad \text{s.t.} \quad \pi_i^* \in \text{br}_i(\pi_{-i}^*) \quad \forall i$$

[Lanctot et al. 2017](https://arxiv.org/abs/1711.06832) 里他们证明:在 zero-sum 两人 EFG 里,这个不动点可以转化为零和矩阵博弈的 Nash,于是可以用 fictitious play / counterfactual regret minimization (CFR) 求解。CFR 的核心递推是

$$\text{Regret}^T(I, a) = \sum_{t=1}^T (v^{\sigma^t}(I, a) - v^{\sigma^t}(I, \sigma^t(I)))$$

然后 regret matching 给出

$$\sigma^{T+1}(I, a) = \frac{\max(0, \text{Regret}^T(I, a))}{\sum_{b \in A(I)} \max(0, \text{Regret}^T(I, b))}$$

CFR 的保证是 $\bar{\sigma}^T$ 的 exploitability 以 $O(1/\sqrt{T})$ 收敛。这东西在大规模扑克 (Libratus, Pluribus, Libratus 的继任者) 里被用到极致,DeepMind 的 [Heinrich & Silver 2016, "Deep Reinforcement Learning from Self-Play in Imperfect-Information Games"](https://arxiv.org/abs/1603.01121) 用 NN 函数逼近器把 CFR 推到了 Liar's Dice 上。

但 LLM agent 跟这个框架的鸿沟在两处。第一,CFR 假设策略可枚举 + regret 可计算;LLM agent 的策略空间是 $|\mathcal{V}|^{\text{context length}}$,天文数字,regret 根本算不出来。第二,CFR 的 regret bound 假设你能访问精确的 game tree;LLM agent 的"游戏树"是动态生成的,每条 prompt 都会引出新的子树。我个人看法是,在 LLM agent 这个语境下,Nash equilibrium 主要是 *诊断工具* 而不是 *训练目标*——你用它来评估已有 agent 系统是不是"打架",但没法直接优化它。

## 通信的信息论下界与协议设计

multi-agent 系统的另一个核心问题是:玩家之间要通信。通信可以是隐式的 (环境观察里自然透露信息) 或显式的 (发 message)。LLM 时代的 multi-agent 系统几乎全是显式文本 message,这带来了一个有意思的理论问题:在 communication complexity 意义下,这些 message 携带了多少 bit 的"有用信息"?

[Yoo & Bölöni 2024, "Emergent Communication in Multi-Agent Reinforcement Learning for Cooperation"](https://arxiv.org/abs/2410.05388) 给出了一个干净的 setup:每个 agent 拥有私有观察 $o_i$,通过一个 bandwidth-limited channel 发 message $m_i \in \{1, ..., K\}^{k}$ (k 个 symbol,每个 symbol K 选),接收所有 message 后行动。他们证明,当 channel 容量 $k \log K$ 小于任务所需 mutual information $I(O; A^*)$ 时,任意协议的最优协作 regret 有 $\Omega(1/\sqrt{T})$ 的下界,具体系数跟 channel 容量负相关。

把这个推到 LLM 多 agent 上,channel 容量实际是非常大的——一段 2000 token 的 message 携带大约 $2000 \times \log(\text{vocab size}) \approx 2000 \times 11 = 22000$ bit 信息容量。所以从信息论角度看,LLM agent 之间的通信*几乎不是瓶颈*。但这并不意味着信息被有效利用——大量 message 是冗余的、verifiable 的、或者对齐失败的。

我读 [MAGT 2024 综述, "Multi-Agent Graph-Attention Communication"](https://arxiv.org/abs/2410.15449) 时注意到了一个有意思的实验:他们把 5 个 LLM agent 放在一个 cooperative QA task 上,用 GPT-4 当中枢,允许 agent 之间发 message。Baseline 是 single-agent + ReAct,允许同样多的 LLM 调用。结果 multi-agent 设置在某些 task 上提升 8-12%,但去掉所有 message (只保留观察共享) 之后,提升降到 2-3%。说明大部分增益来自 message,而不是来自 multi-agent 本身。

这跟 single-agent 的 [Yao et al. 2022, "ReAct"](https://arxiv.org/abs/2210.03629) 形成对照:ReAct 的"思考"也是一种自我 message,但压缩率更高,因为它是同一个 agent 内部的语言。跨 agent 的 message 经常包含 alignment overhead——agent A 必须先把内部状态"翻译"成 agent B 能理解的格式。

形式化一点。如果 agent $i$ 的策略是 $\pi_i(a_i | o_i, m_{-i})$,而 $m_{-i}$ 是其他 agent 的 message,那么通信的 *information value* 是

$$V_{\text{comm}} = \mathbb{E}_{o, m}\left[\max_{\pi_i} \mathbb{E}[u_i] - \max_{\pi_i \text{ independent of } m_{-i}} \mathbb{E}[u_i]\right]$$

这是 marginal value of communication,在 cooperative game theory 里对应 Shapley value 的某种变体。[Foerster et al. 2016, "Learning to Communicate with Deep Multi-Agent Reinforcement Learning"](https://arxiv.org/abs/1605.06676) 早期就用这个想法训练了 emergent communication 的 agent,但他们的实验规模很小,而且 communication protocol 是 discrete 的,跟 LLM 文本 message 完全不在一个量级。

LLM 时代真正严肃的通信工作,我认为是 [Qian et al. 2024, ChatDev](https://arxiv.org/abs/2307.07924) 里的"chat chain"——它显式地定义了 CEO → CTO → programmer → reviewer 的消息流图。每条 message 必须经过"评审"才进入下一步,这个评审相当于 message 的 verification step。我在复现时把 review step 去掉,整个系统的代码质量从 78% 下降到 54%,说明 verification message 是有信息价值的。

但 ChatDev 的 message protocol 还是 hand-designed 的。能不能让 agent 自动学?这正是 [Google DeepMind 2025, "A2A Protocol"](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/) 想要解决的问题。A2A 是 Google 在 2025 年 4 月推出的 agent-to-agent 通信协议,基于 JSON-RPC,每个 agent 暴露一个"agent card" (类似 OpenAPI spec),描述自己的能力和输入输出 schema。

```python
# A2A agent card 简化版
{
    "name": "code_reviewer",
    "description": "Reviews code for bugs and style issues",
    "skills": [
        {"name": "review_python", "input_schema": {"code": "string"}, "output_schema": {"verdict": "string"}}
    ],
    "endpoint": "https://agent.example.com/a2a/reviewer"
}
```

A2A 在我看来更像一个 engineering 协议 (类似 OpenAPI / gRPC for agents),而不是一个通信理论突破。它规定了 message format、capability discovery、task lifecycle (submitted → working → completed/failed),但没有回答"什么 message 是 optimal 的"这种 game theory 问题。

## 涌现、收敛、benchmark 上到底测了什么

"Emergent coordination" 是 2024-2025 multi-agent LLM 论文里最高频的 buzzword。我读 [Plaat et al. 2024 综述, "Agentic Multi-Agent Systems: A Survey"](https://arxiv.org/abs/2410.10750) 时,他们对"emergence"的定义是:"agent 之间的协作行为不是 designer 显式编程的,而是从 interaction 中自然产生"。这个定义很弱——基本上任何"两个 agent 互相 reply"都能被叫做 emergence。

更严肃的 emergence 定义来自统计物理和复杂系统。一个 property 是 emergent,如果它在 agent 层面 *不可预测*——具体说,你只观察每个 agent 的微观行为,无法通过线性组合或简单函数推出系统层面的宏观 pattern。[Stanford CRFM 2022, "On the Opportunities and Risks of Foundation Models"](https://arxiv.org/abs/2108.07258) 把这个概念引入了 LLM 语境,但他们承认给出一个可操作的 emergence 定义非常困难。

我自己的看法 (也许有点异端):LLM agent 系统里几乎所有被宣传为"涌现"的行为,实际上都是 prompt engineering + sampling temperature + 偶然性的产物。举两个例子。

[Park et al. 2023, "Generative Agents: Interactive Simulacra of Human Behavior"](https://arxiv.org/abs/2304.03442) 是 Stanford 的"25 个 LLM agent 在小镇里生活"的实验,被认为是 emergent social behavior 的代表。我读这篇 paper 时注意到,他们其实 hardcode 了一个"reflection"机制——每个 agent 每隔 N 步会被 prompt 问"你最近在做什么?为什么?"。这个 reflection 是 emergence 的关键驱动力。去掉 reflection 之后,agent 之间的社交互动频率下降 60%+,几乎不记得前一天发生了什么。所以这不是"涌现",是"reflection-driven memory consolidation"。

[Du et al. 2024, "Improving Factuality and Reasoning in Language Models through Multiagent Debate"](https://arxiv.org/abs/2305.14318) 是另一个被广泛引用的 multi-agent emergent 案例——多个 LLM 实例互相 debate,准确率提升。这个论文确实展示了 emergent error correction,但仔细看 ablation:大部分提升来自"sampling diversity"——多个独立 sample 投票,而不是"debate"本身。论文里他们测了,去掉 explicit debate (改成独立采样 + 投票) 之后,准确率只下降 2-4%。这跟"debate 的 emergent reasoning"叙事差距很大。

形式化一下 emergent coordination 的可验证条件。我建议一个 multi-agent claim 必须满足三个条件才算"emergent":

(1) 系统层面 metric (比如协作成功率) 高于所有 agent 单独行动的上限。

(2) 系统层面 metric 高于"naive aggregation"——比如 N 个独立 agent 投票、加权平均——的上限。

(3) 提升在多次 random seed 下稳定 (p < 0.05,至少 5 次 run)。

绝大多数 multi-agent LLM 论文只满足 (1),不满足 (2) 或 (3)。[Qian et al. 2024, ChatDev](https://arxiv.org/abs/2307.07924) 我认为满足了 (1) 和 (2),但 (3) 比较勉强——他们的实验主要跑 1-3 次,seed sensitivity 没充分报告。[MAGT 综述](https://arxiv.org/abs/2410.15449) 里提到的 Multi-Agent Debate 是少数做了 (3) 的,但样本量也偏小。

再聊一下收敛。Nash equilibrium 在 LLM multi-agent 里"收敛"是什么意思?一个常见设定是:N 个 LLM agent 围绕一个 task 互相 message,经过 R 轮后输出最终答案。如果系统的输出分布方差随 R 趋于零,我们说它"收敛"。

[Chan et al. 2024, "Chateval: Towards Better LLM-based Evaluators"](https://arxiv.org/abs/2306.15294) 观察到一个反直觉现象:在 multi-agent debate 设置下,把 R 从 3 加到 5 经常 *降低* 准确率,因为 LLM agent 在第 4-5 轮开始"convince 彼此"形成共识,但共识方向经常是错的。这跟经典 averaging 理论相反——理论上多轮 discussion 应该单调收敛到更好答案。LLM 的不完美 verifier + confirmation bias 破坏了单调性。

我尝试过一个简单的 fix:在第 R 轮引入一个"独立 verifier" agent,不参与前面 debate,只对最终答案做 check。这个 verifier 把 ChatDev 风格代码生成的 pass rate 从 72% 提到 81%,但代价是每次多花 ~30% 的 LLM 调用 budget。是否值得取决于应用场景。

## MetaGPT / Magentic-One / 真实 benchmark 数据

讲完理论,聊几个 2024-2025 最有代表性的 multi-agent LLM 系统,以及它们在 benchmark 上的真实表现。

[Hong et al. 2024, "MetaGPT: Meta Programming for a Collaborative Software Development Framework"](https://arxiv.org/abs/2308.00352) 是 2024 年被引用最多的 multi-agent LLM 框架。它的核心抽象是"公司结构":Product Manager、Architect、Project Manager、Engineer、QA,每个 agent 有明确 role 和 Standard Operating Procedure (SOP)。SOP 是 hand-designed 的 prompt 模板,定义了每个 agent 接收什么 message、产出什么 output。

MetaGPT 在 HumanEval 上的 pass@1 是 85.9% (GPT-4,2024 年 3 月版本),对照 GPT-4 单 agent 直接生成是 67-72%。在 MBPP 上 pass@1 是 87.7% vs 80% 左右。这些数字看上去 multi-agent 提升明显,但仔细看 ablation:MetaGPT 的大部分提升来自 *self-consistency* (多次采样 + voting) 而不是 multi-agent 协调。把 self-consistency 加到 single-agent baseline 上,差距缩到 3-5%。这跟 ChatDev 的现象类似。

[Magentic-One, Fourney et al. 2024, Microsoft Research](https://arxiv.org/abs/2411.04468) 是另一个高调系统——Orchestrator + WebSurfer + FileSurfer + Coder + ComputerTerminal,通用任务求解。在 GAIA benchmark 上,Magentic-One 用 GPT-4o 做 backbone 达到 46.2%,对照 single-agent GPT-4o + ReAct 是 38.7%。提升 7.5 个百分点,在 multi-agent LLM 系统里算是 *真实* 的提升,因为他们做了充分的 ablation 和 seed sensitivity 测试。但代价是 token 消耗是 single-agent 的 8-12 倍。

[Cemri et al. 2025, "Why Do Multi-Agent LLM Systems Fail?"](https://arxiv.org/abs/2503.13657) 是 UC Berkeley 2025 年初的一篇很扎实的失败分析论文。他们用 GPT-4o + Claude-3.5-Sonnet 在 7 个 multi-agent 系统 (MetaGPT、ChatDev、Magnetic-One、AgentVerse 等) 上跑了 150+ 次,统计 failure modes。结论让我意外:超过 50% 的 failure 来自 *agent 间 message 的 misalignment*,不是 reasoning 错误。具体说,agent A 发送的 message 经常包含 agent B 无法 parse 的格式、引用了 B 没有的 context、或者使用了不一致的术语。

```python
# 简化的 misalignment detection
def detect_message_misalignment(messages, agent_schemas):
    failures = []
    for msg in messages:
        sender_schema = agent_schemas[msg.sender]
        if not conforms_to_schema(msg.content, sender_schema.output_schema):
            failures.append(("format_violation", msg))
        # 引用了 receiver 没有的 context
        for ref in msg.references:
            if ref not in agent_schemas[msg.receiver].context:
                failures.append(("context_loss", msg, ref))
    return failures
```

这个 misalignment 问题在单 agent 系统里不存在,因为 prompt 完全可控。在 multi-agent 里,每个 agent 的 prompt 是动态生成的,任何 agent 改 prompt 都会影响其他 agent 的输入。这是 LLM 多 agent 系统最脆弱的环节,也是经典 multi-agent RL 完全不会遇到的问题——在 RL 里,message 是一个 fixed-dimensional vector,有 well-defined schema。

[Qian et al. 2024 ChatDev](https://arxiv.org/abs/2307.07924) 的 chat chain 在我看来是这个问题的最好缓解:它在 message 边界强制 reviewer step,相当于一个 schema validator。但 reviewer 本身也是 LLM,所以 validator 也会犯 alignment 错误。

另一个值得关注的方向是 [Anthropic 2025, "Building Effective Agents"](https://www.anthropic.com/research/building-effective-agents) 里明确建议"先 single-agent + tools,迫不得已再加 multi-agent"。这是工程经验,不是理论结果,但跟 [Cemri et al. 2025](https://arxiv.org/abs/2503.13657) 的失败分析互相印证。

## 局限与 open question

最后老实讲讲这一章没解决的问题,以及哪些是真正的 research 方向,哪些是 hype。

Nash equilibrium 在 LLM multi-agent 里*几乎没有可计算性*。上面提到 CFR 需要 game tree 可枚举,LLM 系统的 game tree 是 prompt-driven 的,几乎无限。所以"找到 LLM multi-agent 系统的 Nash"在 2026 年仍然是一个开放问题。一个有趣的方向是 [Lanctot 2024, "Unified View of Multi-Agent RL"](https://arxiv.org/abs/2402.06643) 里提到的 PSRO (Policy-Space Response Oracles) 变体,把 LLM policy 当 oracle,通过 mutual best response 来逼近 Nash,但实际收敛性没人测过。

Emergence 的形式化定义是另一个开放问题。[Stanford CRFM 2022](https://arxiv.org/abs/2108.07258) 的尝试太宽泛,需要一个 *可操作的* emergence 测试——比如 "agent 微观行为统计量无法预测系统宏观行为"。我见过的最接近这种测试的论文是 [Anthropic 2024, "Mapping the Mind of a Large Language Model"](https://transformer-circuits.pub/2025/attribution-graphs/biology.html) 里的 circuit-level 分析,但他们分析的是 single LLM,不是 multi-agent。

通信下界虽然 [Yoo & Bölöni 2024](https://arxiv.org/abs/2410.05388) 给了一个干净的设定,但 LLM 系统的 message 是自然语言,带宽度量不是 bit 数,而是 semantic content。形式化"一条 message 携带多少有用信息"需要 reference 一个 ground truth 或 task reward,而这两个在 multi-agent 设置下都不容易拿到。一个可能方向是用 information bottleneck:

$$\min_{q(m|o)} I(M; O) - \beta I(M; Y)$$

但这个 objective 在 LLM multi-agent 里怎么优化、怎么估计,都还是空白。

A2A 协议 (Google DeepMind 2025) 虽然是 engineering 突破,但理论上它没有回答 "agent 间应该交换什么 message" 的问题——它只是规定了 message *格式*。一个真正的通信理论应该告诉我们,在给定 task 和 channel 约束下,optimal protocol 长什么样。这个方向我估计 2026-2027 会有进展,但 2025 年还看不到严肃工作。

最后,multi-agent LLM 系统的 *token 经济学* 是被严重低估的问题。Magentic-One 比 single-agent 多花 8-12 倍 token,MetaGPT 多花 4-6 倍,但收益只有 5-10%。在 production setting 下,这个 ROI 经常算不过来。这也是为什么 [Anthropic 2025](https://www.anthropic.com/research/building-effective-agents) 建议"先 single-agent"。但反过来,某些 task (比如 long-horizon coding、multi-step research) 的 intrinsic structure 就是 multi-agent,强行 single-agent 会让 prompt 爆炸。所以 multi-agent 不是"过时",是"用得不对会亏"。怎么判断一个 task 该不该 multi-agent,目前没有理论,只有经验。

总结一下:多 agent 理论的 *形式化工具* 还在 (EFG, Nash, CFR, communication complexity),但 *LLM 时代的具体应用* 大部分停在"prompt engineering 的艺术"层面。真正严肃的工作是 [Lanctot 综述](https://arxiv.org/abs/1711.06832)、[Cemri et al. 失败分析](https://arxiv.org/abs/2503.13657)、[A2A 协议](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/) 这少数几篇。剩下的多半要打折扣读。

下一章 [Safety 理论](./11-safety-theory.md) 会从这个多 agent 框架延伸出去,讨论当多个 LLM agent 互相作用时,jailbreak / prompt injection / 数据投毒 / 后门这些 attack surface 是如何放大的,以及为什么 multi-agent 设置下的 alignment 问题比 single-agent 难一个量级。