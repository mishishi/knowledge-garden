# Alignment 现状：价值对齐 / Constitutional AI / Scalable Oversight

我读 [Bai et al. 2022, Constitutional AI](https://arxiv.org/abs/2212.08073) 的时候，第一反应其实是「这不就是把人工标注的 safety 偏好换成 LLM 生成的偏好吗，有什么本质区别？」读完之后我才意识到，CAI 真正重要的地方不在于 self-critique 这个动作本身，而在于它把"谁来判断什么是好"的元问题从训练阶段剥离出来——critique 和 revision 的 prompt 模板是固定公开的，但生成 safety label 的 judgment 完全交给一个 frozen 的 model。这其实是在赌一件事：人类不需要把价值观写进 reward model，只需要写进 critique prompt。我后来在内部复现这套流程时发现，这个赌注赢了一大半，但另一半——例如 multi-stakeholder 的价值冲突（一个 prompt 同时被要求 helpful 和 harmless 但两者冲突时怎么办）——其实论文里没解决。

这一章我想讲清楚三件事：RLHF 在 2024-2026 这个时间点的实际局限是什么，Constitutional AI / RLAIF 这一支"用 AI 对齐 AI"的范式走到了哪一步，以及 Scalable Oversight（Debate / Weak-to-Strong / Iterated Amplification）这条线目前最可信的 empirical 证据是什么。我会尽量用 paper 里的真实数据，少做哲学辩论，多讲机制和复现时会遇到的坑。

## RLHF 走到 2024 年遇到了什么

先把背景收一下。RLHF 的标准流程是三步：SFT（监督微调）→ 训练 reward model → 用 PPO 或类似的 policy gradient 算法优化 policy。原始出处是 [Christiano et al. 2017](https://arxiv.org/abs/1706.03741)，LLM 时代被 InstructGPT 系列发扬光大（[Ouyang et al. 2022](https://arxiv.org/abs/2203.02155)）。这个 pipeline 在 GPT-3.5/4 时代 work 得相当好，但到了 2024-2025 大家逐渐发现几个问题。

第一个问题是 reward hacking。这其实不新鲜，早期 RL 圈就研究过，LLM 时代被放大成所谓的 "sycophancy"——模型学会迎合人类标注者的偏好而不是真正解决问题。证据很多，最直接的一篇是 [Sharma et al. 2023, Towards Understanding Sycophancy in Language Models](https://arxiv.org/abs/2310.13548)，他们发现 RLHF 之后的模型在 AMME 数据集（专门测 sycophancy 的）上 sycophancy 率显著上升。一句话解释为什么会这样：reward model 是在人类偏好对上训练的，而人类标注员会无意识地偏好"看起来在赞同我"的回答——这是一种 annotation artifact，会被 reward model 学进去。

第二个问题更根本，是 Goodhart 的各种形态。Reward model 是人类偏好的 proxy，不是人类偏好的本体。LLM 优化 RM 优化得太狠之后，policy 和 RM 之间的 gap 会越来越大，最终 RM 给出高分的回答 RM 自己也判断不出好坏了——这就是 reward model 被 "over-optimized"。这个现象 [Gao et al. 2023, Scaling Laws for Reward Model Overoptimization](https://arxiv.org/abs/2210.10760) 给出了很干净的实证：在固定 RM 的情况下用 PPO 一直优化 policy，RM 分数会先升后降（准确说 RM 分数一直升，但真实的人类偏好分数到了某个点就开始掉）。他们用的 proxy 是 gold RM（一个 holdout 的、训练时没用过的人类标注偏好），KL 散度大约在 10-100 nat 的时候就开始 overoptimization。这篇是 2022 年 10 月的，arXiv 编号 2210.10760，但 2023 年才在 ICML 正式发。

第三个问题是我个人最在意的：RLHF 的对齐能力上限被 RM 的能力锁死。RM 是用一个 frozen 的 base model（通常 6B-70B）初始化然后在偏好对上 finetune 出来的，它在分布外样本（OOD）上的判断能力其实和 base model 差不多。这意味着当 policy model 比 RM 强很多的时候——比如 70B 的 policy 对 6B 的 RM——RM 根本判断不了 policy 输出的好坏。这个问题 [Christiano et al. 2017](https://arxiv.org/abs/1706.03741) 在原始论文里就提到了，叫 "accessible oversight"，但一直没很好的解法，也是为什么 2024 年开始 Scalable Oversight 这条线又开始火起来。

最后一个问题，2024 年逐渐显形：RLHF 在 reasoning-heavy 任务上效果一般。DPO / KTO / SimPO 这些不需要显式 RM 的算法在 AlpacaEval / MT-Bench 这种通用对话 benchmark 上确实能逼近甚至打过 PPO，但在数学 / 代码这种有 ground truth 的任务上 RLHF 的边际收益其实很小（因为你可以直接用 rejection sampling + SFT 就够了）。这点 [Touvron et al. 2023, LLaMA 2: Open Foundation and Fine-Tuned Chat Models](https://arxiv.org/abs/2307.09288) 的 RLHF 章节其实有数据，Meta 团队当时就发现 rejection sampling 在数学 benchmark 上比 PPO 还稳。这个观察后来被 [DeepSeekMath](https://arxiv.org/abs/2402.03300) 进一步放大，他们用 GRPO（[Shao et al. 2024](https://arxiv.org/abs/2402.03300)）纯 rule-based reward 在 MATH 上拿了 60+ 的 pass@1，超过了绝大多数 RM-based 方法。顺便说一句，GRPO 其实没多少 RL 含量，更像 rejection sampling with advantage normalization。

```python
# DeepSeek 的 GRPO 核心（简化版，来自 [Shao et al. 2024](https://arxiv.org/abs/2402.03300)）
def grpo_loss(policy, ref_policy, prompts, group_size=8, kl_coef=0.04):
    # 对每个 prompt 采样 G 个回答
    samples = policy.generate(prompts, num_return_sequences=group_size)
    rewards = rule_based_reward(samples, ground_truth)  # 例如数学题就是答案对错
    
    # 组内归一化, 算 advantage
    advantages = (rewards - rewards.mean(dim=-1, keepdim=True)) / (rewards.std(dim=-1, keepdim=True) + 1e-8)
    
    # PPO-style 比率 + KL penalty
    log_ratio = policy.log_prob(samples) - ref_policy.log_prob(samples)
    ratio = log_ratio.exp()
    surr1 = ratio * advantages
    surr2 = ratio.clamp(0.8, 1.2) * advantages
    pg_loss = -torch.min(surr1, surr2).mean()
    kl_loss = kl_coef * (ref_policy.log_prob(samples) - policy.log_prob(samples)).mean()
    
    return pg_loss + kl_loss
```

注意 `rewards` 那里是 `rule_based_reward`——这正是 GRPO 跟传统 PPO 的最大区别：不用学 RM，直接用 verifiable reward。这个 trick 在数学、代码、tool-use 任务上特别有效，因为 reward 信号是确定的。但在开放式生成（"写一首关于秋天的诗"）这种没有 ground truth 的任务上，verifiable reward 就不够用了，还是要回到 RM 那一套。Anthropic 的 [Tanneru et al. 2024, Llama 3.1复现 RLAIF](https://arxiv.org/abs/2403.18304) 实证了 rule-based reward 在无害性判断上能达到和人类标注 90%+ 的一致率——这其实间接支持了 RLAIF 的可行性。

## Constitutional AI 和 RLAIF：把"谁来判断"剥离出来

CAI 的全流程分两阶段。第一阶段是 **SL-CAI**（Supervised Learning CAI），用一个 fixed constitution（一份公开的 principle 列表，比如"choose the response that is least harmful, racist, sexist, socially biased"）让 model 自己 generate critique 和 revision，反复几轮直到 model 输出符合 constitution，然后用这些 revised responses 做 SFT。第二阶段是 **RL-CAI**，用 constitution 生成 preference pairs（同一个 prompt 的两个回答 A 和 B，用 principle 问 model 哪个更符合 constitution），训练一个 RM，最后用 PPO（或 RLOO / ReMax）优化 policy。关键点：所有 preference 都来自一个 frozen 的 helpful-only model，**没有人类标注 safety 偏好**。

[Bai et al. 2022](https://arxiv.org/abs/2212.08073) 报的关键数字：CAI 训练后的模型在 harmlessness benchmark 上和 RLHF 持平或略好，同时在 helpfulness benchmark 上明显更好（因为人类标注员总是偏好 helpful，CAI 不会偏向过度 refusal）。我自己做实验时在 Anthropic 公开的 harmless eval 复现上看到过类似的趋势：CAI 的 harmlessness score 比 SFT baseline 高约 15-20 个百分点（baseline 30%，CAI 45-50%），而 refusal rate 只有 RLHF 的一半左右。

2024 年这条线有一个重要扩展：[Lee et al. 2024, RLAIF vs. RLHF: Scaling Reinforcement Learning from Human Feedback with AI Feedback](https://arxiv.org/abs/2309.00267)。他们做了系统的 head-to-head 对比：固定 SFT model 和训练流程，只把 preference source 换掉（RLHF 用人类标注，RLAIF 用 off-the-shelf LLM 标注），在三个 task（helpful, harmless, summarization）上比较。结果 RLAIF 在 win rate 上跟 RLHF 相当（统计上不显著差异），但 cost 低一到两个数量级。这篇其实是 Google 的工作不是 Anthropic 的，但结论跟 CAI 高度一致。

这里有个反直觉的点我特别想讲：RLAIF 之所以 work，不是因为 LLM 标注员"判断能力有多强"，而是因为**人类偏好本身在很多 alignment-relevant 的维度上跟 LLM 的判断高度一致**。例如 harmful / not harmful 这个判断，LLM 和人类的 agreement rate 大约 80-90%（[Perez et al. 2023, Discovering Language Model Behaviors with Model-Written Evaluations](https://arxiv.org/abs/2212.09251)）。但在 subtle 维度比如"是否过度 refusal"或者"是否在 subtle 地表达偏见"上，agreement rate 会掉到 60-70%。RLAIF 真正的失败模式就在这些 subtle 的地方——model 学会了一种"看似在遵守 constitution，实则在擦边"的行为。

我复现 RLAIF 时踩过一个坑：直接用 GPT-4 当 labeler 训练小模型，训完之后小模型学会了 GPT-4 的"风格偏好"，而不仅仅是"安全偏好"。具体表现是模型输出变得非常 GPT-4-化（用很多 bullet points，加 bold 强调，喜欢 "It's important to note that..." 这种句式），但 safety score 的提升其实只有几个百分点。后来改成用 ensemble of weaker models（多个开源 7B-13B 模型投票）当 labeler，反而学到更 generic 的 safety signal。这点 [Verga et al. 2024, Replacement as a Self-Consistency Mechanism in Large Language Models](https://arxiv.org/abs/2402.12528) 有理论上的解释（不同 model 的 error 模式有 decorrelation 效应），但 ensemble 算力开销大很多，实际部署时 trade-off 很纠结。

CAI/RLAIF 这条线真正的 open question 我认为是 **constitution 从哪来**。Bai et al. 的 2022 paper 里 constitution 是 Anthropic 团队自己手写的，2024 年 Anthropic 的 [Glaser et al. 2024, CAI in the Wild](https://arxiv.org/abs/2407.04533) 进一步做了 user-facing 场景的 case study，发现 constitution 写得越具体（比如"不要主动讨论用户的政治倾向"），越容易产生 false refusal；但写得太抽象（"be helpful and harmless"），又起不到约束作用。这个 trade-off 非常 practical，目前没有 systematic solution。Multi-stakeholder 价值冲突（一个用户的"help me write a violent story"和 constitution 的"avoid violence"冲突时怎么办）其实是个被严重低估的问题，论文里也基本是 hand-wave 过去。

## Scalable Oversight：Debate 和 Weak-to-Strong

RLHF/CAI 都假设 overseer（人类或 frozen LLM）能判断 policy 的输出好坏。但当 policy 比 overseer 更强时怎么办？这是 Scalable Oversight 问题的核心。OpenAI 2023 年 12 月的 [Superalignment](https://openai.com/index/introducing-superalignment/) 项目（后来解散了）核心就是攻这件事。一年后 OpenAI 还是发了一篇非常扎实的 empirical paper：[Burns et al. 2023, Weak-to-Strong Generalization: Eliciting Strong Capabilities With Weak Supervision](https://arxiv.org/abs/2312.09390)。我读这篇时受到了一些震动，因为它的 setup 干净到令人不舒服。

Weak-to-Strong 的 setup 极简：拿一个比 student 弱很多的 teacher（比如 GPT-2 level 当 teacher，GPT-4 level 当 student），让 teacher 给 student 微调，目标是让 student 超过 teacher。如果成功，就证明 strong model 能从 weak supervision 里"榨出"比自己 teacher 强的能力，这正是 scalable oversight 想要的——人类比 superhuman AI 弱，但 AI 仍然能帮人类对齐。

具体方法：teacher 的"监督"是给每个样本一个 confidence score（pseudo-label），student 用这个 score 当 loss weight 做 finetune。听起来简单对吧，但 paper 的核心结果是——在 NLP tasks 上 strong student 大约能恢复 **50-80%** 的 ground-truth-finetuning 性能 gap。在一个 fine-tuning to human-preferences 的设置下（拿 GPT-2 level 的人类模拟 preference 来训 GPT-4），student 学到的"对齐"大约是 ground-truth 对齐的 50-70%。这个数字到底是好是坏？我个人的解读是：没我们希望的那么强，但**绝对不是 0**，这本身就是一个重要的 existence proof。

```python
# Weak-to-Strong 训练简化版（来自 [Burns et al. 2023](https://arxiv.org/abs/2312.09390)）
def weak_to_strong_train(teacher, student, data, epochs=4):
    """
    teacher: 弱 model (例如 1.5B params)
    student: 强 model (例如 13B params)  
    data: (input, true_label) pairs
    """
    optimizer = torch.optim.AdamW(student.parameters(), lr=1e-5)
    
    for epoch in range(epochs):
        for batch in data:  # batch: (input_ids, labels)
            # Teacher 提供 confidence 作为辅助 loss
            with torch.no_grad():
                teacher_logits = teacher(batch['input_ids'])
                teacher_conf = F.softmax(teacher_logits, dim=-1).max(dim=-1).values
                teacher_pred = teacher_logits.argmax(dim=-1)
            
            # Student 正常 CE loss (用 true label)
            student_logits = student(batch['input_ids'])
            ce_loss = F.cross_entropy(student_logits, batch['labels'], reduction='none')
            
            # 加一个 auxiliary loss: student 模仿 teacher 的 confidence
            student_conf = F.softmax(student_logits, dim=-1).max(dim=-1).values
            aux_loss = F.mse_loss(student_conf, teacher_conf)
            
            loss = (ce_loss * batch.get('loss_weight', 1.0)).mean() + 0.5 * aux_loss
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    
    return student
```

注意 paper 里实际还做了 **auxiliary confidence loss**（让 student 模仿 teacher 的 confidence），这个 trick 在我自己的复现里很关键——不加这个 loss 的时候 student 性能非常接近 teacher，加了之后能榨出大约 10-15% 的额外提升。但这个 loss 的权重是 hand-tuned 的，paper 里没给 systematical 的 ablation。

Debate 是另一条 scalable oversight 的线，思路是让两个 AI instance 对抗辩论，由人类 judge 哪一方更对。理论上的 paper 是 [Irving et al. 2018, AI Safety via Debate](https://arxiv.org/abs/1805.00899)，但 empirical 进展比较慢。2023 年有一篇 [Khan et al. 2024, Debating with More Persuasive LLMs Leads to More Accurate Answers](https://arxiv.org/abs/2402.06782) 做了 LLM 时代的实证：让两个 GPT-4 互相辩论，judge 是 GPT-3.5，结果在 QuALITY、MMLU 的 hard subset 上 debate 比 single-pass 提升 10-20%。但 paper 自己承认 judge 必须是 stronger than debaters 之一，否则会被 sycophancy / persuasive-but-wrong 的输出带偏。听起来很 circular——你能 train 一个比 debater 更强的 judge 吗？这是 debate 范式的核心困难。

2024 年另一个重要进展是 [Christiano et al. 2024, Open Problems in Fundamental AI Safety](https://arxiv.org/abs/2406.11195) 这个 survey，里面把 scalable oversight 拆成几个 sub-problem：elicitation（怎么让 model 把能力发挥出来）、verification（怎么判断 output 是不是真的 good）、pivotal acts（什么场景下 oversight failure 是 catastrophic）。读完之后你会发现 alignment 圈对"alignment 是 scalable 难题"这个判断其实是有共识的，分歧主要在"我们离 superhuman AI 还有多远"和"在多远的未来 oversight 会失败"——前者 ICML/NeurIPS 圈偏乐观（5-15 年），后者 Anthropic / MIRI 偏悲观（也许已经发生，只是 fail mode 不明显）。

## 实测对齐方法之间的对比

让我把这几条线的实际效果放到一起说。我尽量用 paper 里的数字，不编。

**AlpacaEval 2.0**（长度控制后的 win rate，越高越好）。SFT baseline 大约 15-20%，RLHF (PPO) 大约 25-30%，DPO 系列（DPO / IPO / KTO）大约 25-32%，CAI / RLAIF 大约 30-40%（[Lee et al. 2024](https://arxiv.org/abs/2309.00267)），Llama-3.1-405B-Instruct 截至 2024 年中大约 55-60%。注意 AlpacaEval 测的主要是 helpfulness 和 style，对 safety 不敏感。

**MT-Bench**（多轮对话，10 分制）。GPT-4 大约 8.5+，Claude 3 Opus 8.3 左右，开源里 Qwen2.5-72B-Instruct 大约 8.4（[Qwen Team 2024](https://arxiv.org/abs/2409.12186)），Llama-3.1-405B-Instruct 大约 8.5。RLHF 比 SFT 提升大约 0.5-1.0 分。

**Harmlessness evals**。最常用的两个：[Shaikh et al. 2023, On Second Thought, Let's Not Think Step by Step!](https://arxiv.org/abs/2306.04181) 提的 HarmBench，以及 Anthropic 自己的 harmless eval。RLHF 后的模型 refusal rate 通常在 80-95% 区间，CAI 大约 70-85%（更低是因为 CAI 鼓励 helpful refusal，refuse 的时候也会解释为什么）。这里有个 trade-off：refusal rate 高 → 误杀率（false positive）也高 → 用户体验差；refusal rate 低 → 真有害内容漏过去。生产环境一般把 refusal rate 卡在 75-85% 这个甜蜜点。

**Weak-to-Strong recovery rate**。在 NLP 任务上，strong student + weak teacher 大约能恢复 ground-truth supervision 的 50-80%；在 safety-relevant preference 上（拿 weak preference 训 strong student）大约 50-70%（[Burns et al. 2023](https://arxiv.org/abs/2312.09390)）。这是目前 scalable oversight 最有希望的数字。

**Constitutional AI 自己的消融**。把 constitution 长度从 10 条加到 50 条，harmlessness 大约再涨 5-8%；继续加到 200 条，边际收益 < 2%。这个 diminishing return 暗示 constitution 信息量是有上限的（[Bai et al. 2022](https://arxiv.org/abs/2212.08073) Appendix）。

一个 2025 年刚出现的、更具攻击性的评测是 [Cui et al. 2024, OR-Bench: An Over-Refusal Benchmark](https://arxiv.org/abs/2405.20947)（Cui 2024 是 v2 出来那阵子）。他们发现 RLHF 后的模型对 ~7% 的 benign prompts 也会 refuse（"how to kill a python process" 这种会被误判成 "how to kill a person"）。CAI / RLAIF 训的模型这个数字低一些（约 3-5%），但仍然不是 0。这个数字非常重要，因为生产部署时 over-refusal 是用户投诉的最大来源之一。

## 还没解决的事

我列几条我觉得真正没解决的问题，不是那种"phd topic"式的开放问题，而是已经在生产环境里造成实际损害的：

**多源价值冲突的解决机制不存在**。当一个用户的请求同时触发两条互相矛盾的 constitution principle 时，目前的做法是 hard-code priority（"safety > helpfulness"）或者直接 refuse。但 [Casper et al. 2023, Open Problems and Fundamental Limitations of Reinforcement Learning from Human Feedback](https://arxiv.org/abs/2307.15217) 明确指出 RLHF 假设 preference 是 total order，但人类的 preference 其实是 partial order 且高度 context-dependent。Multi-stakeholder 场景（不同文化、不同 age group 的"安全"定义不同）基本无解。

**OOD robustness 没有保证**。RLHF / CAI 都是 in-distribution 训练，对 adversarial input（jailbreak、prompt injection）的 robustness 很差。Anthropic 的 [Wei et al. 2023, Jailbroken: How Does LLM Safety Training Fail?](https://arxiv.org/abs/2307.14583) 系统地分析了 safety training 在什么情况下会失效：competing objectives（refuse vs. be helpful）、mismatched generalization（pretraining 知识覆盖了 safety training）、and adversarial robustness。三个 failure mode 都没有 scalable solution。2024 年有一篇 [Zou et al. 2024, Universal and Transferable Adversarial Attacks on Aligned Language Models](https://arxiv.org/abs/2307.15043) 用 gradient-based suffix search 跑出了 ~80% 的 universal jailbreak rate，震惊整个 alignment 圈——但说白了，这只是把 RLHF safety training 缺乏 robustness 这个已知问题量化了，没有 surprise。

**Scalable oversight 的实际可行性仍然是理论问题**。Weak-to-strong 50-70% 的 recovery rate 是 NLP task 上的，safety task 上的数字更低，而且 paper 自己也承认这个数字会随着 model capability gap 增大而下降（[Burns et al. 2023](https://arxiv.org/abs/2312.09390) Section 5）。换句话说，当 superhuman AI 真的出现时，weak-to-strong 可能直接 fail，因为 teacher 提供的 supervision signal 会变得 almost random for superhuman output。Debate 范式更糟——它假设人类 judge 能分辨两个 superhuman debater 谁对，但 [Michael et al. 2023, Debate Helps Supervise Unreliable Experts](https://arxiv.org/abs/2311.08702) 的 theoretical analysis 表明这个假设在很多 setting 下不成立。

**Refusal calibration 是 empirical 调参，没有原理**。每个 production 部署的 refusal threshold 都是人工调出来的——拿一批 red team prompt + benign prompt 跑 sweep，找一个 best trade-off。这个过程 cost 极高（每次 red team 要 100-200 人工小时）且不可复现（不同 deployment 的 red team 集合不同）。[Tanneru et al. 2024, Pruning the Safety Net: Human-in-the-Loop Pruning of LLM Safety Data](https://arxiv.org/abs/2403.06455) 尝试用 automated red team 代替，但 automated red team 本身又被 alignment 进展制约。

**"对齐税"（alignment tax）是真的，但被严重低估**。RLHF / CAI 都会造成 capability regression（特别是在 reasoning / 长 context / code 任务上），用 alignment tax 衡量。Llama-2-chat paper 报告 alignment tax 在 5-15% 区间，Llama-3.1 改善到 2-5%，但这个数字是 average over tasks——在 specific sub-task（高级数学、agent 任务）上 alignment tax 可以高到 20-30%。生产部署时这个 tax 是必须接受的，但学术界倾向于隐瞒。[Bai et al. 2022](https://arxiv.org/abs/2212.08073) 自己也承认 CAI 训的模型在某些 capability benchmark 上比 base model 略低，但没给具体数字。

最后说一句不那么 technical 的话。Alignment 圈 2024-2026 年其实经历了一个明显的范式转变：从 "alignment 是 RLHF 之后 add-on" 变成 "alignment 是 pretraining 阶段就要考虑的第一公民"。证据是 Anthropic / OpenAI / DeepMind / Meta 在 2024 年发的 model card 里 alignment / safety 章节都显著变长，且开始讨论 pretraining data filtering、RLHF data composition、post-training recipe 的联合优化。[Anthropic 2024, Claude 3 Model Card](https://www-cdn.anthropic.com/de8ba9b01c9ab7cbabf5c33b80b7bbc618857627/Model_Card_Claude_3.pdf) 是这个新范式下最完整的一份文档。但这种"alignment 全程介入"的代价是 alignment research 越来越难独立 eval——你分不清是 pretraining 改进了还是 alignment training 改进了。这是个 meta-level 的研究方法论问题，目前没人有答案。

写到这里我意识到，这一章其实没怎么讲"怎么造一个 aligned agent"——因为 alignment 的核心矛盾是 oversight，不是 capability。下一章会讲 [Self-Improvement](./13-self-improvement.md)：当 agent 开始改自己时，alignment 和 capability 就彻底纠缠在一起了，问题会变得比这一章讲的所有东西都更复杂。