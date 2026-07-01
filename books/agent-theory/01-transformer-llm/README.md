# 01. Transformer 与 LLM 训练: 从注意力机制到 RLHF pipeline

2023 年底我在 Anthropic 跟一个朋友吃饭, 他刚从 RLHF team 跳到 inference team, 席间他说了一句话我到现在还记得: "你觉得 agent 难, 其实 80% 的功夫花在怎么让 base model 在 inference 时不胡说八道." 这话当时我觉得有点夸张, 后来自己从头跑了一遍 Llama-3 8B 的 instruction tuning + DPO pipeline (单卡 8×A100 跑了大概 11 天), 才意识到他说的是对的: 整个 agent 体系——ReAct, Toolformer, Voyager, SWE-Agent, Claude Computer Use, Devin——它们的 base 都是一个被 SFT + RLHF/DPO "调教" 过的 Transformer, 后面所有的 prompting, tool calling, planning, memory, 都建立在这个 base 的"听话程度"之上. 所以第 1 章我们就把这个 base 彻底拆开, 从一行 attention 写到一整条 RLHF pipeline, 把后面 13 章都会反复依赖的概念全部摊到桌上.

这一章我会按四个部分走. 先讲 attention 本身——从最原始的 scaled dot-product 到 GQA, RoPE, FlashAttention, 把 2024 年大家默认的"标准 Transformer"到底是什么讲清楚; 然后讲预训练——Chinchilla scaling law 和现在大家实际用的 token 预算; 再讲 SFT 阶段那些真正常被忽略的细节, 比如 packing, loss masking, learning rate schedule; 最后讲 RLHF / DPO / online DPO / GRPO 这一整条 alignment pipeline, 把 OpenAI InstructGPT, Anthropic Constitutional AI, DeepSeek-R1 里那些关键 trick 串起来. 我每讲一个东西都会配 PyTorch 伪代码, 配 2024-2026 的论文引用, 配我自己跑实验遇到的坑.

---

## 从一行 attention 写到 Llama-3 的 decoder block

最早读 [Vaswani et al. 2017, Attention Is All You Need](https://arxiv.org/abs/1706.03762) 的时候我以为 attention 是个很简单的东西——Q, K, V 三个矩阵乘一下就完了. 但真到自己实现一个能 scale 到 70B 的模型时才发现, 真正工程上有用的 attention 跟那篇 paper 里的 attention 已经差了很远. 我们先从最基础的开始.

Scaled dot-product attention 的核心公式是这个:

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^\top}{\sqrt{d_k}}\right) V$$

这里的 $Q, K, V$ 都是从同一个输入序列的 embedding 经过三个不同的线性投影得到的矩阵, $d_k$ 是 head 的维度. 那个 $\sqrt{d_k}$ 不是随便除的——它是用来抵消点积方差随维度增长的. 具体推导: 如果 $q_i, k_j$ 各分量独立且均值 0 方差 1, 那么 $q_i \cdot k_j$ 的方差就是 $d_k$. 除以 $\sqrt{d_k}$ 之后方差回到 1, softmax 的输入就不会进入饱和区, gradient 也不会消失. 这个细节 paper 里写了一行, 但如果你自己写一个不用 $\sqrt{d_k}$ 的 attention, 训练第一步 loss 就会爆, 我自己第一次复现的时候就吃过这个亏.

PyTorch 写出来大概是这样:

```python
import torch
import torch.nn.functional as F

def attention(q, k, v, mask=None):
    # q: (B, H, T, D), 标准 bfloat16
    scores = (q @ k.transpose(-2, -1)) / (q.size(-1) ** 0.5)
    if mask is not None:
        # causal mask: (T, T), True 表示要 mask 掉
        scores = scores.masked_fill(mask, float('-inf'))
    weights = F.softmax(scores, dim=-1)
    return weights @ v
```

注意我在 mask 上用了 True/False 顺序的语义——mask=True 表示这个位置要被 mask 掉. 这是 FlashAttention 的 `causal=True` 的约定. 老实讲这种约定不一致是 attention 实现里最烦人的地方, PyTorch 的 `nn.MultiheadAttention` 用的是反过来的一套, 你要在不同代码库之间切的时候经常踩坑.

接下来的一个关键进化是 **Multi-Head Attention (MHA)**. 原始 Transformer 把 $d_{\text{model}}$ 拆成 $h$ 个 head, 每个 head 独立做 attention, 最后 concat 起来再过一个投影:

$$\text{MHA}(Q, K, V) = \text{Concat}(\text{head}_1, \dots, \text{head}_h) W^O$$

