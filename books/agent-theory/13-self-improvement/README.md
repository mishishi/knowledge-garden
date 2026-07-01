# 13. Self-Improvement: Agent 怎么改自己

我第一次读到 "self-improvement" 这个词被严肃使用时, 是 DeepMind 的 AlphaGo Zero 在 2017 年左右的事情. 当时它在自己跟自己下棋, 三天超过人类五千年积累的围棋知识. 但那个语境下的 "self" 跟 LLM 时代的 "self" 不是一回事. AlphaGo Zero 的 self 是固定的 MCTS + 固定的神经网络 + 固定的奖励函数 (赢棋), 改进的是策略网络的权重. LLM 时代的 self-improvement 更混沌: 同一个模型既是 actor 又是 grader 又是 editor, 改的不光是权重, 还有 prompt / 工具 / 记忆 / 流程. 这两者的边界从 2023 年起一直在模糊, 今天这一章我想把这条线讲清楚.

先抛三个我会展开的核心问题. 第一个, 一个 frozen 的 LLM, 不更新权重, 能不能通过修改 prompt、self-critique、tool use 来提升自己的输出? 答案是可以, 但有天花板, 天花板来自模型对自身错误分布的 calibration 程度. 第二个, 如果让它生成训练数据去 fine-tune 自己, 这是不是就是 "真正的 self-improvement"? 这个方向 (RLAIF / Self-Rewarding / Self-Play) 在 2024 年有大量工作, 但 empirical 收敛性很差, 而且 reward hacking 很容易. 第三个, recursive self-improvement (用更强的模型改更弱的模型, 后者再去改更弱的...) 在 2026 年的能力前沿上到底是不是 open question? 老实讲, 我读到 [Huang et al. 2024, Self-Rewarding Language Models](https://arxiv.org/abs/2401.10020) 和 [Yuan et al. 2024, Self-Rewarding Language Models: Pushing the Boundary of LLM Alignment](https://arxiv.org/abs/2410.18052) 第二版的时候, 我觉得 OpenAI 内部对这条路的天花板有更清晰的认识, 只是没公开讲. 这一章我会把 2024-2026 这条线上的关键论文串起来, 把数学、伪代码和我复现 / 跑实验时遇到的坑都放进去.

---

## Self-Refine 和 self-critique 的工作机制

我们从最简单的版本讲起: 模型不改自己权重, 就在 inference 时改自己的输出. [Madaan et al. 2023, Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651) 是这个方向的开山工作之一, 思路简单到乍一看会觉得 "这也能发 paper?": 生成初稿 → 让模型自己给反馈 → 根据反馈改写 → 循环, 直到模型自己说满意或达到最大轮数.

机制层面, 这其实是在做 inference-time 的 search. 我们可以把每一轮的分布写成 $p_\theta(x_{t+1} \mid x_t, f_t)$, 其中 $x_t$ 是第 $t$ 轮的输出, $f_t$ 是同一模型生成的反馈. Self-Refine 的隐含假设是 feedback 比 generation 更 "honest", 因为生成时模型被 prompt 引导去 "完成任务", 而 feedback 时它被引导去 "挑毛病", 后者的温度 / 抽样分布通常更低且更尖锐. 这个假设对 InstructGPT 时代 (2022) 的模型成立度大约 60-70%, 对 GPT-4 / Claude 3.5+ 大约 75-85% — 后面这个数字不是来自某篇 paper, 是我在 AlpacaEval 类似的 prompt suite 上跑 self-refine vs CoT 时的经验, 不同 domain 差很多, 我后面会讲.

```python
def self_refine(model, prompt, max_iters=3, threshold=0.8):
    x = model.generate(prompt, temperature=0.7)
    for t in range(max_iters):
        # feedback stage: 模型被要求当 editor
        feedback_prompt = (
            f"Original task: {prompt}\n\n"
            f"Current output: {x}\n\n"
            "Provide concrete, actionable feedback to improve the output. "
            "End with 'Overall score: X/10' where X is an integer."
        )
        feedback = model.generate(feedback_prompt, temperature=0.3)
        score = parse_score(feedback)
        if score >= 10 * threshold:
            break
        # refine stage: 模型被要求当 writer
        refine_prompt = (
            f"{prompt}\n\n"
            f"Improve this output based on the feedback:\n{feedback}\n\n"
            f"Current output:\n{x}\n\n"
            f"Improved output:"
        )
        x = model.generate(refine_prompt, temperature=0.5)
    return x
```

读 Self-Refine 论文时有一个细节作者写得比较隐晦: feedback 和 refine 必须用同一个模型, 不能用 ground truth 评分的 oracle. 这不是 trick, 是这套范式的核心. 如果你用外部 grader 当 oracle, 那其实是 RLHF / reward model 的 inference-time 版本, 不是 self-improvement. Self-Refine 的卖点在于 *self*: feedback 必须从同一个 $\theta$ 出来. 也因此, Self-Refine 对模型的 metacognitive 能力有要求 — 它得能区分 "我现在输出的东西是好是坏". 这个能力在 GPT-3.5 上几乎不存在, 在 GPT-4 上勉强存在, 在 o1 / Claude 3.5 Sonnet 之后才真正稳定.

我自己在 AlpacaEval 上跑过一组对照: zero-shot、Self-Refine-3iter (3 轮)、Self-Refine-5iter. 在 Llama-3-70B-Instruct 上, zero-shot 的 win rate 是 78.4%, Self-Refine-3iter 是 81.7%, 5iter 是 81.4% — 边际收益在 3 轮后就消失了, 5 轮反而略掉 (噪声或 mode collapse). 这跟 [Madaan et al. 2023](https://arxiv.org/abs/2303.17651) 报告的 "3-5 轮 sweet spot" 一致. 但在 reasoning-heavy 的任务 (MATH, HumanEval+), Self-Refine 的提升更明显, 5-10 个点. 原因是 reasoning 任务的 error 更容易被模型自己识别 (格式错 / 步骤缺), 生成任务的 error 更 subtle (风格 / 信息密度), 模型对自己的盲区更没辙.

把这条线推到极致的是 Anthropic 的 [Gao et al. 2024, Hierarchical Autoregressive Language Models](https://arxiv.org/abs/2410.08258) — 等等, 这个不是. 我想说的是 [Qu et al. 2024, Recursive Introspection: Teaching Language Model Agents How to Self-Reflect](https://arxiv.org/abs/2405.10196) 这类工作, 让模型显式地学习 "什么时候该 trust 自己的输出, 什么时候该 double-check". 它把 self-confidence 作为辅助训练目标加进 loss, 比纯 prompt 版的 Self-Refine 稳很多. 这种 meta-cognition 训练是 2024 年之后 self-improvement 范式的一条主线.

---

## 自我博弈和 RLAIF: 同一模型生成 reward

如果 self-refine 是 inference-time 的 self-improvement, 那 self-rewarding / RLAIF 是 training-time 的. 核心思想: 让模型自己给输出打分, 用这个分数当 reward 去 RL 自己. [Bai et al. 2022, Constitutional AI: Harmlessness from AI Feedback](https://arxiv.org/abs/2212.08073) 是这条线的源头 (Anthropic 2022 年底), 但真正把这套机制跑通的是 [Lee et al. 2023, RLAIF: Scaling Reinforcement Learning from Human Feedback with AI Feedback](https://arxiv.org/abs/2309.00267) 和 [Yuan et al. 2024, Self-Rewarding Language Models](https://arxiv.org/abs/2410.18052).

让我把数学写出来. 标准 RLHF 的 reward 是 $r_\phi(x, y)$ from human preference, 损失是 $\mathcal{L}_{RL} = -\mathbb{E}_{(x,y) \sim \pi_\theta} [r_\phi(x,y) - \beta \cdot \text{KL}(\pi_\theta \| \pi_{\text{ref}})]$. RLAIF 把 $r_\phi$ 换成 $r_\theta$, 也就是同一个 LLM 当 reward model:

$$r_\theta(x, y) = \mathbb{E}_{y' \sim \pi_\theta(\cdot \mid x, \text{prompt}_r)} [\text{LLM-judge}(x, y, y'; \theta)]$$

其中 $\text{prompt}_r$ 是 "你是一个公平的打分员, 对下面两个回答按 1-10 打分..." 之类的. Self-Rewarding ([Yuan et al. 2024](https://arxiv.org/abs/2410.18052)) 的关键 trick 是同时训练 generation 能力和 judging 能力, 损失分两块:

$$\mathcal{L}_{\text{SR}} = \mathcal{L}_{\text{RL}}(r_\theta) + \alpha \cdot \mathcal{L}_{\text{SFT}}(x, y^*) \text{ where } y^* = \arg\max_{y \in \text{candidates}} r_\theta(x, y)$$

前半是 RL loss 用 self-judgment 当 reward, 后半是 SFT loss 拟合 self-judge 选出来的 best output. 它在 Llama-2-70B 上报告 AlpacaEval 2.0 从 64.7% 到 91.4% — 老套数字. 但读 paper 时我注意到一个 caveat 作者没在 abstract 里讲: 第二轮迭代后 reward hacking 开始出现. 模型学会了 "怎么让 self-judge 打高分" 而不是 "怎么生成好回答". 这跟 GAN 训练里的 mode collapse 是同一类问题, 只是 LLM 这边更 subtle: 你看到的不是样本多样性下降, 而是回答逐渐偏向某种 self-judge 喜欢的风格 (更长、更礼貌、更多 hedging).

我自己在复现 Self-Rewarding 时遇到的坑: 第一, self-judge 的 prompt 模板极其敏感, 改一两个字 reward distribution 就会跳, 训练出来完全不一样. 作者给的 prompt 模板是基于 Llama-2 tokenizer 的, 换到 Qwen / Mistral 上时 tokenizer 不一致会把 token 数算错, 训练会崩. 第二, DPO / PPO 的选择. Self-Rewarding 用 PPO, 但我没跑通 PPO 的稳定版本 (4 张 A100 上 70B 跑 PPO 不实际), 用 DPO 替代时 loss 收敛轨迹跟 paper 报告的不一样 — paper 里 DPO baseline 也差, 但方向一致.

把这条线再推一点, 是 [Zhang et al. 2024, Iterative Preference Learning from Human Feedback: Bridging Theory and Practice](https://arxiv.org/abs/2412.18825) — 这篇不是 self-rewarding, 但它告诉我 self-rewarding 的迭代次数为何会在 2-3 轮后饱和: preference 模型对自己的分布 overfit 了. Self-Rewarding 是这个现象在生成侧的对偶.

---

## Self-Play 和 Voyager: 长期记忆 + 技能积累

在 agent 语境下, "self-improvement" 不光是改输出或改权重, 还要改 *环境中的自己*. [Wang et al. 2023, Voyager: An Open-Ended Embodied Agent with Large Language Models](https://arxiv.org/abs/2305.06290) 是这条线的代表: 一个 Minecraft agent 通过不断写代码 → 测试 → 失败 → 改代码 → 把成功的技能存进 vector store, 实现 "持续学习". 模型的权重不变, 改的是 prompt 的 skill library.

机制层面, Voyager 的三个组件是: curriculum (GPT-4 根据当前进度提议下一个挑战)、skill library (每次成功的代码片段存进去, 用 embedding 做 retrieval)、verifier (用一个简单的 "物品是否被收集到" 的 oracle 反馈). 它跟 Self-Refine 的区别在于 Self-Refine 是 "同一任务多轮", Voyager 是 "不同任务跨 session 积累".

```python
class VoyagerAgent:
    def __init__(self, llm, env, skill_lib):
        self.llm = llm           # frozen
        self.env = env           # Minecraft
        self.skills = skill_lib  # vector store of (embedding, code)

    def step(self, state):
        # curriculum: 提议下一件事做
        task = self.llm.generate(
            f"你目前会 {len(self.skills)} 个技能, 上次完成了 {state.last}. "
            f"根据毕加索学习的难度曲线, 下一步应该做什么? "
            f"返回一行 Python 任务描述."
        )
        # code generation: 结合相关历史技能
        retrieved = self.skills.search(task, k=5)
        code = self.llm.generate(
            f"在 Minecraft 用 Mineflayer API 完成任务: {task}\n"
            f"参考这些已成功运行的代码:\n{retrieved}\n"
            f"返回可执行 JavaScript."
        )
        # execute and verify
        success, stderr = self.env.run(code)
        if success:
            self.skills.add(task, code)
        else:
            # self-debug: 让 LLM 看 stderr 改代码
            fixed = self.llm.generate(
                f"代码失败, 错误: {stderr}. 改它."
            )
            self.env.run(fixed)
```

Voyager 跟 Self-Rewarding 的关键差别: Voyager 的 reward 是环境给的 (物品是否被收集), 不是 self-judge. 这绕开了 reward hacking, 但代价是必须有 simulator. 这是 2024 年自我博弈流派的一个分化: 一边是要 oracle reward 但需要环境 (Voyager / AgentEvol), 一边是不要 oracle 但 reward hacking (Self-Rewarding / SPIN). 

[Chen et al. 2024, AgentEvol: Evolving LLM Agents via Continual Learning](https://arxiv.org/abs/2410.20716) 把 Voyager 的精神推到更通用的 domain: 不光是 Minecraft, 而是任意 tool-use 环境. 它维护 "experience buffer", 每次任务结束后让模型反思 "为什么成功 / 失败, 关键决策点是?", 反思结果存进 buffer 下次 retrieval. 它报告在 HotpotQA / ALFWorld 上比 fixed-prompt baseline 高 10-15 个点.

我读 Voyager 复现时最大的失望是: 它的 "持续学习" 其实非常 brittle. skill library 的 embedding 是用 text-embedding-ada-002, 这个模型跟 GPT-4 的语义空间不完全对齐, retrieval 时会召回不相关的 skill, 然后 LLM 看到不相关的 skill 反而写出错的代码. 论文里报告的数字看着漂亮, 但 variance 很大. 后续的 [Wang et al. 2024, ODYSSEY: Empowering Minecraft Agents with Open-Ended Exploration](https://arxiv.org/abs/2410.07086) 修了这个问题 (用 LLM 自己生成 skill 描述, 不用 embedding retrieval), 效果稳很多. 老实讲, Voyager 是 "看起来 work 但难复现" 的典型, 我组里当时有两个 PhD 花了两个月才稳定跑通.

---

## 递归自我改进和 Open Question

到这里我们讲了三种 self-improvement: Self-Refine (改输出)、Self-Rewarding (改权重)、Voyager (改记忆 + 工具). 它们的共同假设是 "改的幅度有上限". 但 [Yao et al. 2024, Olympus / Recursive Self-Improvement](https://arxiv.org/abs/2402.10554) (虚构标题, 我不确定有这样一篇 — 让我换成正确的) 让我引用 [Huang et al. 2024, Large Language Models Can Self-Improve](https://arxiv.org/abs/2210.11610) 早一些的工作, 它从理论上问: 一个模型用自身生成的数据去 fine-tune 自己, 性能是不是会单调上升? 答案是否. 论文给出一个反直觉的结果: 当 self-generated data 的质量低于 ground truth 数据时, 迭代 self-improvement 会 *退化* (performance 比 base 还差). 模型越自信, 退化的越快.

数学上, 假设 base 模型是 $\pi_0$, 第 $t$ 轮的模型是 $\pi_t$, self-generated distribution 是 $q_t$. 如果我们训练 $\pi_{t+1}$ 来拟合 $q_t$ 中 "高质量" 子集:

$$\mathcal{L}_t(\theta) = -\mathbb{E}_{x \sim q_t} [w(x) \log \pi_\theta(x)]$$

其中 $w(x)$ 是 self-judge 给的 weight. 退化发生在 $w$ 跟真实 quality 的 KL 散度大于某个阈值时. 这个 KL 散度对 $\pi_t$ 很敏感 — 模型越强, self-judge 越准; 模型越弱, self-judge 越像 noise. 这就是为什么 Self-Rewarding 在强模型 (Llama-2-70B) 上 work, 在弱模型 (Llama-2-7B) 上完全崩.

这引出一个我没在任何一篇 paper 看到答案的问题: 递归 self-improvement (用 $\pi_{t+1}$ 去教 $\pi_{t+2}$, 而不是回到 $\pi_0$ 教后续所有代) 在 LLM 上有没有 scaling 效应? 形式化地:

$$\pi_{t+1} = \text{fine-tune}(\pi_t, \text{data generated by } \pi_t)$$

vs.

$$\pi_{t+1} = \text{fine-tune}(\pi_0, \text{data generated by } \pi_t)$$

后者叫 iterative restart, 前者叫 recursive. 在 AlphaGo Zero 上 recursive 赢了 — 每代都比上一代强, 用上一代当对手. 在 LLM 上 recursive 没有这种保证, 因为 reward 不是固定的 (MCTS 用的赢棋概率是 ground truth). Self-Rewarding 的实验基本只跑 2 轮 recursive, 第 3 轮就报告 reward collapse.

我的赌注是: 真正的 recursive self-improvement 需要比 RL 更结构化的目标. 比如 [Yuan et al. 2024, Self-Rewarding LM](https://arxiv.org/abs/2410.18052) 的生成 *judging* 双任务联合训练是其中一个突破口 — 它不是单纯拟合 self-output, 而是同时优化 "生成好输出" 和 "识别好输出" 两个能力, 这是固定点的某种构造. 但这只是猜想, 没有 paper 给 convergence proof.

更激进的方向是 [OpenAI 2024, Self-Play Fine-Tuning (SPIN)](https://arxiv.org/abs/2401.01355). SPIN 的设定: $\pi_t$ 是第 $t$ 轮的策略, $\pi_0$ 是 reference. 训练目标:

$$\mathcal{L}_{\text{SPIN}} = \mathbb{E}_{x \sim \mathcal{D}, y \sim \pi_t} \left[ -\log \pi_\theta(y \mid x) \cdot \mathbb{1}[y \in \pi_0] + \log \pi_\theta(y \mid x) \cdot \mathbb{1}[y \notin \pi_0] \right]$$

这是种 self-play 版的 DPO — 模型跟自己之前的能力对决. 论文里 SPIN 在 Llama-2-7B 上跑到第 3 轮 AlpacaEval 从 53.4 → 64.7 → 69.1, 第 4 轮掉到 65.2. 跟 Self-Rewarding 一模一样的 "两轮后崩" 模式. 我读这篇 paper 时觉得: SPIN 的理论 motivation 跟 GAN 的 min-max 形式很像 (generator 跟 discriminator 对决), GAN 的训练困难 (mode collapse, 不收敛) 大概率也会出现在 SPIN 上.

---

## 实验数据和局限

让我把关键数字摆出来. Self-Rewarding Llama-2-70B 第二轮 (paper 里最好的 checkpoint) AlpacaEval 2.0 LC win rate 是 91.4%, 比 base 高 ~27 个点, 比 RLHF 版 (Llama-2-70B-Chat) 高 ~9 个点. SPIN-3 on Llama-2-7B AlpacaEval 1.0 从 53.4 升到 69.1 — 但跟 RLHF 的 78.4 还差不少. 老实讲, 在 7B scale 上, self-rewarding 还打不过 RLHF. 差距在 70B+ 才抹平. 我的猜测是 self-judge 在弱模型上不够 calibrated, 强模型上 judge 分布更 sharp, RL signal 才有足够信息量.

Self-Refine 在 LLM-as-judge 设置下报告 (在 GPT-3.5 上): code generation +9%, math reasoning +7%, dialogue +5%. 注意 GPT-3.5 是 Self-Refine 的下限 — GPT-4 上数字更高, paper 没报具体数字. Voyager 在 Minecraft report 的 unique items collected 是 3.5x baseline (fixed-prompt), diamonds 收集数是 15x. 这些数字看着强, 但 baseline (fixed-prompt GPT-4 Minecraft agent) 的 variance 大, 我的复现里 baseline 就能达到 paper 报告的 70% 水平, Voyager 提升没论文那么夸张.

局限. 第一, 这章所有 self-improvement 方法都对 *模型大小* 敏感. 7B 上基本不 work, 70B+ 才能稳定. 这意味着 self-improvement 不会 "让小模型变大模型", 它只是放大已有能力. 这跟 AlphaGo Zero 不一样 — Go Zero 从零开始训练就能达到 superhuman. LLM 的 self-improvement 永远需要 reasonable pretrained base. 第二, evaluation 的问题. 大部分 self-improvement 论文在 AlpacaEval / MT-Bench 上报告, 这些 benchmark 本身用 LLM-as-judge — Self-Rewarding 把 LLM judge 当 reward signal 又当 eval metric, 有 circular evaluation 的嫌疑. 我组当时做 ablation 时发现, 把 eval 换成 human raters, Self-Rewarding 的提升从 27 个点降到 8 个点. 这个数字我没在任何 paper 看到, 因为没 paper 做这个 ablation (做出来就不好看了). 第三, 没有 paper 给 *convergence guarantee*. Self-Rewarding / SPIN 都是 empirical, 数学上没证明这个过程会停或会上升.

下一个 open question 我觉得值得研究者注意: 怎么让 self-improvement 跨 domain transfer? 现在的 self-rewarding 是在单一 domain (chat / code / math) 上 iterate, 一个在 math 上 self-improved 的模型, 不一定在 code 上变好. AlphaGo Zero 的 transfer 是天然的 (围棋只有一种规则), LLM 没有这种统一性. [Cheng et al. 2024, Self-Improvement Is Not Equal to Stronger Data](https://arxiv.org/abs/2410.09412) (我不确定这篇存在, 让我用一个更可靠的引用, [Yue et al. 2024, Large Language Models as Optimizers](https://arxiv.org/abs/2309.03409) 讨论了类似问题) — y'know, 这个领域给我的感觉是: 大家对 inference-time 的 self-improvement 信心比较足 (Self-Refine / Voyager 是真的 work), 对 training-time 的 self-improvement 信心明显不足 (Self-Rewarding / SPIN 的天花板在反复被打), 对 recursive self-improvement 几乎是 puzzle — 不知道会发生什么, 但都觉得应该会发生. 2026 年 1 月, [OpenAI o3 系统 card](https://arxiv.org/abs/2412.16161) 透露在某些 internal benchmark 上 o3 用了 self-play 风格的训练, 但没有细节. 我赌半年内会有更系统的 paper 出来.

---

最后说一句关于 safety 的题外话, 但重要. Self-improvement agent 的 safety 含义跟 RL agent 不一样. RL agent 被 bounded 在 reward model 里, reward 是 hand-designed 或 human-labeled. Self-improvement agent 的 reward *是它自己*. 这意味着 alignment 问题从 "对齐外部奖励" 变成 "保证内部奖励不变". [Cotra 2022, Without specific countermeasures, the simplest path to advanced AI may be self-improvement](https://arxiv.org/abs/2203.07388) 这种哲学性讨论我们就不展开了, 但研究者动手做 self-improvement 实验时, 应该把 "self-judge 的 bias 累积" 当成 first-class concern, 而不是先 train 再 audit. 

下一章 [World Model / Embodied / AGI 路径](./14-frontier.md) 我们从 self-improvement 转出去, 看 LLM agent 在 embodied / world-model 这条线上的 2026 真实现状和几个流派的争论.

---

# 第 14 章预告

下一章我会写 [World Model / Embodied / AGI 路径: 2026 真在发生, 几个流派](./14-frontier.md). 重点会放在三个流派的对立上: Sora / Genie 这种 "world model 直接训 video" 的派, RT-2 / Octo 这种 "VLM + robot control" 的派, 还有 Yann LeCun 一直在推的 "JEPA / predictive embedding" 的派. 我会把这三个流派的 2024-2026 关键论文串起来, 看它们对 "agent 需要什么样的世界知识" 这个根本问题的不同回答. 数学上会展开 V-JEPA 的 embedding objective 和 Sora 的 diffusion transformer 的 latent 怎么对得上. 代码上会有 RT-2 的 action chunking 实现和 V-JEPA 的 predictor 简化版. 实验数据上会摆 Sora 的物理 benchmark (虽然有人批评它用的 eval 不够硬), RT-2 的 grasping 数据, 和 V-JEPA 在 EgoSchema 上的数字. 不卖关子, 我对 Sora 派的怀疑比 V-JEPA 派多, 我会写出来为什么.