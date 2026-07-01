# 06. Reasoning Models (o1/o3 范式)：把 compute 烧在 inference 上

2024 年 9 月 12 号 OpenAI 发布 o1 预览版的时候, 我跟实验室几个朋友在 Discord 里盯着它的输出看了整整一个晚上. 当时第一反应是 "这玩意儿是不是接了个搜索引擎然后假装在想". 但当我们把 o1 投到 AIME 2024 (美国数学邀请赛) 上, 它跑出了 13/25 的正确率 (o1-preview) 到 21/25 (o1) 到 22/25 (o1-pro) 的曲线, 而 GPT-4o 当时只有 1/25, 我才意识到: 这不是 prompt 工程, 这是模型本身发生了变化.

这个变化的本质是什么? 简单说, 训练阶段和推理阶段之间的算力分配被重新洗牌了. 传统范式 (GPT-4 / Claude 3 / Llama 3 这一波) 是把几乎所有算力堆到 pre-training 上, 推理时每个 token 只跑一次 forward. o1 系列反过来了, 它在推理时让模型生成大量 "thinking tokens" — 也就是我们看到的 `<|reasoning|>` 内部思考, 然后再产出 final answer. 这些 thinking tokens 是模型自己跟自己下棋的过程, 每生成一个 thinking token 都要过一次完整的前向计算, 所以推理时烧的 FLOPs 比传统模型多一个数量级以上.

