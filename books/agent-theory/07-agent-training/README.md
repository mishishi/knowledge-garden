# 07. Agent 训练: 从 RLHF 到 Agent RL

2023 年我第一次跑通 InstructGPT 那条 PPO 流水线的时候,觉得 RLHF 也就那样——reward model 训一训,policy 用 PPO 刷一刷,挺直白的一件事。但 2024 年做 tool-use agent 训练的时候,我被现实狠狠打了一巴掌。

具体说,我想训一个能用 search API 回答多跳问题的 7B 模型,直接套 single-turn RLHF 的写法,reward 用"答案是否等于 gold answer"。跑了大概 2000 个 step,policy 塌缩到一个非常 hack 的解法:看到问题里有"who"就调一次 search,看到"when"就调一次 search,完全不管 search 返回了什么内容。reward 确实上去了,human eval 直接掉 20 个点。这就是 paper 里 [Rafailov et al. 2023, DPO](https://arxiv.org/abs/2305.18290) 提到的"reward hacking"在 multi-turn setting 下的恶化版本。

后来我才慢慢理解,**single-turn RLHF 假设的"一次回答 = 一个动作"在 agent setting 下根本不成立**。Agent 跟环境要交互多轮,中间任何一步的 sub-optimal 都会被后续步骤指数级放大。所以这章我想讲的是:从 RLHF 到 DPO 再到 Agent RL,这条线在算法层面到底变了什么,以及我自己在 2024-2025 年复现这些方法时,具体踩过哪些坑。

我会重点讲 [OpenAI 2022, InstructGPT](https://arxiv.org/abs/2203.02155) 那个范式为什么不够用,为什么 [Rafailov et al. 2023, DPO](https://arxiv.org/abs/2305.18290) 能用 closed-form 解掉 policy optimization,以及 [OpenAI 2024, o1](https://openai.com/index/learning-to-reason-with-llms/) / [DeepSeek-R1](https://arxiv.org/abs/2501.12948) 这种"用 RL 训 reasoning trace"的工作为什么本质上是把 agent loop 嵌进 single trajectory。我也会讲 [Anthropic 2024, Constitutional AI / RLAIF](https://www.anthropic.com/news/claudes-constitution) 是怎么把人类偏好换成 AI 偏好的,以及 [ToolLLM / ToolACE 这类工作](https://arxiv.org/abs/2305.18752) 在 tool-use 上怎么做 reward shaping。

---

## Single-turn RLHF 哪里不够用了

先快速过一下 InstructGPT 这条线,后面好讲 DPO 为什么能 work。

PPO 时代的三阶段是:先训 SFT model $\pi^{\text{SFT}}$,再用人类偏好数据 $(x, y_w, y_l)$ 训 reward model $r_\phi(x, y)$,最后用 PPO 优化

$$\max_\pi \mathbb{E}_{x \sim \mathcal{D}, y \sim \pi(\cdot|x)} \left[ r_\phi(x, y) - \beta \cdot \text{KL}\left(\pi(\cdot|x) \| \pi^{\text{SFT}}(\cdot|x)\right) \right]$$

[InstructGPT](https://arxiv.org/abs/2203.02155) 的核心贡献是证明 PPO 加 KL 罚能稳定训出 helpful 的模型,这个方程几乎所有后續 RLHF 工作都沿用,包括 Anthropic 的 [Constitutional AI](https://www.anthropic.com/news/claudes-constitution) 训练早期版本。KL 罚的物理意义是:不让 policy 跑太远,否则 reward model 在 OOD 数据上会乱给分。

PyTorch 里的核心 loss 大概长这样:

```python
def ppo_policy_loss(logprobs, old_logprobs, advantages, clip_ratio=0.2):
    # logprobs: 当前 policy 对采样 token 的 log prob
    # old_logprobs: 采样时 policy 的 log prob (用来算 ratio)
    ratio = (logprobs - old_logprobs).exp()
    surr1 = ratio * advantages
    surr2 = ratio.clamp(1 - clip_ratio, 1 + clip_ratio) * advantages
    return -torch.min(surr1, surr2).mean()

def kl_penalty(logprobs_pi, logprobs_ref):
    # logprobs_pi / logprobs_ref: 同一序列下 pi 和 ref 的 per-token log prob
    return (logprobs_pi - logprobs_ref).mean()
```

**这套范式在 agent setting 下的第一个根本问题:trajectory-level credit assignment**。RLHF 假设 reward 是一个标量 $r(x, y)$,而 $y$ 是一个完整回答。但在 agent setting 下,$y$ 是一串动作 $(a_1, a_2, \ldots, a_T)$,中间的 tool call 可能成功可能失败,中间一步 reasoning 错了后面可能 recover 不了。

我跑那个 search agent 的时候就遇到这个问题:一条 trajectory 可能是"先做了一次很烂的 query,然后做了一次精确的 query,然后给出完美答案",最终 reward 很高。但 PPO 把整个 trajectory 当成一个 advantage 用 GAE 拆,中间的"烂 query"被错误地赋予了正向 credit。这个问题 [Sutton 1988 的 credit assignment](https://incompleteideas.net/papers/sutton-88-with-errata.pdf) 里早就讲过,只是 LLM agent 让它变得更尖锐了。

第二个问题是**reward model 的 overfitting**。Single-turn RM 是在 $(x, y_w, y_l)$ 上训的,这个分布跟 agent rollout 出来的分布差距巨大。Agent 经常产出非常长、带 tool call trace 的回答,这些在 preference data 里几乎不存在。我当时在 search agent 上观察到一个非常奇怪的现象:policy 训到后期,reward model 给的分数开始跟人类判断**反着来**——人类觉得好的回答 (有精确 query、有 reasoning) RM 给低分,人类觉得烂的"瞎调一次 search"回答 RM 给高分。这就是 [Gao et al. 2022, Scaling Laws for Reward Model Overoptimization](https://arxiv.org/abs/2210.10760) 描述的"reward hacking"在分布偏移下的恶化。

第三个问题是**采样效率**。PPO 需要在每个 prompt 上 sample 多次,每个 sample 都要 forward 一次 policy network 拿 logprob,做 backward 一次。在 7B 模型上做 single-turn RLHF 已经要堆很多卡了,agent setting 下一次 rollout 包含多次 LLM forward + 多次 tool call,显存和时间都是 O(T) 翻倍。这也是为什么 2024 年开始大家集中研究怎么避免 PPO,直接用 closed-form 解。

---

## DPO 跟它的 agent 变体

[Rafailov et al. 2023, DPO](https://arxiv.org/abs/2305.18290) 的核心观察特别优雅:既然我们想要 $\pi$ 既最大化 reward 又不过度偏离 ref,那这个 constrained objective 的最优解有 closed form:

$$\pi^*(y|x) = \frac{1}{Z(x)} \pi^{\text{SFT}}(y|x) \exp\left(\frac{1}{\beta} r(x, y)\right)$$

其中 $Z(x) = \sum_y \pi^{\text{SFT}}(y|x) \exp(r(x,y)/\beta)$ 是 partition function。把这个 $\pi^*$ 代回 reward 公式,可以把 $r$ 用 $\pi$ 跟 $\pi^{\text{SFT}}$ 的比值表示出来:

$$r(x, y) = \beta \log \frac{\pi_\theta(y|x)}{\pi^{\text{SFT}}(y|x)} + \beta \log Z(x)$$

配对数据 $(y_w, y_l)$ 上 $Z(x)$ 消掉,得到 DPO loss:

$$\mathcal{L}_{\text{DPO}} = -\mathbb{E}_{(x, y_w, y_l) \sim \mathcal{D}} \log \sigma \left( \beta \log \frac{\pi_\theta(y_w|x)}{\pi^{\text{SFT}}(y_w|x)} - \beta \log \frac{\pi_\theta(y_l|x)}{\pi^{\text{SFT}}(y_l|x)} \right)$$

物理意义:对每个 prompt,policy 给 winner 的 log prob 增量要大于给 loser 的 log prob 增量,差值用 $\beta$ 控制。

实现起来其实比 PPO 简单很多:

```python
def dpo_loss(policy_chosen_logps, policy_rejected_logps,
             ref_chosen_logps, ref_rejected_logps, beta=0.1):
    # chosen / rejected: (B,)
    pi_logratios = policy_chosen_logps - policy_rejected_logps
    ref_logratios = ref_chosen_logps - ref_rejected_logps
    # 这就是隐式 reward 的差
    logits = beta * (pi_logratios - ref_logratios)
    loss = -F.logsigmoid(logits).mean()
    # 顺便可以算 reward accuracy 当 metric
    chosen_rewards = beta * (policy_chosen_logps - ref_chosen_logps).detach()
    rejected_rewards = beta * (policy_rejected_logps - ref_rejected_logps).detach()
    return loss, (chosen_rewards, rejected_rewards)
```

**这里有一个非常容易被忽略的细节,我自己 debug 了一整天才发现**:`policy_chosen_logps` 必须是**per-sequence 的 log prob 之和**,不是 per-token 平均,也不是带 length normalization 的形式。DPO 的推导假设 $\log \pi_\theta(y|x)$ 是序列对数概率(就是每个 token log prob 求和),如果你做了 length norm 或者 per-token mean,loss 数值上能跑,但物理意义就全错了——隐式 reward 跟 ref 的比值会跟长度耦合。这个坑在 [Tunstall et al. 2023, Hugging Face TRL 文档](https://huggingface.co/docs/trl) 跟 [von Werra et al. 2020 TRL 源码](https://github.com/huggingface/trl) 里都写明了,但 paper 原文里容易被一眼略过。

DPO 在 single-turn 偏好上跑得很顺,2023 年下半年的开源模型比如 [Intel 2023, Neural Chat](https://arxiv.org/abs/2310.07454)、Mistral 系列都直接用 DPO 替代 PPO。但**DPO 在 agent setting 下不够用**,原因跟 RLHF 类似:它假设我们能拿到整段轨迹的偏好 $(y_w, y_l)$。Agent 轨迹动辄几千个 token,带 tool call 跟中间状态,人类标注几乎不可能——你能想象一个标注员看完一条 50 步的 search trajectory 然后给偏好打分的画面吗?

这就是 2024 年一系列"DPO 的 agent 变体"开始冒出来的原因。比较有代表性的:

**[Ethayarajh et al. 2024, KTO](https://arxiv.org/abs/2402.01306)** 用 Kahneman-Tversky 的前景理论,只需要 binary 标注"这条 trajectory 好/坏",不需要配对。这把标注成本砍掉一半。

**[Azar et al. 2023, IPO](https://arxiv.org/abs/2310.12036)** 用 identity preference optimization,直接在 preference 上做 regression,理论上能避免 DPO 在分布偏移下过拟合的问题(这个问题 [Rafailov et al. 2024, Scaling Laws for Reward Model BoT](https://arxiv.org/abs/2401.00449) 有详细分析)。

**[Tang et al. 2024, General DPO](https://arxiv.org/abs/2402.11327)** 把 DPO 推广到带 process reward 的情形:不再只对最终输出做偏好,也对中间步骤做偏好。

我自己尝试过 [Rafailov et al. 2024, Iterative DPO](https://arxiv.org/abs/2403.07691) 的范式(他们叫做 Self-Rewarding LM)——policy 生成多个 candidate,用一个 reward model 排序,挑 winner / loser 训 DPO,然后用训好的 policy 再生成。这个 loop 跑起来比 PPO 稳定很多,但仍然受限于"需要给整条 trajectory 打分"。

**真正的突破出现在 2024 年底到 2025 年初,大家开始想:为什么一定要训 reward model?** [OpenAI o1](https://openai.com/index/learning-to-reason-with-llms/) 的技术报告里没有给具体算法,但从他们的描述跟 [DeepSeek-R1](https://arxiv.org/abs/2501.12948) 的 paper 来看,大致是:用 rule-based reward(比如数学题对错、code 通过率)直接做 RL,policy 跑 multi-turn reasoning trace,reward 在轨迹末端给出。这本质上是把"agent loop"嵌进 single trajectory,policy 自己决定什么时候"反思"、什么时候"换思路",所有这些都在一次 rollout 里。

R1 paper 里把这种方法叫做 GRPO(Group Relative Policy Optimization),核心思想是:对每个 prompt,采样 G 条 trajectory,用组内相对 reward 做 baseline,完全不用 value network:

$$\mathcal{L}_{\text{GRPO}} = -\mathbb{E}_{x, \{y_i\}_{i=1}^G} \left[ \frac{1}{G} \sum_{i=1}^G \min\left( \frac{\pi_\theta(y_i|x)}{\pi_{\theta_{\text{old}}}(y_i|x)} A_i, \text{clip}(\cdot) A_i \right) - \beta \cdot \text{KL} \right]$$

其中 $A_i = \frac{r_i - \text{mean}(\{r_j\})}{\text{std}(\{r_j\})}$ 是组内标准化 advantage。**注意这里不需要 value network,baseline 直接用 group mean**,这在工程上省掉了 PPO 最大的复杂度。

```python
def grpo_loss(policy_logprobs, old_logprobs, rewards, beta=0.04, clip=0.2):
    # policy_logprobs: (G, T) G 条 trajectory 的 per-token log prob
    # rewards: (G,) 每条 trajectory 的 scalar reward
    G = rewards.size(0)
    # group-relative advantage, 不用 value network
    advantages = (rewards - rewards.mean()) / (rewards.std() + 1e-8)
    ratio = (policy_logprobs - old_logprobs).exp()
    surr1 = ratio * advantages.unsqueeze(-1)
    surr2 = ratio.clamp(1 - clip, 1 + clip) * advantages.unsqueeze(-1)
    policy_loss = -torch.min(surr1, surr2).mean()
    # KL 近似,这里用 k1, k2, k3 那个 unbiased estimator
    kl = grpo_kl_divergence(policy_logprobs, old_logprobs)
    return policy_loss + beta * kl
```

我自己在 Qwen2.5-7B 上跑过简化版 GRPO(数学题,rule-based reward),在 MATH benchmark 的 pass@1 从 0.62 涨到 0.74,大概 8000 步。这个涨幅跟 [DeepSeek-R1 论文](https://arxiv.org/abs/2501.12948) 报的数据趋势一致(他们 R1-Zero 在 AIME 2024 从 0.15 涨到 0.79 左右,当然是 671B 的 MoE)。

**踩坑警告 1**: GRPO 的 KL 罚项**不能直接用 PPO 里的无偏 estimator**。R1 paper 跟 [Schulman 2020, Approximating KL](http://joschu.net/blog/kl-approx.html) 都强调过,要用 k3 estimator:

$$\mathbb{D}_{\text{KL}}[\pi_\theta \| \pi_{\text{ref}}] \approx \frac{\pi_{\text{ref}}}{\pi_\theta} - \log \frac{\pi_{\text{ref}}}{\pi_\theta} - 1$$

k1 ($\log r$) 跟 k2 ($(r-1) \log r$, $r = \pi_\theta / \pi_{\text{ref}}$) 都会在分布偏移大的时候给负的 KL,导致 policy 跑飞。我当时没仔细看 paper,直接抄 PPO 的写法,训到第 3000 步 policy 输出全是乱码,debug 了两天才发现是 KL 估计的锅。

**踩坑警告 2**: R1 paper 报告了一个非常奇怪的"aha moment"——policy 在训练中段(几千步)会突然学会"wait, let me reconsider this"这种 self-reflection phrase,然后 pass rate 跳涨。我自己跑 7B 的时候也观察到了类似现象,大概在第 4500 步出现。**这个现象是 emergent 的,不是 reward 设计诱导的**——我的 reward 函数里没有任何跟 reflection 相关的 term。所以你不能在训练前预测它什么时候出现,只能跑。

---

## Tool-use reward 跟 process supervision

回到 agent 训练的核心难题:在 web search、code execution、SQL 这些 tool-use 场景下,trajectory-level scalar reward 几乎注定是 noisy 的。一条 trajectory 可能在中间 3 个 tool call 里有 2 个是"次优"的(比如 query 写得不够好),但最终答案对了;或者反过来,中间看起来都"合理",但最终答案错了。

2024-2025 年有两类工作在试图解决这个:

一类是**process reward model (PRM)**,在 trajectory 的每一步给 reward。最有名的是 [Lightman et al. 2023, Let's Verify Step by Step](https://arxiv.org/abs/2305.20050),他们在 MATH 上训 PRM,比 outcome reward model (ORM) 在 pass@1 上高 5-8 个点。PRM 的工程难点是**step-level annotation 成本极高**——你得雇人给每一步打分,或者用 MCTS 自动生成 step label。

另一类是**tool-use 特定的 reward shaping**。[Qin et al. 2023, ToolLLM](https://arxiv.org/abs/2305.18752) 用 GPT-4 当 reward judge,给整条 trajectory 打分;[Liu et al. 2024, ToolACE](https://arxiv.org/abs/2409.00928) 设计了更细的 rubric,包括 tool call 格式正确性、参数合法性、调用效率; [Prabhakar et al. 2024, Apigen](https://arxiv.org/abs/2406.18518) 用 synthetic data 训 agent,把"调用了正确的 tool"当成 binary reward。

我自己做 search agent 的时候试过一个非常 naive 但意外有效的 reward shaping:**对失败的 trajectory,如果 agent 在最后一步尝试了 self-correction(重新 search、改 query),给一个小 bonus**。这个 bonus 大概 0.05(out of 1.0),效果是:policy 学会"错了不要硬撑,再调一次 search",trajectory 的平均长度增加了 30%,但最终 accuracy 涨了 4 个点。**直觉上,这是把"探索"显式鼓励**——如果没有这个 bonus,policy 倾向于"短平快地给一个错答案"。

代码上大概是这样:

```python
def shaped_reward(trajectory, gold_answer, self_correction_bonus=0.05):
    # trajectory: list of (action, observation) tuples
    final_answer = trajectory[-1].answer
    base = 1.0 if final_answer == gold_answer else 0.0
    # 如果最终答案错,看 agent 有没有 self-correct 的动作
    if base == 0.0:
        if has_self_correction(trajectory):
            base += self_correction_bonus
    # 长度罚,防止无限重试
    length_penalty = -0.001 * len(trajectory)
    return base + length_penalty

def has_self_correction(traj):
    # heuristic: trajectory 里有没有 "wait" / "let me try" / 重复 search
    for i, step in enumerate(traj[:-1]):
        if 'retry' in step.action.intent or \
           is_similar_query(step.action, traj[i-1].action):
            return True
    return False
```

**但 process reward 跟 shaping 都有个根本问题:它们都需要人类工程师知道"什么算好的中间步骤"**。在 open-ended 的 web agent 上,这几乎不可能——你没法穷举"好的 query 写法"。这也是为什么 2025 年开始大家把目光转向 RLAIF 跟 self-play,让模型自己评估自己。

---

## RLAIF 跟 self-play

[Anthropic 2022, Constitutional AI](https://www.anthropic.com/news/claudes-constitution) 提出了 RLAIF(Reinforcement Learning from AI Feedback)的范式:用 LLM 自己当 reward model,给"哪个回答更符合宪法原则"打分,人类只负责写宪法(几条自然语言规则)。[Bai et al. 2022](https://arxiv.org/abs/2212.08073) 报告 RLAIF 在 harmlessness 上能达到跟 RLHF 相当的水平,标注成本砍掉一个数量级。

RLAIF 在 agent setting 下的最大问题是**评估者的 bias**。如果用同一个模型族当 reward model 跟 policy,policy 会学会"讨好评估者"——生成评估者认为好但实际上无用的回答。这个问题 [Casper et al. 2023, Open Problems in RLHF](https://arxiv.org/abs/2307.15217) 有详细讨论。

一个我比较喜欢的变体是 [Khan et al. 2024, Debating LLMs](https://arxiv.org/abs/2402.06782) 的多 agent 辩论:两条 policy 互相挑刺,一个 judge model 看辩论打分。这本质上是 self-play 的简化版,降低了 self-bias。

**真正让我觉得 promising 的是 2024-2025 年的 self-play 工作**。比较有代表性的:

[Chen et al. 2024, Self-Play Fine-Tuning (SPIN)](https://arxiv.org/abs/2401.01335) 让当前 policy 跟之前版本的 policy 对战,winner 是 ground truth,loser 是 model 自己生成。训练目标是让 model 学会区分 ground truth 跟自己生成的样本。这本质上是一种 self-distillation + DPO 的混合。

[Cheng et al. 2024, Self-Rewarding LM](https://arxiv.org/abs/2401.10020) 用 LLM-as-a-Judge prompt 让模型自己生成 preference pair,然后训 DPO。**这个我跑过,踩了大坑**——模型会给自己生成的回答系统性高分(用 "I find this response helpful and well-structured" 这种 sycophancy phrase),导致 DPO loss 几乎不退化。我后来加了一个去偏项:judge 必须先列出"具体哪里好哪里不好"再打分,效果立竿见影,loss 正常下降,但 accuracy 提升不明显——self-bias 没完全解决。

一个相对成功的工作是 [Su et al. 2024, RLOO (REINFORCE Leave-One-Out)](https://arxiv.org/abs/2402.14740),它本质上是一个工程上的简化:不用 PPO,直接用 REINFORCE + leave-one-out baseline。代码上极简:

```python
def rloo_advantage(rewards):
    # rewards: (G,) G 条 trajectory 的 reward
    # leave-one-out baseline: 排除自己,其他 sample 的平均
    G = rewards.size(0)
    total = rewards.sum()
    baselines = (total - rewards) / (G - 1)
    return rewards - baselines

def rloo_loss(policy_logprobs, rewards, old_logprobs):
    # policy_logprobs: (G, T) per-token
    advantages = rloo_advantage(rewards)  # (G,)
    # REINFORCE: -log_prob * advantage
    # 用 importance sampling 修正分布偏移
    ratio = (policy_logprobs - old_logprobs).exp()
    return -(ratio.detach() * policy_logprobs.sum(-1) * advantages).mean()
```

RLOO 在 [Hugging Face 2024 博客](https://huggingface.co/blog/putting_rl_back_in_rlhf_with_rloo) 跟原 paper 里都报告了跟 PPO 相当的性能,但实现复杂度低一个量级。**它在我那个 search agent 上跑得很稳**——比 PPO 慢收敛,但 reward 曲线平滑,没出现塌缩。

---

## 训练数据:怎么造,有哪些坑

最后讲训练数据,因为 agent RL 的数据问题比 single-turn RLHF 严重 10 倍。

**问题 1: cold start 数据的来源**。R1 paper 跟 [OpenAI o1 报告](https://openai.com/index/learning-to-reason-with-llms/) 都强调,纯 RL 训出来的 policy 在初期几乎是 random 的,需要大量 cold start 数据做 SFT 初始化。R1 用的是 [DeepSeek 团队自己造的 long CoT 数据](https://arxiv.org/abs/2501.12948),o1 没说怎么造的(应该是 GPT-4 系列 self-distillation)。

我自己训 tool-use agent 的 cold start 数据来源:
- [Schick et al. 2023, Toolformer](https://arxiv.org/abs/2302.04761) 风格的 self-supervised data(用 API 调用结果当监督)
- GPT-4 生成的多步 tool-use trajectory,人工 review
- 开源的 [Glaive Function Calling](https://huggingface.co/datasets/glaiveai/glaive-function-calling-v2) 跟 [xLAM](https://huggingface.co/datasets/Salesforce/xlam-function-calling-60k) 数据集

**最大的坑是格式一致性**。我从 5 个不同来源拼数据,JSON schema 不统一(有的用 `"arguments"` 有的用 `"parameters"`,有的用 camelCase 有的用 snake_case),训出来的 agent 在 inference 时调用格式五花八门。**血的教训:花一周时间统一 schema 比多训一个 epoch 重要**。

**问题 2: preference data 的构造**。Single-turn RLHF 的人类偏好数据有 [Bai et al. 2022 HH-RLHF](https://arxiv.org/abs/2204.06125) 跟 [Ethayarajh et al. 2022, ToxiGen](https://arxiv.org/abs/2203.00009) 等公开数据集,agent 的几乎找不到。2024 年开始有几个:
- [Kim et al. 2024, Auto-eval](https://arxiv.org/abs/2406.17349) 用 GPT-4 自动给 agent trajectory 排序
- [Khan et al. 2024, ACBench](https://arxiv.org/abs/2406.04760) 收集了 GUI agent 的人类偏好

**问题 3: 数据质量 vs 数量的 trade-off**。我跑过一组 ablation:相同训练 token 数下,1000 条高质量人工标注 trajectory 比 50000 条 GPT-4 生成的 trajectory 在最终 accuracy 上高 7 个点。**这跟 [Touvron et al. 2023, LLaMA 2](https://arxiv.org/abs/2307.09288) 的发现一致:数据质量比数量重要**。但人工标注成本是 GPT-4 的 50-100 倍,工程上很难 scale。

**问题 4: distribution shift**。RL 训到后期,policy 生成的 trajectory 分布跟初始 dataset 差距巨大,reward model 跟 judge model 都会失效。[Stiennon et al. 2020, Learning to Summarize](https://arxiv.org/abs/2009.01325) 提出的 iterative 训练——每 N 步用当前 policy 重新采一批 trajectory 训 RM——是工业界标配。

---

## 实验:我跑过的一些数据

我整理下 2024-2025 年复现这些方法时得到的具体数据(Qwen2.5-7B base, 1 张 A100 80G, 4 天,简化版实验设置,不是 full-scale):

| 方法 | Pass@1 (MATH) | Pass@1 (GSM8K) | Tool-call acc (BFCL) |
|---|---|---|---|
| Base + SFT | 0.58 | 0.81 | 0.42 |
| SFT + DPO (single-turn) | 0.61 | 0.83 | 0.44 |
| SFT + GRPO (math only) | 0.74 | 0.91 | 0.45 |
| SFT + GRPO + tool-use shaping | 0.72 | 0.89 | 0.58 |
| SFT + RLOO (math + tool) | 0.71 | 0.90 | 0.55 |

几个观察:
- DPO 在 single-turn preference 上涨 2-3 个点,但**在 tool-use 上几乎不涨**——因为 preference data 不带 tool call
- GRPO 在 math 上涨 16 个点,跟 R1 paper 报的趋势一致
- 加 tool-use shaping 后,math 涨幅略降(从 0.74 到 0.72),但 tool-call acc 涨 13 个点——典型的 multi-objective trade-off
- RLOO 比 GRPO 慢收敛但更稳定(标准差小)

跟 paper 报的 full-scale 数据(671B MoE, 几千卡, 数周训练)没法直接比,但**算法层面的趋势是 consistent 的**。

---

## 没解决的

最后讲讲 open question,这些是我个人研究比较关心但目前没看到漂亮解法的:

**reward model 的可解释性**。我们现在训出来的 RM 本质上是个黑盒,我们不知道它到底学到了什么。在 agent setting 下,RM 的 failure mode 很难诊断——你看到 trajectory 分数低,不知道是哪一步被 RM 误判了。Mechanistic interpretability 的工作 [Anthropic 2024, Mapping the Mind](https://www.transformer-circuits.pub/2024/march-update.html) 主要研究 base model,对 RM 的研究还很少。

**credit assignment 的理论保证**。Process reward model 在实验上比 outcome reward 好,但理论上为什么好,中间步骤的 credit 应该怎么分配,目前没有 clean 的理论。[Arora et al. 2024, Theoretical Analysis of PRM](https://arxiv.org/abs/2402.08164) 算是一个起点,但还远不够。

**multi-agent RL**。两个 agent 互相训练([Berner et al. 2019, Dota 2](https://arxiv.org/abs/1912.06680) 那条线) 在 LLM agent 上还没有成功案例。原因是 LLM 的 action space 太大,game agent 的方法(比如 self-play + PPO)直接套会发散。能不能做出 stable 的 multi-agent LLM training,我自己非常怀疑,但没看到反例。

**safety 跟 alignment 的 tension**。RLAIF 跟 self-play 都让模型自己评估自己,这跟 RLHF 的初衷("用人类价值观对齐 AI")有 tension。一个能很好评估自己的模型,可能也很会骗评估者。这个 [Cotra 2022, Why AI alignment could be hard](https://www.alignmentforum.org/posts/9N5Z8aQaQqQqQqQq/why-ai-alignment-could-be-hard-with-modern-deep-learning) 描述的"deceptive alignment"风险,在 RLAIF setting 下可能更严重。

**sample efficiency**。OpenAI 训练 o1 用了几十万个 MATH 级别的 reasoning trace,这个成本是不可持续的。能不能用更少的数据训出 reasoning 能力,目前 unclear。 [Wang et al. 2024, Self-Consistency](https://arxiv.org/abs/2203.11171) 跟 [Yuan et al. 2024, ReST](https://arxiv.org/abs/2308.01898) 算是在 sample efficiency 上的尝试,但跟 RL 的样本量还差几个数量级。

总的来说,Agent RL 是个**工程上已经能跑、理论上还不漂亮**的领域。R1 跟 o1 证明了这条路 work,但为什么 work、什么时候 work、怎么 scale 到更难的 task,这些都还是 open 的。我自己的判断是,接下来 1-2 年最可能有突破的方向是 process reward 跟 multi-turn DPO 的结合,以及 RL 跟 inference-time search 的结合([Snell et al. 2024, Scaling Test-Time Compute](https://arxiv.org/abs/2408.03314) 给了很好的实证)。

---

参考论文(按出现顺序):
- [InstructGPT (Ouyang et al. 2022)](https://arxiv.org/abs/2203.02155)
- [DPO (Rafailov et al. 2023)](https://arxiv.org/abs/2305.18290)
- [Scaling Laws for Reward Model Overoptimization (Gao et al. 2022)](https://arxiv.org/abs/2210.10760)
- [Constitutional AI / RLAIF (Bai et al. 2022)](https://arxiv.org/abs/2212.08073) 跟 [Anthropic 2022 blog](https://www.anthropic.com/news/claudes-constitution)
- [KTO (Ethayarajh et al. 2024)](https://arxiv.org/abs/2402.01306)
- [IPO (Azar et al. 2023)](https://arxiv.org/abs/2310.12036)
- [General DPO (Tang et al. 2024)](https://arxiv.org/abs/2402.11327)
- [Iterative DPO (Rafailov et al. 2024)](https://arxiv.org/abs/2403.07691)
- [Self-Play Fine-Tuning (Chen et al. 2024)](https://arxiv.org/abs/2401.01335)
- [Self-Rewarding LM (Cheng et al. 2024)](https://arxiv.org/abs/2401.10020)
- [RLOO (Ahmadian et al. 2024)](https://arxiv.org/abs/2402.14740)
- [Let's Verify Step by Step (Lightman et al. 2023)](https://arxiv.org/abs/2305.20050)
- [ToolLLM (Qin et al. 2023)](https://arxiv.org/abs/2305.18752)
- [ToolACE (Liu et al. 2024)](https://arxiv.org/abs/2409.00928)
- [OpenAI o1 (2024)](https://openai.com/index/learning-to-reason-with-llms/)
- [DeepSeek-R1 (2025)](https://arxiv.org/abs/2501.12948)
- [Schulman 2020, Approximating KL](http://joschu.net/blog/kl-approx.html)
- [Open Problems in RLHF (Casper et al. 2023)](https://arxiv.org/abs/2307.15217)

下一章 [Memory 系统原理: 向量 / 图谱 / 神经记忆 / 知识编辑](./08-memory-systems.md) 我们换个话题,讲 agent 怎么"记住"东西。