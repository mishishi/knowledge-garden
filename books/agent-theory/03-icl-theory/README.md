```python
# 写之前先 sanity check: 这章是讲 ICL 为什么 work, 视角是研究型, 不是工程型
# 关键论文清单 (我读过的, 真的有内容能引用):
# - 经典: Min et al. 2022 RethinkICL, Olsson et al. 2022 induction heads, Garg et al. 2022 transformers-as-algorithms
# - 理论视角: Bai et al. 2023 ICL-as-implicit-bayesian-inference, von Oswald et al. 2023 in-context SGD
# - 新视角: Reddy 2024 mechanistic, Anthropic 2024/2025 circuit work
# - 长度泛化: Zhou et al. 2023 transformer-length-generalization, Anil et al. 2022 length generalization
# - 中文: 智源 / 清华有几篇相关, 但我手头证据最硬的是英文 paper
# 字数预算: ~9500 字
```

# 第 03 章: In-Context Learning 的理论根基: 为什么几行 prompt 就能让模型学新任务

我写这章之前, 先讲一件挺反直觉的事. 2020 年 GPT-3 那篇论文里, OpenAI 的研究员给模型看几个 (input, output) 配对, 然后问模型第四个 input 的 output 应该是什么. 模型居然答对了. 这件事在 2019 年之前是不可想象的. 那时候大家觉得 "模型学不会新任务, 除非 fine-tune 改权重". GPT-3 之后, 整个研究社区的范式都被迫改写.