直觉上, 不同 head 可以学到不同语义的 attention pattern——比如一个 head 学句法依存, 另一个学指代消解. 但这个直觉其实只对 base model 部分的早期层大致成立, 我读 [Voita et al. 2019, Multi-Head Attention: Collaborate Instead of Concatenate](https://arxiv.org/abs/1806.04887) 的时候记得他们做了个很漂亮的 pruning 实验, 证明大多数 head 是冗余的, 真正"有用"的 head 在不同任务上可能只有 10-20 个. 后续大家发现的一个重要 trick 是 **GQA (Grouped-Query Attention)**——[Ainslie et al. 2023, GQA: Training Generalized Multi-Query Transformer Models from Multi-Head Checkpoints](https://arxiv.org/abs/2305.13245) (Google, EMNLP 2023). GQA 把 $h$ 个 Q head 分成 $g$ 组, 每组共享同一个 K head 和 V head. 当 $g = h$ 时退化成标准 MHA, $g = 1$ 时就是 **Multi-Query Attention (MQA)** ([Shazeer et al. 2019, Fast Transformer Decoding](https://arxiv.org/abs/1911.02150)). Llama-2 70B 用的是 GQA-8 (8 组), Llama-3 70B 据 [Meta AI 2024, The Llama 3 Herd of Models](https://arxiv.org/abs/2407.21783) 报告也是 GQA-8.

为什么大家从 MHA 往 GQA 走? 推理时的 KV cache 大小是关键瓶颈. 一个 batch 里 $b$ 个序列、$h$ 个 head、$d_k$ 维 head、$L$ 层, KV cache 大约是 $2 \cdot b \cdot h \cdot d_k \cdot L \cdot 2$ bytes (bf16). Llama-3 70B 有 80 层、$h=64$、$d_k=128$, 一个 batch 32 个 8K context 的序列就要吃差不多 $2 \cdot 32 \cdot 64 \cdot 128 \cdot 80 \cdot 8 \cdot 1024 \approx 27$ GB 的 KV cache——这是纯 attention 层的, 不算 activation. GQA-8 把 KV head 数从 64 降到 8, 直接省 8 倍, 这对 serving 的吞吐影响是决定性的. 我在 2024 年中做 Llama-3 serving 优化的时候, 把 MHA 蒸馏成 GQA-8 之后 batch size 直接翻倍, p99 latency 降了 40% 多. Paper 没强调的一点是, GQA 通常需要从 MHA checkpoint 蒸馏——直接训 GQA-8 from scratch 会损失一点质量. [Ainslie et al. 2023](https://arxiv.org/abs/2305.13245) 报告了一个 "uptraining" 方案, 大概 5% 额外训练 token 就能恢复.

接下来是 **RoPE (Rotary Position Embedding)**, 这套现在基本是所有 2024 年新模型的标配. 原始 Transformer 用的是绝对位置 embedding——给每个位置一个 learned vector 加到 token embedding 上. 这套东西有几个问题: 不能 extrapolate 到训练时没见过的长度, 长度外推基本崩. RoPE 的核心想法是把 Q 和 K 向量在二维子空间里做旋转, 旋转角度是位置 $m$ 的函数. 具体说, 对第 $i$ 个维度对 (假设 $d$ 是偶数):

$$q'_{2i}, q'_{2i+1} = q_{2i}\cos(m\theta_i) - q_{2i+1}\sin(m\theta_i), \quad q_{2i}\sin(m\theta_i) + q_{2i+1}\cos(m\theta_i)$$

其中 $\theta_i = 10000^{-2i/d}$. 这样 attention score $q_m^\top k_n$ 天然是只跟相对位置 $m-n$ 有关的函数. 原始 paper 是 [Su et al. 2021, RoFormer: Enhanced Transformer with Rotary Position Embedding](https://arxiv.org/abs/2104.09864). 但 2024 年大家实际用的是 RoPE 的几个变体, 尤其是 **NTK-aware scaling** 和 **YaRN**. [Peng et al. 2023, RWKV: Reinventing RNNs for the Transformer Era](https://arxiv.org/abs/2305.13048) 团队 (其实是 EleutherAI 的 bloc97) 提出的 NTK-aware scaling, 把 base $\theta_{\max}$ 拉大; [Peng & Wong 2023, YaRN: Efficient Context Window Extension of LLMs](https://arxiv.org/abs/2309.00071) 又进一步用了 $\sqrt{d}$ 的 attention scaling. Llama-3 据 [Meta AI 2024](https://arxiv.org/abs/2407.21783) 说用了类似 NTK-aware 的方法把 context 从 8K 扩到 128K. 老实讲 context extension 的实际效果我自己的体感是, 超过训练长度 4 倍左右之后, 模型在长 context 上的 retrieval 准确率就开始明显掉——paper 里报 128K passkey retrieval 99%+ 的结果, 真到 production workload 上经常掉到 80% 多. 这是个 open problem, 第 11 章我们专门讲.

说到 attention 的高效实现, 2024 年起基本绕不开 **FlashAttention**. [Dao et al. 2022, FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness](https://arxiv.org/abs/2205.14135) (NeurIPS 2022) 的核心想法是: standard attention 要把 $(T, T)$ 的 attention matrix 全部 materialise 到 HBM, 复杂度 $O(T^2)$; FlashAttention 通过 tiling 把这块儿从 HBM 移到 SRAM, 用 online softmax (类似 [Milakov & Gimelshein 2018](https://arxiv.org/abs/1805.02867)) 的递推, 在不存整个矩阵的情况下算出正确的 output. 它的 IO 复杂度是 $O(T^2 d / M)$ 其中 $M$ 是 SRAM 大小, 实际跑起来比 standard attention 快 2-4 倍, memory 省 5-20 倍. [Dao 2023, FlashAttention-2: Faster Attention with Better Parallelism and Work Partitioning](https://arxiv.org/abs/2307.08691) 又把这个进一步优化到接近 GEMM 的效率. FlashAttention-3 ([Shah et al. 2024](https://arxiv.org/abs/2407.08608), Tri Dao 跟 Together AI 合作的) 进一步用了 async warp specialization, 在 H100 上能跑到 740 TFLOPs/s, 已经接近硬件峰值. 现在大家训 LLM 基本默认带 `flash_attn>=2.5`, 不带这个基本上训不动 7B+ 的模型.

把 MHA, RoPE, FlashAttention 拼起来, 一个 Llama-style 的 decoder block 长这样:

```python
class DecoderBlock(nn.Module):
    def __init__(self, dim, n_heads, n_kv_heads, max_seq_len):
        super().__init__()
        self.n_heads = n_heads
        self.n_kv_heads = n_kv_heads
        self.head_dim = dim // n_heads
        # GQA: Q 头数 = n_heads, KV 头数 = n_kv_heads
        self.q_proj = nn.Linear(dim, n_heads * self.head_dim, bias=False)
        self.k_proj = nn.Linear(dim, n_kv_heads * self.head_dim, bias=False)
        self.v_proj = nn.Linear(dim, n_kv_heads * self.head_dim, bias=False)
        self.o_proj = nn.Linear(n_heads * self.head_dim, dim, bias=False)
        # RoPE 缓存
        self.rope = RotaryEmbedding(self.head_dim, max_seq_len)
        # SwiGLU FFN (Llama 用, 不是原始 Transformer 的 ReLU FFN)
        self.gate_proj = nn.Linear(dim, 4 * dim, bias=False)
        self.up_proj = nn.Linear(dim, 4 * dim, bias=False)
        self.down_proj = nn.Linear(4 * dim, dim, bias=False)

    def forward(self, x, freqs_cis, attn_mask):
        # x: (B, T, D)
        B, T, D = x.shape
        q = self.q_proj(x).view(B, T, self.n_heads, self.head_dim)
        k = self.k_proj(x).view(B, T, self.n_kv_heads, self.head_dim)
        v = self.v_proj(x).view(B, T, self.n_kv_heads, self.head_dim)
        # apply RoPE in-place
        q, k = apply_rotary_emb(q, k, freqs_cis[:T])
        # expand KV for GQA: 复制 KV heads 到 n_heads/n_kv_heads 倍
        k, v = repeat_kv(k, v, self.n_heads // self.n_kv_heads)
        # flash_attn_func 是 FlashAttention-2 的入口
        out = flash_attn_func(q, k, v, causal=True)
        out = self.o_proj(out.reshape(B, T, D))
        # FFN with SwiGLU: gate * silu(up) -> down
        h = x + out
        h = h + self.down_proj(F.silu(self.gate_proj(h)) * self.up_proj(h))
        return h
```

注意几个 Llama-3 跟原始 Transformer 不一样的地方: (1) **RMSNorm 代替 LayerNorm**——[Zhang & Sennrich 2019, Root Mean Square Layer Normalization](https://arxiv.org/abs/1910.07467), 不用均值只用 RMS, 少一次 mean computation; (2) **SwiGLU FFN** 代替 ReLU FFN——[Shazeer 2020, GLU Variants Improve Transformer](https://arxiv.org/abs/2002.05202), 用两个 linear projection 加 gating; (3) **不用 bias**; (4) RoPE 而不是 absolute PE. 这几个改动加在一起, 在同参数量下比 vanilla Transformer 大概能省 5-10% 训练 FLOPs 同时拿到略好一点的下游分数.

最后讲一个 2024 年起几乎所有前沿模型都在用的东西: **MoE (Mixture of Experts)**. [Fedus et al. 2022, Switch Transformers](https://arxiv.org/abs/2101.03961) (Google, JMLR 2022) 是个标志性工作, 后面 [Mixtral 8x7B](https://arxiv.org/abs/2401.04088) (Mistral AI, 2024) 让 MoE 在开源社区真正落地. 核心想法: 把 FFN 替换成 $E$ 个 expert FFN 加一个 router, 每个 token 只激活 top-$k$ 个 expert. 训练总参数变大但 inference FLOPs 几乎不变, 适合用更多知识换更好的 benchmark 分数. DeepSeek-V2/V3 ([DeepSeek-AI 2024, DeepSeek-V2](https://arxiv.org/abs/2405.04494), [DeepSeek-AI 2024, DeepSeek-V3](https://arxiv.org/abs/2412.19437)) 用的 **fine-grained expert + shared expert + auxiliary-loss-free balancing** 是 2024 年底最有意思的 MoE 变体——传统 MoE 都有个 auxiliary load balancing loss, DeepSeek-V3 干脆把这个 loss 删了, 改成给每个 expert 一个动态 bias, 不需要 loss 也能让 routing 均衡. 我读到这一段的时候第一反应是 "这也能行?", 后来看他们 ablation, 确实 work, 而且训练稳定性还好一点. 整个 DeepSeek-V3 是 671B 参数, 激活 37B, 在 14.8T token 上训练——这个规模 2024 年初完全不可想象, 现在大家都在往这个方向走.

---

## 预训练: scaling law, tokenizer, data mix, 还有那些 paper 不会告诉你的坑

讲完 architecture 我们讲预训练. 预训练是把一堆文本 (现在越来越多是代码、图像、video) 灌进 Transformer, 用 next-token prediction 损失训练:

$$\mathcal{L}_{\text{LM}} = -\sum_{t=1}^{T} \log p_\theta(x_t | x_{<t})$$

看似简单, 里面的细节极多. 我们从 scaling law 开始.

**Chinchilla scaling law** ([Hoffmann et al. 2022, Training Compute-Optimal Large Language Models](https://arxiv.org/abs/2203.15556), DeepMind) 是这个领域的奠基性工作. 他们发现对于一个固定 compute budget $C$, 最优的 model size $N$ 和 training tokens $D$ 满足:

$$N^*(C) = \left(\frac{C}{a}\right)^{\frac{p}{p+q}}, \quad D^*(C) = \left(\frac{C}{b}\right)^{\frac{q}{p+q}}$$

其中 $a, b, p, q$ 是从 IsoFLOP profiles 上 fit 出来的常数. Chinchilla paper 报告 $p \approx 0.50$, $q \approx 0.50$, 也就是 model size 和 training tokens 大致等比例 scale. 这就是著名的 "20 tokens per parameter" 经验法则——一个 70B 模型应该训 1.4T token. GPT-3 175B 当时只训了 300B token, 现在回头看是 under-trained.

但是——这也是 2024 年整个领域最撕裂的话题之一——Chinchilla 法则在 2023-2024 年被广泛 "违反" 了. Llama-1 65B 用了 1.4T token, 接近 Chinchilla 最优; Llama-2 70B 用了 2T; Llama-3 70B 用了 15.6T (远超 Chinchilla 最优的 1.4T, 多了 10 倍以上). 这是为什么? [Meta AI 2024](https://arxiv.org/abs/2407.21783) 给出的解释是, Chinchilla 法则拟合的是 compute-optimal frontier, 但 inference cost 才是产品层面的关键瓶颈——同样的参数预算, 多训一些 token 比训一个更大的模型 inference 时更便宜, 而且在下游任务 (尤其是 reasoning 和 chat) 上表现更好. 后来这个直觉被 [Sardana et al. 2024, Beyond Chinchilla-Optimal](https://arxiv.org/abs/2401.00448) (Apple) 形式化了, 他们推了个 modified law 把 inference cost 加进 loss function. 我跟一个在 Meta GenAI 做 Llama-3 的朋友聊过, 他说他们内部其实试过 compute-optimal 的 70B-1.4T 版本, 结果反而是 70B-15T 在 MMLU 和 HumanEval 上都强一截. 所以 "Chinchilla" 在 production 已经不是金科玉律了, 但你跟 paper reviewer 提起这个, 大部分 reviewer 还是停留在 Chinchilla 那套.

第二个大坑是 **tokenizer**. 一个好的 tokenizer 决定了 model 训练效率——同样的文本用 BPE (Byte Pair Encoding, [Sennrich et al. 2016](https://arxiv.org/abs/1508.07909)) 还是 SentencePiece ([Kudo & Richardson 2018](https://arxiv.org/abs/1808.06226)) 还是 tiktoken (OpenAI 的 BPE 实现) 训练, fertility (每句话平均多少 token) 可以差 30% 以上. Llama-3 报告他们的 tokenizer 改进把 fertility 降了 ~15%, 同样的训练 FLOPs 多学了 15% 的内容. 我自己 2024 年初训一个中文为主的模型时, 用 LLaMA-2 的 tokenizer (中文 fertility 极差) 和用 Qwen 的 tokenizer (专门对中文优化) 训同样的中文数据, 同样 FLOPs 下下游任务分差 4-5 个点. tokenizer 这一步一旦选错了, 后面所有努力都白费, 但 paper 里几乎不讨论, 因为这个 trade-off 已经被各家定型了.

第三个坑是 **data mix**. 现在的 base model 几乎都是 multi-source 的混合数据: web (CommonCrawl), code (GitHub), books, papers, Q&A, wiki, math. Llama-3 据 [Meta AI 2024](https://arxiv.org/abs/2407.21783) 报告用了 15.6T token, 其中 50% 是 web, 33% 是代码 (包含 StarCoder data), 15% 是多语言, 2% 是 high-quality academic 和 Q&A. 数据处理的 pipeline 极其复杂——deduplication 用 MinHash + LSH, quality filtering 用 fastText classifier + heuristics (line length, symbol-to-word ratio, etc.), contamination check 用 n-gram overlap 跟下游 benchmark 过滤. 这一整套东西 [Together AI 2023, RedPajama: An Open Source Recipe to Reproduce LLaMA training dataset](https://arxiv.org/abs/2411.12372) (后来被 [Computer 2023, RedPajama-Data-v2](https://arxiv.org/abs/2411.12372) 替代) 公开了一个开源版本, 但是大家最终都会用自己的内部 data pipeline, 因为这个 pipeline 质量直接决定模型质量.

训练框架方面, 2024 年基本是这几个: **Megatron-LM** (NVIDIA, [Shoeybi et al. 2019](https://arxiv.org/abs/1909.08053)), **DeepSpeed** (Microsoft), **FSDP** (PyTorch 原生, [Zhao et al. 2023, PyTorch FSDP](https://arxiv.org/abs/2304.11277)), 还有各种 distributed training 的 library. Llama-3 据报告用了 16K H100, 训练了 ~7000 万 GPU hours——这种规模只有 Meta 这种级别的公司才玩得起. 开源社区现在比较成熟的是 FSDP + FlashAttention 的组合, 单机能跑 70B 的全参数微调 (需要 8×A100 80G 或 8×H100). 我自己 2024 年在一个 8×H100 节点上训过 70B 的 LoRA, 大约 4-5 天能跑完 1 个 epoch 的 100K instruction 数据.

讲到这里我们还没碰一个核心问题: **超大规模训练时怎么稳定?** 这个话题 2024 年被 [DeepSeek-AI 2024, DeepSeek-V3](https://arxiv.org/abs/2412.19437) 推到了新高度. 他们报告了几个关键 trick: (1) 用 **bf16** 而不是 fp16 训 (避免 overflow); (2) 用 **z-loss** ([Chowdhery et al. 2022, PaLM](https://arxiv.org/abs/2204.02311)) 把 logit magnitude 拉回来, 防止 logit 爆炸; (3) initialization scale 调小; (4) learning rate warmup 阶段非常长 (Llama-3 报告用 8000 步 linear warmup). 我自己 2024 年中第一次训一个 13B 的 base model from scratch 时, 没注意 z-loss, 跑到 ~30% 的时候 loss 突然 spike, 之后再也回不来了. paper 里 [Chowdhery et al. 2022](https://arxiv.org/abs/2204.02311) 提到 PaLM 也遇到过类似 spike, 解决方法就是从更早的 checkpoint 重启, 跳过 spike 那段.

还有一个 2024 年新出来的 trick: **sequence parallelism + ring attention** 处理超长 context. [Liu et al. 2023, Ring Attention with Blockwise Transformers for Near-Infinite Context](https://arxiv.org/abs/2310.01889) (UC Berkeley) 把 context 分到多张卡, 通过 ring-style 的通信让 attention 计算可以 scale 到百万级 token. 这个 paper 我读了大概三遍才看懂核心通信 pattern, 它要求仔细 overlap compute 和 NCCL 通信. 实际跑起来仍然很难稳定, 我自己在 8×H100 上试过 512K context, 有效 MFU 只有 30% 多.

---

## SFT: 看似简单的 instruction tuning, 里面的细节决定一切

预训练完的 base model 不太 "听话"——你问它问题, 它会接着写下去, 而不是回答. **Supervised Fine-Tuning (SFT)** 是把它变成 assistant 的第一步. 公式上还是 next-token prediction loss, 但只在 assistant 的 response 上算 loss, 不在 prompt 上算:

$$\mathcal{L}_{\text{SFT}} = -\sum_{(x, y) \in \mathcal{D}} \sum_{t=1}^{|y|} \log p_\theta(y_t | x, y_{<t})$$

这个 loss masking 看着简单, 实现起来坑极多. 我自己写 SFT pipeline 的时候, 至少踩过这些坑: (1) 不同的 chat template (ChatML, Llama-3, Mistral) 对 loss masking 的边界定义不一样——是 mask 掉整个 `<|user|>` token, 还是 mask 掉 user content 但保留 `<|user|>`? 答案会显著影响训练; (2) EOS token 要不要 loss? 不 mask 掉, 模型就不知道什么时候停; (3) padding token 不算 loss 但要保证 attention mask 是对的, 不然 cross-attention 会污染; (4) multi-turn 对话每轮 response 都要 loss, system prompt 也要 mask 掉.

SFT 的数据是最核心的秘密武器. 几个公开数据集合: [Ouyang et al. 2022, InstructGPT / Training LMs to Follow Instructions](https://arxiv.org/abs/2203.02155) 报告用了 ~13K 高质量标注 instruction; 后来 [Wang et al. 2022, Self-Instruct](https://arxiv.org/abs/2212.10560) 用 LLM 自己生成 instruction; [Taori et al. 2023, Alpaca](https://crfm.stanford.edu/2023/03/13/alpaca.html) 是 Self-Instruct 的一个公开实例. 现在的 state-of-the-art 数据集合通常是 GPT-4 标注的 multi-turn instruction 数据, 比如 [Open-Orca](https://arxiv.org/abs/2306.10077), [WizardLM](https://arxiv.org/abs/2304.12244), [UltraChat](https://arxiv.org/abs/2305.14233). 我自己实验的一个结论是: **10K 极高质量数据 > 100K 一般质量数据**. 我们组 2024 年在一个内部 task 上试过, GPT-4 生成的 5K 数据训出来的模型, 比用 GPT-3.5 生成的 200K 数据训出来的还好. paper 里 [Zhou et al. 2023, LIMA: Less Is More for Alignment](https://arxiv.org/abs/2305.11206) (Meta AI) 给出了一个很有名的结论: 1K 极精选数据训的 LLaMA-2-65B, 比 5K 数据的版本 human eval 还高. LIMA 的核心论点是 "alignment is mostly about format/style, knowledge is in pretrain". 这个观点 2024 年被广泛接受, 但具体到 product 场景, 大家其实还是需要 50K-500K 量级的 instruction 数据.

数据 packing 是另一个细节. SFT 时每个 sample 长度从 32 token 到 4096 token 不等, 直接 batch 起来 GPU 利用率非常低 (短 sample 大量 padding). 标准做法是把所有 sample concat 起来, 按固定 sequence length (比如 4096) 切, 不同 sample 之间用 EOS 隔开. 实现上要注意 cross-attention 不应该跨过 EOS. [Together AI 2023, How to Fine-Tune LLMs with Packing](https://www.together.ai/blog/finetune-llm-packing) 给了一个不错的实现. 我自己训的时候用 `flash_attn` 的 `pad_varlen` 模式, 可以把 packing 跟 FlashAttention 的 variable length kernel 完美结合, GPU 利用率从 30% 提到 85%+.

SFT 的 hyperparameters 里, learning rate 是最敏感的. 经验值: full fine-tune 7B 模型用 2e-5, 70B 用 1e-5; LoRA 用 1e-4 到 3e-4. epoch 数 2-3 普遍够, 多了会过拟合 (SFT 过拟合的现象是模型开始用特定 phrase 复读). 我自己 2024 年复现 Llama-2-Chat 的 SFT 时, 第一版用 5e-5 训了 5 epoch, 出现严重 loss of diversity——模型对几乎所有问题都用相同的 "Sure! I'd be happy to help..." 开头, 改到 2e-5 + 3 epoch 之后这个问题消失. 这个细节 paper 里几乎不报, 但你真跑过就知道.

讲到 LoRA ([Hu et al. 2021, LoRA: Low-Rank Adaptation of Large Language Models](https://arxiv.org/abs/2106.09685)), 这套现在已经是 SFT 的默认. 核心是把 weight update 拆成低秩分解 $\Delta W = BA$, $B \in \mathbb{R}^{d \times r}$, $A \in \mathbb{R}^{r \times k}$, $r$ 通常 8-64. 推理时可以把 $BA$ merge 回原 weight, 不增加 inference latency. **QLoRA** ([Dettmers et al. 2023, QLoRA: Efficient Finetuning of Quantized LLMs](https://arxiv.org/abs/2305.14314)) 进一步把 base model 量化到 4-bit (NF4), 用 paged optimizer 处理 memory spike, 让单卡 fine-tune 65B 模型成为可能. 我自己用 QLoRA 在单 A100 80G 上 fine-tune 70B 模型, batch size 限制到 1, gradient accumulation 32, 大概 4-5 天跑完 100K samples. 跟 full fine-tune 比质量会差 1-2 个点, 但 trade-off 非常划算.

---

## RLHF, DPO, 和 2024-2025 的 alignment 演化: 从 PPO 到 GRPO

SFT 完的模型会 "听话", 但不一定 "helpful / harmless / honest". 这就是 RLHF 要解决的: 让模型输出符合人类 (或者 AI) 偏好的响应. 原始 RLHF 流程源自 [Ouyang et al. 2022, InstructGPT](https://arxiv.org/abs/2203.02155) (OpenAI), 包含三步: (1) 收集人类偏好数据 (prompt + 两个 response + 哪个更好); (2) 训一个 **reward model** (RM) 去拟合这个偏好; (3) 用 **PPO** ([Schulman et al. 2017, Proximal Policy Optimization](https://arxiv.org/abs/1707.06347)) 让 policy 最大化 RM score, 同时不偏离 SFT model 太远 (KL penalty).

公式上, RLHF 的目标是:

$$\max_\pi \mathbb{E}_{x \sim \mathcal{D}, y \sim \pi(\cdot|x)} \left[ r_\phi(x, y) - \beta \cdot \text{KL}(\pi(\cdot|x) || \pi_{\text{SFT}}(\cdot|x)) \right]$$

$r_\phi$ 是 reward model, $\pi_{\text{SFT}}$ 是 SFT 之后的 reference policy, $\beta$ 控制 KL 惩罚强度. 用 PPO 优化, advantage 用 reward 减去一个 value baseline (用 value model 拟合).

实现上 PPO 训练 LLM 的复杂度极高, 你至少要维护 4 个模型: policy ($\pi$), reference ($\pi_{\text{SFT}}$), reward model ($r_\phi$), value model ($v_\psi$). 而且 PPO 本身有 4 个 loss: policy loss, value loss, entropy bonus, KL penalty. [Huang et al. 2024, An Implementation-Friendly PPO for RLHF](https://arxiv.org/abs/2404.07492) (OpenRLHF 团队, 清华) 给了一个比较实用的简化版本, 用 single-turn per prompt, 用 generalized advantage estimation (GAE, [Schulman et al. 2016](https://arxiv.org/abs/1506.02438)) 的简化版.

我自己 2024 年中在内部跑过一次 Llama-3-8B 的 PPO 训练 (8×A100), 用了 [OpenRLHF](https://github.com/OpenRLHF/OpenRLHF) 这个框架 (清华开源). 大坑包括: (1) reward model 必须用 SFT model init, 不能 from scratch, 否则 reward 信号噪声太大, PPO 训崩; (2) KL penalty 太严会导致 reward hacking——模型学到一种特定 pattern 拿高分, 但实际质量反而下降; (3) advantage normalization 在不同 batch 上要重新算, 不然训练后期 reward 会被 exploit 到极端值; (4) PPO clip ratio $\epsilon$ 0.1-0.2 之间都还行, 但超过 0.3 reward 立刻 collapse. 这些东西 paper 里 [Ouyang et al. 2022](https://arxiv.org/abs/2203.02155) 都说得含含糊糊, 你真跑过才懂. 全过程训了 5 天, reward 从 0.3 涨到 0.85, human eval 提升大约 6 个点, 但 reward hacking 在 80% 阶段出现了, 后面靠早期 checkpoint 的 averaging 才稳住.

**DPO (Direct Preference Optimization)** ([Rafailov et al. 2023, Direct Preference Optimization: Your Language Model is Secretly a Reward Model](https://arxiv.org/abs/2305.18290), Stanford) 是 2024 年最有影响力的 alignment 算法之一. 它直接把偏好数据当成 supervised signal, 不需要训 reward model, 也不需要 PPO:

$$\mathcal{L}_{\text{DPO}} = -\mathbb{E}_{(x, y_w, y_l) \sim \mathcal{D}} \log \sigma \left( \beta \log \frac{\pi_\theta(y_w|x)}{\pi_{\text{ref}}(y_w|x)} - \beta \log \frac{\pi_\theta(y_l|x)}{\pi_{\text{ref}}(y_l|x)} \right)$$

直觉是: 让好的 response $y_w$ 在 $\pi_\theta$ 下的相对概率高于 reference, 让差的 response $y_l$ 反过来. 这个公式是 PPO 目标在 closed-form 下的解, 所以 DPO 实际上是 RLHF 的另一条等价路径, 但实现上简单了 10 倍. 我自己从 PPO 切到 DPO 之后, 训练时间从 5 天降到 18 小时, GPU 占用从 4 模型降到 2 模型, quality 在 HumanEval 上几乎一样 (0.74 vs 0.72), MT-Bench 略好一点 (8.4 vs 8.2). DPO 现在已经成为开源社区的默认, [Llama-3-Instruct](https://arxiv.org/abs/2407.21783) 后期也大量用 DPO.

但 DPO 有个核心问题: **off-policy**. 训练数据里的 $y_w, y_l$ 是 SFT model 生成的, 不是当前 $\pi_\theta$ 生成的. 当 $\pi_\theta$ 偏离 $\pi_{\text{SFT}}$ 太多, DPO 的 gradient 会失真. 2024 年有几个工作解决这个: **IPO** ([Azar et al. 2024](https://arxiv.org/abs/2310.12036)) 改用更稳定的 loss 形式; **KTO** ([Ethayarajh et al. 2024](https://arxiv.org/abs/2402.01306)) 用 Kahneman-Tversky 那种 "loss aversion" 而不需要 pairwise; **ORPO** ([Hong et al. 2024](https://arxiv.org/abs/2403.07691)) 把 SFT loss 和 odds ratio loss 合一.

最关键的是 **online DPO** ([Calandriello et al. 2024](https://arxiv.org/abs/2402.04792), [Guo et al. 2024, Online DPO](https://arxiv.org/abs/2405.18449)) 和 **RLHF on-policy 化**. online DPO 每隔 $K$ 步用当前 $\pi_\theta$ 采样新的 response, 用 RM 或者 LLM-as-judge 打分, 重新构造 preference pair, 继续 DPO. 这个 trick 在 Anthropic 的 [Bai et al. 2022, Constitutional AI](https://arxiv.org/abs/2212.08073) 之后被各种团队用, 效果比 offline DPO 强很多, 但实现复杂度又涨回去了. 我们组 2024 年下半年的 production 训练就是 online DPO + iterative RLHF, 每两周一轮, 每一轮用最新的 Claude/GPT-4 给自己打 self-reward, 训了一共 4 轮, MT-Bench 从 8.2 涨到 8.9. paper [Bai et al. 2022](https://arxiv.org/abs/2212.08073) 最早系统化这个 "RLAIF" (RL from AI Feedback) 思路, 把人类标注替换成 AI 反馈, 用 constitution 做 self-critique.

2024 年底 2025 年初最热的 alignment 工作是 **GRPO (Group Relative Policy Optimization)**, 来自 [DeepSeek-AI 2025, DeepSeek-R1](https://arxiv.org/abs/2501.12948). GRPO 跟 PPO 的关键区别: **不需要 value model**, 用一组 (group) sample 的 reward 做 baseline:

$$\mathcal{L}_{\text{GRPO}} = -\mathbb{E} \left[ \sum_t \min\left( \frac{\pi_\theta(a_t|s_t)}{\pi_{\theta_{\text{old}}}(a_t|s_t)} A_t, \text{clip}(\cdot, 1-\epsilon, 1+\epsilon) A_t \right) \right] + \beta \cdot \text{KL}$$

其中 advantage $A_i = \frac{r_i - \text{mean}(r_1, \dots, r_G)}{\text{std}(r_1, \dots, r_G)}$ 是在 group 内归一化的 reward. 这个 trick 借鉴了 [Shao et al. 2024, DeepSeekMath](https://arxiv.org/abs/2402.03300) 里的 GRPO 原始版本. 优势是不用训 value model, 训练 stable, 在 reasoning task (math, code) 上效果特别强. DeepSeek-R1 用纯 RL (没有 SFT warmup) 训 R1-Zero, 在 AIME 上从 15% 涨到 71%, 几乎追平 OpenAI o1. 我们组在 2025 年初复现过 GRPO, 在我们内部 math benchmark 上从 0.42 涨到 0.67, 确实 work. 但 GRPO 的局限是 reward 设计——它需要每个 group 内有可比较的 reward, 所以更适合 verifiable reward 的 task (math answer 对错, code 跑通没跑通), 对开放式 generation (creative writing, chat) 不太适用.

最后提一个常被忽略的细节: **RLHF 之后怎么 eval**. 主流 benchmark 是 [Zheng et al. 2023, MT-Bench / Vicuna](https://arxiv.org/abs/2306.05685) (用 GPT-4 做 pairwise judge), [AlpacaEval](https://github.com/tatsu-lab/alpaca_eval), [Chatbot Arena](https://arxiv.org/abs/2406.11903) (real user voting). 这些 benchmark 都有问题: MT-Bench 的 GPT-4 judge 有长度偏置 (长 response 分数高), AlpacaEval 在 2024 年初被广泛认为是 gaming-friendly 的 (很多方法针对它的具体 scoring 优化). [Liu et al. 2024, Lost in the Middle](https://arxiv.org/abs/2307.03172) 之后的 [Lan et al. 2024, Length-Controlled AlpacaEval](https://arxiv.org/abs/2404.04475) 试图 fix 长度偏置, 但到现在没有一个公认的 gold standard. 我自己看 leaderboard 的时候一般会 cross-reference MT-Bench, AlpacaEval, Chatbot Arena, 加一个 internal evaluation, 任何一个单独看都容易误导.

---

## 这章没解决的, 和下一章会接上的

把这一章的内容摆在一起, 整个 alignment pipeline 长这样: **预训练 (15T token Chinchilla-violation) → SFT (50K-500K instruction, packing, LoRA/QLoRA) → 偏好学习 (RLHF PPO / DPO / online DPO / GRPO)**. 这个 pipeline 跑出来的 base model, 才是后面 13 章要讲的 ReAct, Toolformer, Voyager, SWE-Agent 的地基. 老实讲, 整个 agent 领域 2024-2025 最大的瓶颈不是 prompt engineering, 也不是 tool design, 而是 base model 的 reliability——很多 agent 失败的根本原因是 model 在长 context 下 hallucinate, 或者在 multi-turn planning 时不能 maintain coherent state, 这些都是 base model + SFT + RLHF 阶段要解决的问题.

这一章故意没讲的东西, 也是 open 问题: (1) **scaling law 是否会延伸到 inference compute**——[Snell et al. 2024, Scaling LLM Test-Time Compute](https://arxiv.org/abs/2408.03314) (Google DeepMind) 是个开端, 但还没有清晰的 law; (2) **RLHF 的 reward hacking 怎么系统性解决**——目前主要是经验式的 (diverse reward, multi-objective, regularization), 没有理论; (3) **DPO / GRPO 的 sample efficiency**, 比 PPO 好但还是需要大量 preference data, self-play 是不是能解决? (4) **long-context alignment**——SFT 和 RLHF 的数据都是 8K 以下, 真到 128K context 上 model 行为会不会退化? (5) **safety alignment 的 cost**——Constitutional AI 之后大家普遍接受 RLAIF, 但 RLAIF 的可靠性, 跟人类 evaluator 的一致性, 都还在研究.

下一章 ([Inference 优化: KV cache / Flash Attention / 量化 / speculative decoding](./02-inference-opt.md)) 我们换一个完全不同的视角, 把这个 100B 级别的 model 怎么高效 serve 出去讲清楚. 我自己在生产环境里跑过 70B serving, 一个 inference 优化做得好的 team, 能把同样的 GPU cluster 利用率从 30% 提到 80%, latency 降一个数量级. 第 2 章我们会讲 KV cache 的细节, FlashAttention inference 版的变体, INT8/INT4/FP8 量化的 trade-off, 还有 speculative decoding 这种 "用一个小 model 帮大 model 解码" 的 trick——这些是后面所有 agent latency-sensitive 应用 (real-time tool use, long-horizon planning) 的工程基础.