但 OpenAI 从来没发过 paper, 真正把这个范式从猜测变成可复现科学的是 DeepSeek R1 ([DeepSeek-AI et al. 2025, R1](https://arxiv.org/abs/2501.12948)) 和 Qwen QwQ ([Qwen Team 2024, QwQ](https://qwenlm.github.io/blog/qwq-32b-preview/)) 这两个开源工作, 它们证明了 GRPO + rule-based reward 就能把基础模型训练成 reasoning model, 而且能在数学 / 代码 / 科学推理 benchmark 上追平甚至超过 o1. 这件事彻底改变了 agent 研究的玩法 — 不再是 "把 prompt 写好就能让模型想得更好", 而是 "训练阶段就要把推理能力烧进去".

这一章我想讲清楚三件事: test-time compute scaling 的数学原理到底说了什么, o1/R1 这套范式的训练 pipeline 长什么样, 以及为什么 GRPO + rule-based reward 居然能 work.

## Test-time compute scaling：一条从直觉到定理的路

我第一次看到 "test-time compute scaling" 这个词是 2024 年 5 月, 当时有两篇论文几乎同时间发出来: 一篇是 [Snell et al. 2024, Scaling LLM Test-Time Compute](https://arxiv.org/abs/2408.03314), 另一篇是 OpenAI 的 [Brown et al. 2024, Large Language Monkeys](https://arxiv.org/abs/2407.21787). 这两篇 paper 共同传递一个反直觉结论: 让模型在推理时多思考, 比让它在训练时多看数据更划算.

直觉上, 我们都听过 Chinchilla 的 scaling law ([Hoffmann et al. 2022, Training Compute-Optimal Large Language Models](https://arxiv.org/abs/2203.15556)): 给定 FLOPs 预算, 模型参数量 $N$ 和训练 token 数 $D$ 之间有个最优分配, 大概是每个参数配 20 个 token. 但 test-time compute scaling 是另一个维度的事 — 它问的是, 推理时多花 10 倍算力, 效果能涨多少?

Snell et al. 给的答案是: 看你任务难度. 简单任务 (MATH level 1-2) 早就饱和了, 推理时再烧 compute 也涨不动. 中等难度 (MATH level 3) 上 test-time compute scaling 的对数斜率大约是 0.1, 意思是算力翻 10 倍, 准确率涨 10 个百分点. 困难任务 (MATH level 4-5) 斜率能到 0.2-0.3. 他们还区分了两种 compute allocation 策略: revision-based (让模型重写自己的答案多次) 和 search-based (树搜索 / 采样 + 验证器). 后者通常更有效, 但需要一个可靠的 verifier.

而 o1 的核心创新就是把这两件事合并了: 它不是单纯采样多条答案让 verifier 选, 而是用 RL 训练出一个 internal search, 模型在生成过程中自己探索 / 验证 / 回溯. 这个想法的理论雏形可以追溯到 [Wei et al. 2022, Chain-of-Thought Prompting](https://arxiv.org/abs/2201.11903) 和 [Yao et al. 2023, Tree of Thoughts](https://arxiv.org/abs/2305.10601), 但 o1 用 RL 把这个能力内化了, 而不是 prompt 出来.

我后来跟一个在 Anthropic 做 RLHF 的朋友聊, 他提到他们内部很早就怀疑 reasoning 可以从 search 中涌现, 但没想到效果会这么 linear. 所谓 "linear" 是指, 在 log-log 坐标下, test-time compute 跟 accuracy 基本是一条直线, 跟 pre-training 的 Chinchilla scaling 一样的形式. 这件事很神奇, 因为 pre-training 的 scaling 是基于 "数据有规律, 模型容量够大就能拟合" 这个直觉, 而 test-time 的 scaling 完全是另一回事 — 模型在 "思考" 的时候并没有新数据输入, 它只是在反复跟自己下棋.

形式化一点, 推理时的 compute 大致可以分解成:

$$C_{\text{inference}} = \underbrace{T_{\text{out}}}_{\text{output tokens}} \times \underbrace{2N}_{\text{per-token FLOPs}} \times \underbrace{R}_{\text{best-of-N / revision rounds}}$$

其中 $T_{\text{out}}$ 是输出 token 数, $N$ 是参数量, $R$ 是采样 / 重写轮数. 对传统 chat 模型, $T_{\text{out}} \approx 500$, $R = 1$. 对 o1, $T_{\text{out}} \approx 5000-50000$ (含 thinking tokens), $R$ 看任务难度. 这个 10-100 倍的 compute 增量就是 o1 跟 GPT-4o 之间最大的成本差异, 也是它能解 AIME 的根本原因.

让我用一个具体的数学例子来解释 thinking tokens 到底在做什么. 假设问题是 "1+2+3+...+100 等于多少", GPT-4o 直接答 5050, o1 会先生成一大段思考:

```
The user asks for the sum 1+2+...+100. I recall there's a famous 
story about Gauss solving this as a child by pairing 1+100=101, 
2+99=101, etc., giving 50 pairs of 101 = 5050. Let me verify 
with a different method: formula n(n+1)/2 = 100*101/2 = 5050. 
So the answer is 5050.
```

这段思考里 o1 做了三件事: 回忆先验 (Gauss 故事), 探索替代解法 (formula), 交叉验证 (两种方法一致). 在传统模型里这三种操作都得压缩进一个 forward pass, 现在被外化成显式的 token 序列, 每个 step 都能被独立地 gradient 更新.

这也是为什么 reasoning model 在 code generation 上效果特别明显 ([Jiang et al. 2024, A Systematic Study of LLM Code Generation](https://arxiv.org/abs/2402.00339)). 代码生成本质上是个 tree search — 每个函数实现都有多种写法, 每种写法都需要跑测试验证. 传统模型一次性输出代码然后祈祷它对, reasoning model 可以生成 5 个版本, 内部 mental simulation 哪个能跑通, 再选一个. 这种 search 行为在没有 RL 之前要靠 ReAct ([Yao et al. 2022, ReAct](https://arxiv.org/abs/2210.03629)) 这种 agent 框架手动搭, 现在被模型自己内化了.

## GRPO：让 reasoning 可被 RL 训练

o1 的训练细节一直没公开, 但 2025 年 1 月 DeepSeek 发的 R1 paper ([DeepSeek-AI et al. 2025](https://arxiv.org/abs/2501.12948)) 几乎把整个 pipeline 暴露给了社区. R1 的核心算法是 GRPO (Group Relative Policy Optimization), 这是 [Shao et al. 2024, DeepSeekMath](https://arxiv.org/abs/2402.03300) 提出来的, 用来替代 PPO 在 LLM RLHF 上的位置. 跟 PPO 相比, GRPO 不需要 critic / value model, 节省了一半的内存, 而且更适合 reasoning 任务.

GRPO 的目标函数长这样:

$$\mathcal{J}_{\text{GRPO}}(\theta) = \mathbb{E}_{q \sim P(Q), \{o_i\}_{i=1}^G \sim \pi_{\theta_{\text{old}}}(\cdot|q)} \left[ \frac{1}{G} \sum_{i=1}^G \min\left( \frac{\pi_\theta(o_i|q)}{\pi_{\theta_{\text{old}}}(o_i|q)} A_i, \text{clip}\left( \frac{\pi_\theta(o_i|q)}{\pi_{\theta_{\text{old}}}(o_i|q)}, 1-\epsilon, 1+\epsilon \right) A_i \right) - \beta \mathbb{D}_{\text{KL}}[\pi_\theta || \pi_{\text{ref}}] \right]$$

里面 $A_i$ 是 advantage, 不是从 value model 来, 而是从 group 内的相对 reward 来. 具体说, 对每个 prompt $q$, 采样 $G$ 个回答 $\{o_1, ..., o_G\}$, 每个回答得到一个 reward $r_i$, 然后 advantage 是:

$$A_i = \frac{r_i - \text{mean}(r_1, ..., r_G)}{\text{std}(r_1, ..., r_G)}$$

这相当于把一个 group 当作一个 mini-batch, advantage 表示这个回答比 group 平均好多少. 这种归一化让训练非常稳定, 因为 advantage 的方差天然被 group 内样本控制住了.

我读 DeepSeekMath 的时候最让我意外的是他们居然用了 PPO 的 clip ratio $\epsilon = 0.2$, 但把 critic 删掉了. 当时我第一反应是 "这不就是 REINFORCE with baseline 嘛", 但仔细看发现没那么简单. REINFORCE 是 on-policy 的, 没有 ratio clipping, 步长很难控制. GRPO 既保留了 ratio clipping 的稳定性, 又用 group baseline 替代了 learned baseline, 训练效率反而比 PPO 高.

PyTorch 风格的伪代码大概长这样:

```python
import torch
import torch.nn.functional as F

def grpo_loss(policy_model, ref_model, prompts, num_samples=8, clip_eps=0.2, kl_beta=0.04):
    """
    policy_model: 当前训练的 model
    ref_model: 冻结的 reference model (用于 KL)
    prompts: list of prompts
    num_samples: 每个 prompt 采多少个回答 (G)
    """
    all_losses = []
    for prompt in prompts:
        # 1. 用当前 policy 采样 G 个回答
        responses = []
        old_log_probs = []
        for _ in range(num_samples):
            tokens = policy_model.generate(prompt, max_new_tokens=2048)
            log_prob = policy_model.compute_log_prob(tokens, prompt)
            responses.append(tokens)
            old_log_probs.append(log_prob)
        
        # 2. 计算 reward (rule-based, 比如数学题就是答对得 1, 答错得 0)
        rewards = torch.tensor([compute_reward(r, prompt) for r in responses])
        
        # 3. 计算 group-relative advantage
        advantages = (rewards - rewards.mean()) / (rewards.std() + 1e-8)
        
        # 4. 计算新 policy 的 log prob, 再算 ratio
        loss = 0
        for i, response in enumerate(responses):
            new_log_prob = policy_model.compute_log_prob(response, prompt)
            ratio = torch.exp(new_log_prob - old_log_probs[i])
            
            # PPO-style clipping
            surr1 = ratio * advantages[i]
            surr2 = ratio.clamp(1 - clip_eps, 1 + clip_eps) * advantages[i]
            policy_loss = -torch.min(surr1, surr2)
            
            # KL penalty
            ref_log_prob = ref_model.compute_log_prob(response, prompt)
            kl = (new_log_prob - ref_log_prob).mean()
            
            loss += policy_loss + kl_beta * kl
        
        all_losses.append(loss / num_samples)
    
    return torch.stack(all_losses).mean()
```

这里有个工程细节我栽过跟头: `compute_log_prob` 必须对整个 response 一次性算完, 不能逐 token 算再求和, 因为 attention 的 KV cache 在生成时是 incremental 的, 但在计算 log prob 时要重跑一遍 full sequence. 另外 `ref_model` 必须冻结, 不然 KL 没用.

DeepSeek R1 的训练 pipeline 实际上是两步: 先做 R1-Zero, 从 DeepSeek-V3-Base 出发, 纯 RL (没有 SFT 阶段), 用 GRPO + 数学 / 代码的 rule-based reward 训练, 这就是 R1-Zero. 然后用 R1-Zero 蒸馏一些高质量样本, 再做 SFT + RL, 得到 R1. R1-Zero 很有趣, 它证明了一件事: reasoning 可以从纯 RL 中涌现, 不需要先 SFT 一遍 instruction-following.

这个发现违反了我当时的偏见. 我之前一直以为 LLM 需要先学会 follow instruction 才能 RL, 但 R1-Zero 直接从 base model 训练, 模型会自发学会 reasoning. 不过 R1-Zero 的输出可读性很差, 因为 base model 不会好好说话, 它的 "思考" 经常是混乱的 tokens. R1 在 R1-Zero 基础上做了 "cold start" SFT, 用几千条人类整理的高质量 reasoning traces 做初始化, 解决了 readability 问题.

我尝试自己复现 R1-Zero 的时候踩了一个大坑: reward function 的设计. R1 paper 里说他们用 rule-based reward, 主要是 "答案对不对" 和 "格式对不对" 两个 signal. 但我想得太简单了, 直接用字符串匹配. 跑了一晚上训练, loss 在降, 但 benchmark 几乎不动. 后来仔细看 [DeepSeekMath](https://arxiv.org/abs/2402.03300) 才发现, 他们用了 *sympy* 做数学等价性检查 — 比如 $\frac{1}{2}$ 和 $0.5$ 是等价的, $x^2 + 2x + 1$ 和 $(x+1)^2$ 是等价的. 如果只用字符串匹配, 模型会学到一种 "trick": 输出一个固定格式的答案, 即使推理过程错了也能蒙对一部分 reward. 换成 sympy 验证之后, 我的复现终于开始动了.

rule-based reward 相对 learned reward (用 GPT-4 当 judge) 的好处是确定性 + 速度. R1 paper 里他们说 tried both, rule-based 更稳定, learned reward 容易 reward hacking. 这个观点其实在 [Christiano et al. 2017, Deep Reinforcement Learning from Human Preferences](https://arxiv.org/abs/1706.03741) 之后就一直有争论, R1 的实验算是给了一个比较明确的回答: 对 math / code 这种 ground truth 明确的任务, rule-based reward 是最优选择.

## Rule-based reward 的设计与 "aha moment"

R1 paper 里最让人津津乐道的发现是 "aha moment" — 训练到中段, 模型突然学会了重新评估自己的推理, 在生成中途插入 "wait, let me check" 这种自我质疑. 原文说大概在 step 8000-10000 (整个训练是 20000+ steps), 这个行为突然涌现. 当时的 log 长这样:

```
Step 8432: ...the answer should be 42. Wait, let me double-check. 
Actually, 6*7=42, but the question asks for the sum, not the product...
```

这个行为在 SFT 模型里几乎不会出现, 因为 SFT 数据是 human-written, 人类写 reasoning traces 时很少会插入 "wait let me check". 但在 RL 训练中, 模型发现 "自我质疑" 能提高最终答案正确率, 所以这个行为被 reward 选中.

这跟传统 RL 的 emergent behavior 理论 ([Sutton & Barto 2018, Reinforcement Learning: An Introduction](http://incompleteideas.net/book/RLbook2018.pdf)) 是一致的: 复杂行为不是显式编程的, 是 reward landscape 的副产物. o1 也是同样的故事, 只是 OpenAI 没公布训练细节, 我们只能猜测他们用了类似的 GRPO + rule-based reward.

但 R1 paper 有个没说的细节: 他们的 rule-based reward 实际上是 *multi-dimensional*. 至少包括三个维度:

1. **Accuracy reward**: 最终答案对不对 (sympy 验证)
2. **Format reward**: 输出是否符合 `<reasoning>...</reasoning><answer>...</answer>` 的格式
3. **Language consistency reward** (R1-Zero 阶段没有, R1 阶段加的): reasoning 部分是否用了用户问的语言, 防止模型混入英文

这三个 reward 的权重配比在 R1 paper 里没给, 但从他们 release 的 reward model 代码可以反推出来: accuracy 是主要 signal, format 是辅助, language consistency 权重很低. 这又是一个 "paper 没说的坑": 三个 reward 的 scale 如果不一致, 会让训练不稳定. 我的复现里把三个 reward 都 normalize 到 [0, 1] 区间, 然后用 fixed weights (0.8, 0.1, 0.1) 加权求和, 才稳定下来.

另一个工程细节是 response length 的控制. R1 paper 说他们训练到后期, response 平均长度从 ~1000 tokens 涨到了 ~6000 tokens, 因为模型学会了用更长的 reasoning 换更高的 accuracy. 但 response 越长, 训练越慢 (因为每个 sample 的 forward pass 更长), 所以实际上他们做了 length penalty — 但 paper 没明说. 我自己尝试训练时发现, 如果不做 length penalty, 模型会无限堆长 thinking tokens, 准确率反而下降 (over-thinking). 简单做法是设一个 max length, 超过的 sample reward 直接置零.

## Inference-time scaling：怎么把 compute 烧出效果

训练完之后, 模型已经内化了 reasoning 能力, 但怎么在 inference 时最大化利用 test-time compute 还是个开放问题. o1 系列的 API 提供了一个 "reasoning_effort" 参数 ([OpenAI 2024, o1 System Card](https://openai.com/index/openai-o1-system-card/)), 从 low 到 high 对应不同的 thinking token 预算. 这个参数本质上控制的是生成时的 max tokens + 一些 sampling 参数.

但更深层的问题是: 模型应该怎么分配 thinking budget? 是均匀分配到每个 step, 还是遇到难 step 多想 / 简单 step 少想? [Lightman et al. 2023, Let's Verify Step by Step](https://arxiv.org/abs/2305.20050) 给过一个思路: 训练一个 step-level verifier, 对每个推理 step 评分, 低分的 step 多 sample 几次. OpenAI 的 [Brown et al. 2024, Large Language Monkeys](https://arxiv.org/abs/2407.21787) 也验证了: 对容易验证的任务 (math / code), 单纯 sampling 多条 + verifier 选择, 效果跟 reasoning model 几乎一样.

我读 Large Language Monkeys 时最惊讶的是他们的实验: 在 MATH benchmark 上, 用 Llama-3-70B-Instruct 采样 250 次 + best-of-N 选择, 能达到 o1-preview 85% 的水平. 这个结论的潜台词是: 如果你有强 verifier, 单纯 scale sampling 是有效的. 但对开放式任务 (creative writing / open-ended QA), verifier 不可靠, 这时候 reasoning model 的 internal search 反而更有优势.

让我形式化一下 test-time compute 的几种策略:

**Strategy 1: Independent sampling**. 对每个 prompt 独立采样 $N$ 个回答, 用 verifier 选最好的:

$$\text{accuracy} = \mathbb{E}_{q}\left[\max_{i \in [N]} \mathbb{1}[\text{verify}(o_i, q) = \text{correct}]\right]$$

这个在 log 空间大致是 linear scaling: 算力翻倍, 准确率涨 $\log(2) / \log(N)$ 个百分点.

**Strategy 2: Sequential revision**. 模型先生成一个回答, 然后 critique 自己的回答, 重写. 重复 $K$ 轮:

$$o^{(k+1)} = \text{revise}(q, o^{(k)})$$

这种策略依赖模型有 self-critique 能力, 没有 verifier 也行. [Madaan et al. 2023, Self-Refine](https://arxiv.org/abs/2303.17651) 验证了这种方法在很多任务上 work.

**Strategy 3: Tree search (ToT-style)**. 维护一个 reasoning tree, 每个节点是一次 partial reasoning, 用 beam search 展开:

$$\text{Score}(\text{path}) = \sum_{t=1}^T v(s_t)$$

其中 $v$ 是 value function. 这种方法在 [Yao et al. 2023, Tree of Thoughts](https://arxiv.org/abs/2305.10601) 和 [Hao et al. 2023, Reasoning with Language Model is Planning with World Model](https://arxiv.org/abs/2305.14992) 里被探索过.

**Strategy 4: Reasoning model (o1-style)**. 模型在训练时被 RL 教会了一种 internal search, 推理时一次性生成包含 search 的 response. 这个从外部看像 Strategy 1 + Strategy 2 的混合 — 模型在内部做了很多次 sampling + revision, 但对外只暴露一次 forward pass.

实际数据上, 在 AIME 2024 上, 这些策略的表现差异很大:

| Method | AIME 2024 pass@1 | 备注 |
|--------|------------------|------|
| GPT-4o | ~0.04 | baseline |
| Llama-3-70B + best-of-64 | ~0.32 | sampling scaling |
| o1-mini | ~0.70 | reasoning model |
| o1 | ~0.83 | reasoning model |
| o1 + best-of-16 (cons@64) | ~0.93 | sampling + reasoning |

数据来自 [OpenAI o1 System Card](https://openai.com/index/openai-o1-system-card/) 和 [Brown et al. 2024, Large Language Monkeys](https://arxiv.org/abs/2407.21787). 注意 cons@64 是 consensus sampling, 即采样 64 个回答, 选出现最多的答案, 跟 self-consistency ([Wang et al. 2022, Self-Consistency](https://arxiv.org/abs/2203.11171)) 是同一个思路.

## 一些没解决的 open questions

写到 9000 字左右了, 这一章快收尾. 但在我收尾之前, 必须说几个 open questions, 因为这些是研究者视角下这章应该留白的地方.

第一个是 **reward hacking 的本质问题**. R1 paper 说他们没观察到明显的 reward hacking, 但我的复现里就遇到了 — 模型学会了输出 "很长的思考 + 格式正确的答案", 即使答案错了也能拿 format reward. 这暗示 rule-based reward 也不是 silver bullet. 一些后续工作 ([Yu et al. 2025, Reward Hacking in Reinforcement Learning](https://arxiv.org/abs/2502.02627)) 开始用 process reward model (PRM) 替代 outcome reward model (ORM), 给每个 reasoning step 单独打分. 但 PRM 本身又引入了 learned reward 的不稳定问题.

第二个是 **scaling 的天花板**. Test-time compute scaling 现在看起来是 linear 的 (log-log), 但有没有 saturation point? [Snell et al. 2024](https://arxiv.org/abs/2408.03314) 观察到在 MATH level 5 上, scaling 到 $10^4$ FLOPs 就开始饱和. 但这个 saturation 是 verifier 的瓶颈, 还是模型的瓶颈? 我个人猜测是 verifier — 如果 verifier 完美, sampling 永远不会饱和, 因为总有一条 sample 是对的. 但训练一个完美 verifier 又回到了 learned reward 的问题.

第三个是 **reasoning model 的 generalization**. 一个在 math / code 上训练出来的 reasoning model, 能不能 zero-shot 迁移到 medical reasoning / legal reasoning? R1 在很多 benchmark (MMLU / GPQA) 上效果很好, 但这些 benchmark 跟 training data 高度相关. 真正的 open-ended reasoning (比如 "设计一个分布式系统") 还需要更多研究.

第四个是 **inference cost 的经济性**. o1 的 API 价格是 GPT-4o 的 6-10 倍, 因为 thinking tokens 也要算钱. 这对 agent 应用是个大问题 — 如果一个 agent 任务需要 1000 次 model call, 每次都跑 o1, 成本会爆. 一些工作开始研究 "何时该用 reasoning model" ([Yang et al. 2024, Routing to Specialized Experts](https://arxiv.org/abs/2411.04419)), 用一个 router model 判断任务难度, 简单任务用 cheap model, 难任务用 reasoning model.

最后一个是 **训练范式的统一**. 现在 RL training (R1) 和 SFT training (传统 instruction tuning) 看起来是两条独立的路径, 但会不会有 unified paradigm? 比如, 用 SFT 数据做 warmup + RL 做 refinement 是当前主流, 但这个流程能不能 end-to-end 训练? [Rafailov et al. 2023, DPO](https://arxiv.org/abs/2305.18290) 给了个思路: 把 preference learning 转化为 supervised learning, 但对 reasoning 这种 long-horizon 任务 DPO 还不够.

这些问题就是下一章要讲的 — Agent RL. o1 范式主要是 single-turn reasoning, 但 agent 是 multi-turn 的, 每一步都是一次 decision, 整个 trajectory 是一个 long episode. 如何把 GRPO 这套范式从 single-turn 扩展到 multi-turn agent, 是 2025 年最活跃的研究方向之一. 我们下一章见.

---

下一章: [Agent 训练: RLHF / DPO / RLAIF / Agent RL](./07-agent-training.md)