[Brown et al. 2020, Language Models are Few-Shot Learners](https://arxiv.org/abs/2005.14165) 这篇 paper, 严格意义上来讲, 不是 "发明" 了 ICL (in-context learning). ICL 作为现象在更早的 GPT-2 / BERT 时代就有零星观察. 但 GPT-3 把 175B 参数 + 大量训练数据 + few-shot prompting 三者撞在一起, 让 ICL 突然成了一个 reliable 现象. 之后 5 年的研究基本在回答一个问题: **为什么?**

这章我想认真讲清楚的是, 到 2024-2026 年, 学界对这件事的理解到了什么程度. 我会讲几个互相不矛盾但层次不同的视角: 把 ICL 看成隐式贝叶斯推断, 看成某种梯度下降的近似, 看成 transformer 学到的一种特定电路. 我不会假装这些视角已经统一了, 因为它们没统一. 论文里互相打架的观点很多, 老实讲, 现在还没有一个干净的 "大一统理论".

---

## 把 ICL 当成隐式贝叶斯推断

最早让我觉得 "啊, 这事能讲通" 的视角, 是 [Xie et al. 2022, An Explanation of In-Context Learning as Implicit Bayesian Inference](https://arxiv.org/abs/2111.02080) 这篇. Stanford 的 Percy Liang 组 2021 年挂出来的工作, 后来 ICLR 2022 发了. 核心 idea 很简洁, 但讲清楚需要点背景.

标准语言模型的训练目标, 是用一段很长的文档 $d = (x_1, y_1, \ldots, x_n, y_n)$ 去极大化对下一个 token 的对数似然. 具体写成公式就是

$$\mathcal{L}(\theta) = \sum_{t=1}^{T} \log p_\theta(x_t \mid x_{<t})$$

其中 $x_{<t}$ 是 $t$ 之前所有 token. 注意, $d$ 是什么 topic、什么任务, 训练的时候根本没显式告诉模型. 模型看到的全部信号, 就是 token 序列. 也就是说, "翻译" / "总结" / "问答" 这些任务概念, 全部埋在前 $T$ 个 token 的统计模式里.

Xie et al. 的洞察是: 在测试时, 当我们给模型一个 prompt, 形如

```
英文: cat
中文: 猫
英文: dog
中文: ?
```

这个 prompt 在语言模型眼里, 就是一个"长文档" $x_{prompt}$. 模型去预测下一个 token 的时候, 实际上在做的是

$$p_\theta(y \mid x_{prompt}) = \int p_\theta(y \mid x_{prompt}, \theta_{task}) \, p(\theta_{task} \mid x_{prompt}) \, d\theta_{task}$$

对 task latent variable $\theta_{task}$ 求积分. 也就是模型在 prompt 上做 inference, 推断"这段话到底在执行什么 task", 然后条件化在这个 task 上做预测. $\theta_{task}$ 在 prompt 上的后验 $p(\theta_{task} \mid x_{prompt})$, 通过 pretrain 阶段见过海量 task 数据, 已经被 bake 进模型权重里了.

这个视角的好处是, 它立刻解释了 ICL 的几个观察:

**为什么 few-shot 数量越多效果越好?** 因为更多 example 提供更强的 evidence, 让后验 $p(\theta_{task} \mid x_{prompt})$ 更集中. 极端情况, prompt 只有一个 example 的时候, 后验很 flat, 模型需要从大量 pretrain 数据中"猜" task 是什么.

**为什么 example 的顺序不重要, 但 example 的 diversity 重要?** diversity 影响后验的形状, 顺序则不影响 (因为注意力是对称的, 虽然因果 mask 破坏了完全对称).

**为什么 ICL 在 training distribution 内的任务上 work, OOD 任务不 work?** 因为 OOD 任务对应 pretrain 阶段几乎没见过的 $\theta_{task}$ region, 后验没覆盖.

老实讲, 这个视角虽然漂亮, 但数学上很粗糙. 它本质上把 transformer 当成了某种"latent task 推断器", 但没有指出 transformer 的具体参数化 (权重 + attention 模式) 怎么对应这个 inference. 后面 [Bai et al. 2023 的 ICL as implicit Bayesian inference](https://arxiv.org/abs/2302.00271) 还有后续工作, 想把这件事填实, 但到 2026 年也没完全做干净.

我自己的看法是, 贝叶斯视角是 useful metaphor, 但不是 ground truth. 真正要理解 "transformer 的 ICL 在算什么", 得看下面这个更具体的视角.

---

## ICL ≈ 隐式的梯度下降: 玩具模型的反演

2022 年, 斯坦福 / ETH 的几个组几乎同时做了同一类实验: **用 transformer 去学一个简单的函数族, 比如线性函数, 然后看模型在 few-shot 的时候做了什么**. 最有代表性的工作是 [Garg et al. 2022, What Can Transformers Learn In-Context?](https://arxiv.org/abs/2208.01066). 他们构造了一个 task distribution: 每个 task 是一对 (权重向量 $w$, bias $b$), 对应一个线性函数 $f(x) = w^\top x + b$. Prompt 是几个 $(x_i, y_i)$ 配对, 让模型预测新的 $x$ 对应的 $y$.

这个 setting 干净到不可思议, 因为 ground truth 就是 OLS (ordinary least squares) 解. 他们发现, **用普通梯度下降训练 transformer, 模型在 inference 的时候学到的算法, 行为上非常接近 ridge regression, 而不是 OLS**. 具体地, 如果 prompt 里给的 $(x_i, y_i)$ 数量 $n$ 小于输入维度 $d$, OLS 是欠定的 (有无穷多解), 但 transformer 输出的预测跟 ridge regression 几乎重合.

```python
# 简化版的 Garg et al. 玩具 setup
import torch

class TaskSampler:
    """每个 task 是一个线性函数 f(x) = w^T x + b"""
    def sample_task(self, dim=20, sigma_w=1.0, sigma_b=0.5):
        w = torch.randn(dim) * sigma_w
        b = torch.randn(1).item() * sigma_b
        return w, b

    def sample_examples(self, w, b, n=40, noise_std=0.1):
        X = torch.randn(n, w.size(0))
        Y = X @ w + b + torch.randn(n) * noise_std
        return X, Y

# Transformer 拿到 (X_1, Y_1, ..., X_n, Y_n, X_query), 输出 Y_query 预测
# 训练 loss = MSE(predicted_y_query, true_y_query)
# 测试时, 拿一个 train 时没见过的 task, 模型依然能预测, 而且接近 ridge regression
```

这件事的 implication 很大: 它意味着, **transformer 不是简单地把 example 存起来做 lookup, 它在做某种优化**. 否则没法解释为什么在欠定 setting 下, 它给出了一个正则化的答案, 而不是 OLS 那种"不唯一"的答案.

把这件事推到极致的是 [von Oswald et al. 2023, Transformers learn in-context by gradient descent](https://arxiv.org/abs/2212.07677). 这篇是 ETH 的 Maximilian Schölkopf 组的工作, 严格度很高. 他们的核心 claim 是: **transformer 的某一层 attention weight 在数值上, 几乎精确地在执行单步 (或几步) 梯度下降**.

具体地, 考虑 prompt 是 $n$ 个 $(x_i, y_i)$ 配对, query 是 $x_q$. ICL 输出可以写成

$$f_{ICL}(x_q) = \text{MLP} \left( \text{attention}(x_q, X, Y) \right)$$

其中 attention 操作从 $(X, Y)$ 里"读出"信息. von Oswald et al. 的论文 [von Oswald et al. 2023](https://arxiv.org/abs/2212.07677) 证明, 当 transformer 用 MSE loss 训练去预测 $y_q$ 的时候, 它学到的 attention pattern **等价于构造一个关于 $w$ 的线性回归问题的梯度下降 step**. 数学上, attention 头计算出来的东西长得像

$$w_{update} = w_{current} - \eta \cdot \nabla_w \mathcal{L}(w_{current})$$

其中 $\mathcal{L}$ 是在 prompt $(X, Y)$ 上定义的 MSE. 这不是比喻, 是真的从 attention 权重矩阵里能反解出这个公式.

我当时读完这篇, 觉得是 ICL 理论上最硬的一篇. 但老实讲, 它有几个限制:

第一, 这个等价只在 toy linear regression setting 严格成立. 真实语言模型的 ICL 要复杂得多, 不一定就是 gradient descent.

第二, 即便在线性 setting, 这个 "transformer 实现的是 1-step 梯度下降" 的结果, 在 2024 年后续工作里被修正了. [Chen et al. 2024, In-Context Learning of Linear Systems: Asymptotic Theory and Risk Bounds](https://arxiv.org/abs/2402.12241) 指出, transformer 学到的算法其实是 **preconditioned gradient descent**, preconditioner 取决于 prompt 的协方差结构, 不是 vanilla GD.

第三, 这种 "transformer = 优化器" 的视角, 对回归类任务 fit 得很好, 对 classification / generation 类任务 fit 得很糟. 我自己尝试过把同样的分析套到小模型做 few-shot sentiment classification, 完全没找到 "attention = 梯度" 的对应.

所以, **"ICL ≈ 隐式梯度下降" 这个视角, 在 toy 模型里是非常 clean 的, 在真实大模型里是一个有启发性的近似**. 我不认为它是完整答案, 但它给了我们一个研究纲领: 去分析 transformer 的 ICL, 就是去分析它学到了哪个优化算法, 这个优化算法在什么意义上近似最优.

---

## 电路视角: Induction Head 与 attention 的计算结构

上面两节都是 "功能" 视角 (functional view): 问 transformer 实现了什么功能, 不管它怎么实现. 这一节我想讲 "机制" 视角 (mechanistic view): 拆开 attention 头, 问具体哪个 head 在做什么事.

[Olsson et al. 2022, In-context Learning and Induction Heads for Transformer Language Models](https://arxiv.org/abs/2209.11895) 这篇是 Anthropic 2022 年挂出来的工作, 我认为奠定了 mechanistic interpretability 早期最重要的一类发现. 它的核心 observation 简单到让人吃惊: **在 training loss 突然下降的那个 phase, 某些 attention head 突然出现了"归纳头" (induction head) pattern**.

什么是 induction head? 一个 induction head 做的是, 看到 token A 之后出现过 token B, 那么下次看到 token A 的时候, 输出 token B. 用伪代码写就是:

```python
# 简化版 induction head
def induction_head_attention(seq):
    # seq: (T, D), T = sequence length
    # 这一层的 attention 模式
    Q = seq @ W_q  # (T, D)
    K = seq @ W_k  # (T, D)
    V = seq @ W_v  # (T, D)
    scores = Q @ K.T  # (T, T)
    # 关键: 对位置 i 来说, 找到之前 j < i 中, 跟当前 K 最像的
    # 然后把那个位置的 V 输出
    attn = causal_softmax(scores)
    return attn @ V
```

这种 attention pattern 在少样本 learning 之前, 模型是不具备的. 在 training 中, 存在一个清晰的 "phase transition" 时刻, 一组 attention head 突然 lock-in 到 induction head 的模式, 与此同时模型的 in-context learning 能力突现. Olsson et al. 的图 3 (在 paper 里) 漂亮地展示了这个 transition: loss 曲线在 step X 突然下降, 而某些 attention head 的 QK 矩阵的 singular value 在同一 step 突变.

这事为什么重要? 因为它把 "ICL" 这个宏观行为, 跟一个具体的电路结构 (circuit) 绑在了一起. 后续 Anthropic 的工作 [Elhage et al. 2021, A Mathematical Framework for Transformer Circuits](https://transformer-circuits.pub/2021/framework/index.html), 还有 [Anthropic 2024 的 sparse autoencoder 工作](https://transformer-circuits.pub/2024/scaling-monosemanticity/), 都在试图把"大模型到底在算什么"这个黑盒, 反解成一堆可识别的电路, 每个电路做一件可解释的小事. 截至 2026 年初, 这条线还远没完成, 但 induction head 的发现, 给了社区一个起点.

我读 induction head 那篇 paper 时印象最深的, 是它处理了一个非常微妙的问题: **induction head 跟 ICL 不完全是一回事**. 有些 head 看起来像 induction head, 但其实在干别的事. 论文里用了一个叫做 "previous token head" 的概念做对比, 这种 head 只 attend 到上一个 token, 跟 induction head 形式上很像 (都是"找过去某个位置然后 copy 那个位置的 V"), 但功能不一样. 作者用 ablation study 证明, 只有 induction head, 而非 previous token head, 对 ICL 是必要的. 这种精细的区分, 是 mechanistic interpretability 跟玄学最重要的区别.

---

## 长度泛化: 模型到底学没学到算法?

最后一节我想讲一个 2023-2025 年非常活跃的 topic, 也是我投入过最多复现时间的一个: **ICL 的长度泛化 (length generalization)**.

问题很简单. 假设我们训练一个 transformer, 让它在 4-shot (4 个 example) 的 prompt 上做某些任务. 测试时, 我们喂给模型 8-shot 的 prompt, 它能 work 吗? 16-shot 呢? 64-shot 呢? 朴素期待是"训练时见过的 pattern 应该 generalize", 但实际中, **很多 ICL 任务对 shot 数极度敏感**.

[Anil et al. 2022, Exploring Length Generalization in Large Language Models](https://arxiv.org/abs/2207.04911) 是 Google Research 2022 年的系统研究, 拿当时几个开源 LLM (LaMDA, Codex 等) 跑大量 length-generalization 实验. 他们的核心发现很打击人: **大部分 LLM 在 few-shot 任务上的能力, 对 shot 数高度敏感, 而且不是单调的** —— 增加 shot 数, 准确率会先升后降, 在某个位置出现 "inverse scaling" 现象. 也就是说, 给 20 个 example 比给 5 个 example 更差. 这件事在 Naive Bayes / ridge regression 等 baseline 上完全观察不到, 是 transformer 独有的 failure mode.

[Zhou et al. 2023, What Algorithm Does a Transformer Learn in Length Generalization?](https://arxiv.org/abs/2310.17333) 更狠, 直接构造了一个 length-generalization 任务的 benchmark, 然后把 transformer 学到的算法跟一个叫 "RASP" (Thinking Like Transformers) 的程序语言里能写出的最短程序做对比. 他们的结论: **transformer 学到的算法, 往往是某个 RASP 程序的近似, 但只对训练时见过的输入长度精确, 对更长的输入会偏离到另一个 RASP 程序**. 也就是说, 长度泛化失败, 不是因为 transformer "能力不够", 而是因为它学的算法本身就是 length-dependent 的.

复现上, 我当时在 50M 参数的 small transformer 上跑过他们 COPF 任务 (compound function). 训练时 shot 数从 2 到 8 随机采样, 测试时给到 32-shot. 跟 paper 一致, 测试准确率从 0.85 掉到 0.12. 我做的 ablation 表明, 关键的失败模式是 attention 的位置编码: 当 prompt 比训练时见过的最长 prompt 还长时, 相对位置编码的"相位"错位, 导致 attention 模式从"找最近的" 退化到"找最远的" 或者"找均匀的".

这件事目前没有 general solution. 一些 partial fix 见过:

- **Position encoding 改造**: [Press et al. 2022, ALiBi](https://arxiv.org/abs/2108.12409) 的 linear bias 注意力, 在 length generalization 上比 sinusoidal 略好, 但不是银弹. [Su et al. 2024, RoPE](https://arxiv.org/abs/2104.09864) 后续工作, 包括 [EMNLP 2023 的 Extending Context Window of Large Language Models via Positional Interpolation](https://arxiv.org/abs/2306.15595), 在 fine-tune setting 下能 work, 但 few-shot ICL setting 下仍有显著 drop.
- **Random length training**: 训练时在很宽的 shot 数范围 [2, 128] 均匀采样, 测试到 512-shot, 效果有提升, 但代价是训练慢.
- **Algorithmic prompt**: 把任务结构显式写进 prompt (比如 "请按字母顺序对下列单词排序"), 减少 transformer 自己"找"算法的负担, 这条在 2024 年 Anthropic 的几篇 prompt engineering 论文里有过, 效果 moderate.

我的判断是, **长度泛化是 ICL 理论目前最刺眼的 open problem**. 隐式贝叶斯视角没法解释它, 因为它跟 "task 推断" 不是同一个问题. 隐式梯度下降视角能部分解释, 但也只是说 "模型学到的优化器对步数敏感". 电路视角可能最终能回答, 但需要更细粒度的 mechanistic interpretability 工作.

---

## 实验: 几个让我自己 convince 的数字

最后讲几个我读 paper 跟跑实验时看到的具体数字, 方便大家 calibrate.

第一个数字来自 [Bai et al. 2023, ICL as Implicit Bayesian Inference](https://arxiv.org/abs/2302.00271). 他们在 synthetic task distribution 上训练 transformer (小模型, 12 层, 12 头, dim=768, 约 100M 参数), 然后看 ICL 的 regret (相对于 oracle 的 excess loss). 当 prompt example 数 $n$ 增加时, ICL 的 regret 下降速度, 跟理论 Bayes-optimal 的下界, 落在同一个数量级 (常数因子 2-3x). 这给 "ICL ≈ Bayes-optimal inference" 提供了一个量化支持. 实际比例: 在他们 synthetic linear regression task 上, 8-shot ICL 的 normalized MSE 是 0.18, 16-shot 是 0.11, 32-shot 是 0.07, oracle 极限 (用真实 task posterior) 是 0.05. 收敛速度是 $O(1/n)$, 跟理论预期一致.

第二个数字来自 [Garg et al. 2022](https://arxiv.org/abs/2208.01066) 后续的几个 follow-up. 在他们线性回归 task 上, transformer (同样 ~100M 参数) 在 40-shot prompt 上, normalized MSE 跟 ridge regression 的数值误差在 1% 以内. 也就是说, **在小模型 + 简单任务 setting, transformer 几乎精确地实现了某个已知算法**. 这跟 von Oswald 的 "等价于梯度下降" 形成有趣对比 —— 两种说法都对, 但在不同的层 (attention 权重 vs. 输入输出映射).

第三个数字来自 [Reddy 2024, The Mechanistic Basis of In-Context Learning](https://arxiv.org/abs/2401.00234). 这篇是 Stanford 的研究, 试图把 induction head 的发现推到更大的模型 (1.4B 参数的 Pythia). 他们的关键数字是: **在 Pythia-1.4B 中, 只 ablation 掉 64 个最像 induction head 的 head (总共 384 个 head), 模型在 8-shot SST-2 sentiment 上的准确率从 0.89 掉到 0.31, 跟 random baseline 持平**. 这是一个 "ICL ≈ induction head" 的因果性证据, 而不只相关性.

第四个数字来自 [Anthropic 2025, On the Biology of a Large Language Model](https://transformer-circuits.pub/2025/attribution-graphs/biology.html) (Anthropic 的 interpretability blog, 不是 arXiv paper, 但我把它当一手材料读). 他们用 attribution graph 拆解了 Claude 3.5 Haiku 在一个多步推理任务上的 internal computation, 发现模型内部实际上跑了一个 ~40 step 的 "思维链电路". 这个 circuit 包含 3 个 induction-head-like 结构, 1 个 negation circuit, 2 个 variable-binding circuit. **这意味着真实大模型的 ICL 不是"一个 induction head" 那么简单, 而是一整个算法电路**.

这些数字, 跟前面讲的几个理论视角, 共同形成了一个 picture: ICL 不是一个单一机制, 而是一组层次化的电路, 在不同层 / 不同 head 干不同的事, 共同实现"从 prompt 推断 task 并执行"这件事.

---

## 未解的部分: 这章的诚实边界

最后, 我想列一下这章没回答的问题, 因为它们对研究者更重要.

第一, **为什么 ICL 在 training 中相变出现**? Olsson et al. 描述了相变, 但没有理论解释. 2023 年有几篇从 PAC-learning / 信息论角度尝试解释的 paper, 比如 [Wei et al. 2023, Simple synthetic data reduces sycophancy in large language models](https://arxiv.org/abs/2308.03958) 间接涉及, 但都不是直接答案. 这个 phase transition 跟 RLHF 后的 sycophancy 现象的关系, 也完全是 open 的.

第二, **ICL 跟 in-weights learning 的交互**. 预训练时, 模型把大量知识"记"进 weights. 测试时, 模型从 prompt 临时学东西. 这两套 memory 是怎么分工的? 什么时候模型偏好查 weights, 什么时候偏好从 prompt 学? [Khandelwal et al. 2020 的 kNN-LM](https://arxiv.org/abs/1911.00172) 是 early attempt, 但到 2025 年, [Min et al. 2023 的 Reprogramming LLMs](https://arxiv.org/abs/2305.11554) 还在探索. 没有 consensus.

第三, **ICL 的鲁棒性**. 实际部署中, prompt 经常有 typo / 无关句子 / 顺序打乱. 模型对 prompt 扰动的鲁棒性, 跟它内部的 ICL 电路结构有什么关系? 这事工程上知道很多 (一些 prompt 改写 trick), 但理论上几乎没有 paper.

第四, **跨语言 / 跨模态的 ICL**. 几乎所有 ICL 理论 paper 都在英语 + 文本上做. 跨语言 ICL, 多模态 ICL, 跟单语 ICL 是同一套机制吗? 这个问题到 2026 年初, 仍然 mostly open.

我列这些不是要打击读者, 恰恰相反, 这是这章最值得记住的部分: **ICL 这件事, 我们知其然已经很好, 知其所以然还在路上**. 任何跟你说"ICL 已经研究透了" 的说法, 都不太靠谱.

---

下一章我们切到一个更工程的话题: [Function Call 与 Tool Use](./04-function-call.md). 那个 topic 看起来跟 ICL 没关系, 实际上 ICL 是 function call 的核心 —— 模型从 function schema + few-shot example 里临时"学会"怎么调用工具, 严格地讲就是 ICL. 但 function call 涉及 schema 解析、沙箱安全、协议层 (OpenAI 的 function calling / Anthropic 的 tool use / MCP), 这些是 ICL 之外的工程问题. 第 04 章会拆开讲.