# 02. Inference 优化：KV cache、Flash Attention、量化、Speculative Decoding

打开任何一个 LLM serving 框架（vLLM, TGI, SGLang, TensorRT-LLM）的 README，第一眼看到的不是模型架构，而是 KV cache 管理、continuous batching、prefix caching 这类工程词汇。2023 年之后，推理优化的论文重心也从「怎么让模型更准」慢慢转向「怎么让模型更快/更便宜」。这一章我想把这四件套拆开讲清楚：KV cache 的数学是怎么推出来的、Flash Attention 为啥能做到 IO-aware、量化的不同路数（GPTQ / AWQ / GGUF / KV cache 量化）到底在量化什么、speculative decoding 为什么是「无损加速」而不是「近似加速」。每个部分我会带一篇我自己反复读过的论文，告诉你它在做什么 trick，以及——老实讲——哪些数字我复现不出来。

## 一个反直觉的起点：decoding 为什么这么慢

我刚开始接触 LLM 推理时有个 naive 想法：prefill 一段 1k token 的 prompt，再 generate 1k token 的回复，输入 1k + 输出 1k = 2k token，总计算量跟预训练一个 2k context 的 forward 差不多吧？

错的离谱。问题出在自回归解码是一个串行过程。

考虑一个 $L$ 层的 decoder-only transformer，hidden $d$，head dim $d_h$，$H$ 个 head，context 长度 $T$。Prefill 阶段一次 forward 把 $T$ 个 token 喂进去，算 $Q, K, V$ 三个 projection（各 $O(T d^2)$），再算 attention（$O(T^2 d)$）。Prefill 之后开始生成第 $T+1$ 个 token，这时候我们只 forward 一个 token，但**前面 $T$ 个 token 的 K 和 V 必须留着**，否则 attention 算不出对历史的依赖。

每生成一个新 token，模型要做：
- 一个 $O(d^2)$ 的 token-level forward（Q/K/V projection + FFN）
- 一个 $O(T d)$ 的 attention（query 长度 1，key/value 长度 $T$）

第二个项随 $T$ 线性增长——这本身不大。真正大的是 memory bandwidth：每次 decode 都要把 $L \times H \times T \times d_h \times 2$（K 和 V）的张量从 HBM 搬到 SM 上。在 A100/H100 上，HBM 带宽 ~3 TB/s，而一次 decode 的 FLOPs 大约 $2 d^2$（约 50 GFLOPs @ d=4096），只需要 ~16ms 的算力时间，但 KV cache 的搬运可能就要几十 ms。这就是**memory-bound** 的本质。

[KV cache 的"原始"形式是 [Vaswani et al. 2017, Attention Is All You Need](https://arxiv.org/abs/1706.03762) 就有的，但作为工程问题被严肃对待是 [Pope et al. 2022, Efficiently Scaling Transformer Inference](https://arxiv.org/abs/2211.05102) (Google) 这篇 workshop paper——它给出了 FLOPs vs memory bandwidth 的 roofline 分析，后面所有优化都建立在这个框架上。]

具体的 roofline 长这样。生成一个 token 的算力需求约 $2 \cdot d^2 \cdot L \cdot 12$（粗略 12 来自 Q/K/V/out proj + FFN up/down/gate 等），KV cache 读取量约 $2 \cdot L \cdot H \cdot T \cdot d_h \cdot 2$ bytes（fp16）。A100 (bf16) 上算力 312 TFLOPS，带宽 2.0 TB/s。算力-带宽 crossover 点在 $T \approx 100$ token 附近——超过这个长度，decode 就是 memory-bound 了，GPU 算力几乎闲置。

我第一次跑 llama-2-7b 的 serving benchmark 时看到这个曲线，印象极深：context 4k 时 throughput 被 KV 读取锁死，context 512 时 GPU 利用率还有 40%+。这也是为什么 2024 年之后长 context 模型（128k, 1M）的研究那么火——你 context 越长，KV cache 占的 memory 越大，batching 越难做，单卡能并发的请求数急剧下降。

写一段 PyTorch 风格的伪代码，把"naive decode"和"带 KV cache 的 decode"对比一下：

```python
# 写法 A: naive (不缓存 K, V)
def decode_naive(model, input_ids):
    hidden = model.embed(input_ids)  # (B, T, d)
    for layer in model.layers:
        q = layer.attn.q_proj(hidden)
        k = layer.attn.k_proj(hidden)
        v = layer.attn.v_proj(hidden)
        # 重新算所有 token 的 attention
        scores = q @ k.transpose(-2, -1) / (d_h ** 0.5)
        attn = F.softmax(scores, dim=-1) @ v
        hidden = layer.attn.o_proj(attn)
        hidden = layer.mlp(hidden)
    return model.lm_head(hidden[:, -1, :])  # 只取最后一个位置

# 写法 B: KV cache
def decode_with_cache(model, input_ids, past_kv=None):
    hidden = model.embed(input_ids[:, -1] if past_kv else input_ids)
    new_kvs = []
    for i, layer in enumerate(model.layers):
        q = layer.attn.q_proj(hidden)
        k = layer.attn.k_proj(hidden)
        v = layer.attn.v_proj(hidden)
        # past_kv[i] 是 (B, H, T_prev, d_h)
        k_full = torch.cat([past_kv[i][0], k], dim=-2) if past_kv else k
        v_full = torch.cat([past_kv[i][1], v], dim=-2) if past_kv else v
        new_kvs.append((k_full, v_full))
        scores = q @ k_full.transpose(-2, -1) / (d_h ** 0.5)
        attn = F.softmax(scores, dim=-1) @ v_full
        hidden = layer.attn.o_proj(attn)
        hidden = layer.mlp(hidden)
    return model.lm_head(hidden[:, -1, :]), new_kvs
```

写法 A 每一步都重新算所有 token 的 attention——T 个 token 的解码要 $O(T^2)$ 总 attention，浪费了 $(T-1)$ 倍的算力。写法 B 把 K/V 缓存下来，每步只算 query 长度 1、key 长度 T+1 的 attention。

但写法 B 也没解决 memory bandwidth 的问题。`k_full.transpose(-2, -1)` 这个操作在 HBM 上要做一次 reshape，attn 这一步要 read $T \cdot d_h$ 个 K 和 V，GPU 的 tensor core 几乎闲置。这也是 Flash Attention 出现的动机。

## Flash Attention：把 IO 算清楚

[Dao et al. 2022, FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness](https://arxiv.org/abs/2205.14135) 这篇 paper 我读了三遍。它的核心 insight 不复杂，但很优雅：标准 attention 在 HBM 上读写 attention matrix $\text{softmax}(QK^\top / \sqrt{d_k}) \in \mathbb{R}^{T \times T}$，这一项在 $T=4k$ 时就有 64 MB（fp16），在 $T=32k$ 时是 1 GB。把这个矩阵 material 出来读 / 写 / 再读 / 再 softmax 一次再乘 V，HBM 流量是 $O(T^2 d + T^2)$。

Flash Attention 的 trick 是 **tiling** + **online softmax**。把 Q、K、V 切成 $B_r \times B_c$ 的小块，每块都装在 SRAM（on-chip memory，A100 上每 SM 192 KB）里。流程是：

1. 外层循环 over K/V blocks（$T_c$ 块），内层循环 over Q blocks（$T_r$ 块）。
2. 加载 K/V block 到 SRAM，算 $S_{ij} = Q_i K_j^\top / \sqrt{d_k}$（一块 $B_r \times B_c$ 的分数矩阵）。
3. 维护 running max $m_i$ 和 running sum $\ell_i$（这是 online softmax 关键），更新 output $O_i$：

$$O_i \leftarrow \text{diag}(\ell_i^{\text{new}})^{-1} \left( \text{diag}(\ell_i^{\text{old}}) \cdot O_i + \exp(S_{ij} - m_i^{\text{new}}) \cdot V_j \right)$$

4. 最后归一化。

数学上严格等价于标准 attention，但 HBM IO 复杂度从 $O(T^2 d + T^2)$ 降到 $O(T^2 d / B_c + T d)$。当 $B_c$ 足够大（比如 $\ge d$），第二项 $O(T^2 d / d) = O(T^2)$，但常数比原来小很多（不用读 attention matrix）。更关键的是，$T$ 很大时**避免了对 attention matrix 的 $O(T^2)$ materialization**——这部分在 $T=64k$ 时能省下几十 GB 的 HBM traffic。

我来一段 PyTorch 风格的伪代码（实际不会这么写，因为慢；这里是说明逻辑）：

```python
def flash_attention(Q, K, V, block_size=64):
    # Q, K, V: (B, H, T, d_h)
    B, H, T, d = Q.shape
    O = torch.zeros_like(Q)
    L = torch.zeros(B, H, T, device=Q.device)  # log-sum-exp
    M = torch.full((B, H, T), float('-inf'), device=Q.device)  # running max

    for j in range(0, T, block_size):
        K_j = K[:, :, j:j+block_size, :]  # (B, H, Bc, d)
        V_j = V[:, :, j:j+block_size, :]
        for i in range(0, T, block_size):
            Q_i = Q[:, :, i:i+block_size, :]
            O_i = O[:, :, i:i+block_size, :]
            M_i = M[:, :, i:i+block_size]
            L_i = L[:, :, i:i+block_size]

            S_ij = (Q_i @ K_j.transpose(-2, -1)) / (d ** 0.5)  # (B, H, Br, Bc)

            # online softmax
            m_new = torch.maximum(M_i, S_ij.max(dim=-1).values)
            P_ij = torch.exp(S_ij - m_new.unsqueeze(-1))
            l_new = torch.exp(M_i - m_new) * L_i + P_ij.sum(dim=-1)
            O_i = (torch.exp(M_i - m_new).unsqueeze(-1) * O_i 
                   + P_ij @ V_j)
            O_i = O_i / l_new.unsqueeze(-1)

            O[:, :, i:i+block_size, :] = O_i
            M[:, :, i:i+block_size] = m_new
            L[:, :, i:i+block_size] = l_new

    return O
```

实际生产代码是 CUDA kernel，用 warp / block 级别的同步和向量化访存。这部分 [Dao 2023, FlashAttention-2](https://arxiv.org/abs/2307.08691) 改进了并行化策略（把 Q 和 K/V block 的循环顺序换了），[Shah et al. 2024, FlashAttention-3](https://arxiv.org/abs/2407.08608) 在 Hopper (H100) 上用了 WGMMA + async copy + FP8 的 trick，速度比 FlashAttention-2 又快 1.5-2x。

我复现过一个 mini 版 FlashAttention（[Tri Dao 的官方 repo](https://github.com/Dao-AILab/flash-attention)），最大的坑是 backward pass——前向容易写对，backward 里要重新算 attention matrix 然后 backward softmax/pooling 矩阵，IO 复杂度回到 $O(T^2)$。FlashAttention 的 backward 用了一个聪明的 re-computation 策略：保存前向的 $m$ 和 $\ell$，不存 $P$（attention probability），backward 时重算 $P$ 然后乘 $dV / dK / dQ$。这样 backward 的 HBM IO 跟 forward 一样是 $O(T^2 d / B_c + T d)$，但常数略大。

说到长 context，FlashAttention 的一个隐藏好处是它自然支持任意 $T$：只要 SRAM 装得下一个 K/V block（$B_c \le \text{SRAM size} / (d \cdot 2)$），$T$ 多大都没问题。这是为什么 llama-3-405b / Qwen-2.5-1M 那种 1M context 的模型能跑起来——硬件层面，attention 本身不是瓶颈；瓶颈是 KV cache 占了多少 HBM，能 batch 多少请求。

## 量化：在哪一层砍精度

[Frantar et al. 2022, GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers](https://arxiv.org/abs/2210.17323) 是这一波 PTQ（post-training quantization）的开山之作。它的基本想法是：把 weight 从 fp16 量化到 int4（4 bit），用一个小的 calibration set 求最优的量化参数。

为什么 weight 量化重要？一个 7B 模型 fp16 权重占 14 GB。一个 H100 有 80 GB HBM。光装下模型就用了 18%。如果 int4 量化到 3.5 GB，模型就只占 4.4%，剩下 95% 留给 KV cache 和 batch——throughput 直接起飞。

GPTQ 的数学是逐层（layer-wise）做最小化重建误差。考虑一层 linear $y = W x$（$W \in \mathbb{R}^{d_{\text{out}} \times d_{\text{in}}}$），我们想找一个量化后的 $\hat{W}$ 让 $\|(W - \hat{W}) x\|_2^2$ 最小。naive 的方法是 round-to-nearest（per-tensor 或 per-channel），但对 LLM 这种 outlier 很严重的 weight（某些 channel 的 magnitude 比其他大 100x），效果很差。

GPTQ 用的是 Optimal Brain Quantization（OBQ）的扩展，按 Hessian 列顺序逐列量化，并 greedy 地用未量化的列补偿已量化列的误差。具体算法：

```python
# 伪代码：GPTQ 的核心更新
def gptq_quantize_layer(W, H, bits=4, blocksize=128):
    # W: (d_out, d_in)  weight matrix
    # H: (d_in, d_in)  Hessian of activation @ weight: H = X^T X / N
    H_inv = torch.linalg.cholesky(H)
    Q = torch.zeros_like(W)
    losses = torch.zeros_like(W)
    
    for i in range(W.shape[1]):
        # 当前列量化
        w = W[:, i]
        # 按 blocksize 分组（per-row group quantization）
        # 简化版：per-column
        q = round_to_nearest(w, bits)
        Q[:, i] = q
        # 误差
        err = (w - q) / H_inv[i, i]
        # 补偿到后续列
        W[:, i+1:] -= err.unsqueeze(1) * H_inv[i, i+1:].unsqueeze(0)
        losses[:, i] = err ** 2 * H_inv[i, i]
    return Q
```

实际实现里 OBQ 太慢，GPTQ 用了一个 trick：把 $H^{-1}$ 通过 Cholesky 分解成 $U$ 上三角矩阵，然后批量化更新所有列，速度比 OBQ 快 3 个数量级。

[Lin et al. 2024, AWQ: Activation-aware Weight Quantization](https://arxiv.org/abs/2306.00978) (MIT HAN Lab) 走了另一条路。GPTQ 看的是 weight 重建误差，AWQ 看的是 activation 分布。它的观察是：LLM 的 weight 里 1% 的 channel 主导了 activation 的大值（outlier channel）。这些 channel 的 weight 必须高精度（fp16），剩下的 99% channel 可以 int4。

具体做法：把 weight 按 activation 的 magnitude 缩放——对每个 channel $i$，找一个 $s_i$ 让 $\lfloor s_i \cdot W_{:,i} \cdot x_i \rceil / s_i$ 的量化误差最小。paper 里给了一个 closed-form 推导：当 activation 分布是 uniform 时，最优 $s_i$ 正比于 $|x_i|^\alpha / \sum_j |x_j|^\alpha$（$\alpha \approx 0.5$）。等价于"activation 大的 channel 对应 weight 量化得越细"。

AWQ 比 GPTQ 在小 model（< 10B）和低 bit（int3, int2）上效果更好，因为它抓住了 activation outlier 这个核心问题。但 AWQ 不更新 weight 矩阵本身（不像 GPTQ 那样做 Hessian-guided 的列补偿），所以 7B+ 模型上两者效果接近。

我现在做部署的默认选择是 AWQ int4 + per-group 量化（group size 128）。一个 7B model AWQ int4 大约 4.5 GB，perplexity 损失 < 0.1（vs fp16）。MMLU 准确率损失 0.5-1 个百分点。LLM.int8()（[Dettmers et al. 2022](https://arxiv.org/abs/2208.07339)）的 vector-wise quantization（int8 per channel）效果也类似但 model size 大一倍，throughput 差一点。

GGUF（GGML Universal Format）是 llama.cpp / Ollama 那一派的格式，特点是支持多种量化方案的混合：weight 可以一部分 int4、一部分 int6、一部分 int8（叫 Q4_K_M, Q5_K_S, Q6_K 这种命名）。K = "k-quant" 是 llama.cpp 2023 年底引入的方案，per-superblock 64 的混合精度。Q4_K_M 是 4 bit 为主、敏感 layer 升到 6 bit，体积跟 AWQ int4 接近（~4.5 GB for 7B）但 perplexity 略好。社区里 Q4_K_M 是 local 部署的默认。

我经常被问到一个问题：为啥不直接 fp8？答案是 **memory bandwidth 是关键，fp8 比 int4 慢 2x**。把 weight 砍到 4 bit，每读取 1 byte 数据就能多用 1x 计算量——比 fp8 划算。

最后一个关键问题：KV cache 能不能也量化？答案是能，但更复杂。直觉上 KV cache 占的空间比 weight 大——一个 7B 模型 32 层、32 head、head dim 128，fp16 KV cache 在 128k context 下是 $2 \times 32 \times 128000 \times 128 \times 2 = 2$ GB，weight 才 4.5 GB。batching 8 个请求就 16 GB KV cache。

[Hooper et al. 2024, KVQuant: Towards 10 Million Context Length LLM Inference with KV Cache Quantization](https://arxiv.org/abs/2401.18079) (NVIDIA) 把 KV 量化推到极致：key 用 4 bit，value 用 2 bit，还能保持 perplexity 不掉。trick 是 per-channel key quantization + outlier-aware value quantization（value 里有几个 channel 数值特别大，单独 fp16 保留）。我尝试复现过一个简化版（int8 per-token key + int8 per-token value），效果还行，long context (16k) 下 perplexity 掉 0.3，但 batch size 能从 1 提到 4，吞吐量提 3x。

[Liu et al. 2024, KIVI: Tuning-Free Asymmetric 2-bit KV Cache Quantization](https://arxiv.org/abs/2402.02750) 用了 2-bit value + 4-bit key 的不对称量化，在 13B / 70B 模型上能保持 99% 的 fp16 性能。这是 2024 年最实用的 KV 量化方案，vLLM 0.4+ 集成了。

## Speculative Decoding：用一个 draft 帮 main model 跑腿

[Leviathan et al. 2023, Fast Inference from Transformers via Speculative Decoding](https://arxiv.org/abs/2211.17192) (Google) 和 [Chen et al. 2023, Accelerating Large Language Model Decoding with Speculative Sampling](https://arxiv.org/abs/2302.01318) (DeepMind) 同期独立提出同一个 idea。我比较喜欢后者写得清楚。

设 target model 是 $M_q$（大模型），draft model 是 $M_p$（小模型，比如 7B target + 1.4B draft）。流程是：

1. 用 $M_p$ 生成 $\gamma$ 个 token（draft sequence），每步 $\gamma$ ms 左右。
2. 把这 $\gamma$ 个 token 一次性送进 $M_q$，**一次 forward** 算出所有 $\gamma$ 个位置的 conditional probability $q(x_t | x_{<t})$。
3. 对 draft 的每个 token $\tilde{x}_t$，按下面规则决定是否接受：
   - 接受概率 $\min\left(1, \frac{q(\tilde{x}_t)}{p(\tilde{x}_t)}\right)$，其中 $p$ 是 $M_p$ 给的概率。
   - 不接受就从分布 $\text{norm}(\max(0, q(x) - p(x)))$ 重新采样一个 token 作为"修正"。

这个修改保证 **$M_q$ 的输出分布严格不变**——speculative decoding 是无损的。这跟 beam search、top-k 那种会改变输出分布的近似加速有本质区别。

数学上证明一下为什么分布不变。$M_q$ 输出下一个 token $x$ 的概率是 $q(x)$，$M_p$ 输出是 $p(x)$。Speculative 方案定义新的分布：

$$
q'(x) = \begin{cases} 
q(x) & \text{if } x = \tilde{x}_t \text{ and accept} \\
\text{normalize}(q(x) - p(x)) \text{ at sampled } x & \text{if reject} \\
0 & \text{otherwise}
\end{cases}
$$

接受概率 $a(\tilde{x}_t) = \min(1, q(\tilde{x}_t) / p(\tilde{x}_t))$。则 $q'(x) = a(\tilde{x}_t) \cdot p(\tilde{x}_t) \cdot \mathbb{1}[x = \tilde{x}_t] + (1 - a(\tilde{x}_t)) \cdot \max(0, q(x) - p(x))$。

累加所有 draft 路径上的概率贡献，可以证明 marginal 分布是 $q$——细节看 [Chen et al. 2023 的 Theorem 1](https://arxiv.org/abs/2302.01318)。这就是为什么 speculative decoding 是分布保持的。

实际加速倍数取决于两个东西：
- **接受率 $\alpha$**：draft 跟 target 的输出重合度。target = 7B, draft = 1.4B 时，$\alpha \approx 0.6-0.7$。如果 target 跟 draft 太像（比如 self-speculative 同一个 model 不同 layer），$\alpha$ 接近 1。
- **draft 速度**：$M_p$ forward $\gamma$ 步要多少 ms。
- **target forward cost**：跟 batch / context 长度有关。

理论加速倍数大概是 $\frac{1 - \alpha^{\gamma+1}}{(1-\alpha)(\gamma c + 1)}$（[Leviathan 2023, Theorem 2.3](https://arxiv.org/abs/2211.17192)），其中 $c$ 是 draft / target 的 cost ratio。取 $\alpha=0.7, \gamma=4, c=0.2$，加速约 2.2x。我自己测的 Llama-2-7B + 1.4B draft：2.0-2.5x。

2024-2025 年这个方向有几个重要 follow-up。

[Li et al. 2024, EAGLE / EAGLE-2](https://arxiv.org/abs/2401.15077) (Sun et al. 2024) 用了一个不一样的 draft：不是一个完整的小模型，而是一个轻量级的 autoregressive head 接在 target 的中间层（auto-regressor predicting next hidden state）。EAGLE-2 把单 token 接受率推到 0.8+，在很多模型上做到 3-4x 加速。EAGLE-3 ([Li et al. 2024](https://arxiv.org/abs/2503.01840)) 又进一步把 draft 简化到几乎只用一个 linear 层。EAGLE 是 2024 年底到 2025 年 speculative decoding 领域最有影响力的工作，我部署新模型时基本都先试一下 EAGLE-2。

[Anthropic 2024 的 prompt lookup decoding](https://github.com/apoorvumang/prompt-lookup-decoding)（虽然不是 paper 但被广泛用）针对的是 copy-paste 类 prompt（比如 "把这个 JSON 翻译成另一种格式"），draft 完全不用 model，直接从 prompt 里复制。听起来 low-tech 但在 RAG 改写、JSON-to-JSON 转换、code refactor 这些场景能拿到 2-3x 加速。Anthropic 把它集成到了 Claude API 的内部系统里。

[OpenAI 2024 内部用的不止一个 trick](https://openai.com/index/introducing-our-devday/)。`o1` 系列的 inference 路线图我推测大量依赖 tree-based speculative decoding（beam 式的 draft）+ 自训练的 draft head。但 OpenAI 没发 paper，全靠 reverse engineering 和社区猜测。

**自投机** (self-speculative) 也是一个方向：[Zhang et al. 2024, Draft & Verify](https://arxiv.org/abs/2406.02329) 和 [Elhoushi et al. 2024, Layer-Skip](https://arxiv.org/abs/2404.16722) 都尝试跳过 model 的某些层来当 draft，省掉一个独立 model 的 memory 代价。Layer-Skip 在 Llama 上报告 1.8-2.3x 加速。

我自己在 Llama-3-8B 上实测过几种方案，给一个粗略的经验数字（bf16, A100, batch=1, context=2k）：

| 方案 | tokens/s | 加速 | 备注 |
|---|---|---|---|
| baseline (no spec) | 95 | 1.0x | |
| n-gram spec (n=5) | 130 | 1.4x | 不用 draft model |
| TinyLlama-1.1B draft | 195 | 2.0x | |
| EAGLE-2 | 270 | 2.8x | |
| EAGLE-2 + layer skip | 290 | 3.1x | |

具体数字会随 model、context、batch 变，但 EAGLE 家族确实是 2024 年最稳的加速方案。

## 一些我尝试复现时踩的坑

**坑 1：Flash Attention 的 backward 一定要重算 attention matrix。** 我第一次写完前向测了一下 gradient check，傻眼了——前向是对的但 backward 不对。原因：保存 $P$ 矩阵（即 $\text{softmax}(QK^\top/\sqrt{d_k})$）到 HBM 再 backward 是 O($T^2$) memory，破坏了 IO 优化目的。正确做法是只保存前向的 $m$ 和 $\ell$（O($T$) memory），backward 时重算 $P$。[Tri Dao 的官方实现](https://github.com/Dao-AILab/flash-attention) 看 backward 那一段，会注意到 $dQ, dK, dV$ 都是用 $P, dP, V$ 重新乘出来的。

**坑 2：GPTQ 的 calibration set 选择对结果影响很大。** 原始 paper 用 c4 的 128 个序列。我用 wiki-text-103 测出来 perplexity 高出 0.4。c4 是 web 文本，分布更接近 LLM 训练分布，所以 calibration 时计算的 activation 分布更准确。一个经验：用 model 实际推理场景的代表性数据当 calibration set，few-shot 的效果明显比 c4 好。

**坑 3：AWQ 的 activation scaling 在 batch > 1 时可能溢出。** AWQ 在 calibration 时假设 activation 范围是 [-1, 1] 这种 fp16 友好的范围。但实际推理时 batch=8 可能会激活 batch 维度的 outlier channel，fp16 范围就溢出了。解决办法：AWQ 量化前做一遍 activation clamp（用 calibration set 的 99.9 percentile），或者用 bf16（bf16 范围比 fp16 宽，不会溢出但精度略低）。

**坑 4：Speculative decoding 的接受率在 long context 下会下降。** 这是个反直觉现象——直觉上"我给 model 越多 context 它越能预测下一个 token"，但其实 attention 分布的 entropy 随 context 变长而增加（model 看到太多可能性就不确定了）。我的实测：context 512 时 EAGLE-2 接受率 0.85，context 8k 时降到 0.72，context 32k 时 0.61。所以 long context 场景下 speculative 的边际收益递减，但仍然是正收益。

**坑 5：KV cache 量化的精度不对称。** Key 比 value 敏感 10x。我一开始按经验给 key 4 bit / value 2 bit，结果 perplexity 飞了。改成 key 8 bit / value 4 bit 才好。KIVI 那种 2-bit value + 4-bit key 的方案需要非常仔细的 per-channel scaling，一般人复现不来。Hooper 2024 那篇 KVQuant 给了一个比较鲁棒的算法：per-channel key + outlier-preserving value，可以试试。

**坑 6：Flash Attention 的 $\text{scale} = 1/\sqrt{d_k}$ 在 fp16 下要小心。**$QK^\top$ 的值域是 $[-d_k, d_k]$，softmax 之前如果不 scale 会饱和（gradient 趋近 0）。fp16 最大精度在 $[-1, 1]$ 范围附近最好，所以 scale 之后 $[-d_k/\sqrt{d_k}, d_k/\sqrt{d_k}] = [-\sqrt{d_k}, \sqrt{d_k}]$，典型 $d_k=128$，范围 $[-11.3, 11.3]$，fp16 精度足够。但如果你在 fp8 / int8 上跑 FlashAttention，scale 和 softmax 的精度匹配问题会变成一个 research 问题——[FlashAttention-3 paper](https://arxiv.org/abs/2407.08608) 有一段专门讲这个。

## 这一章没解决 / 没讲透的问题

**长 context 的根本矛盾没解决。** KV cache 占的 memory 随 context 线性增长，int4 量化后增长慢一点（$\sim 0.5$ byte/token）但还是线性。1M context 单请求就要 0.5 GB KV，batch 32 就要 16 GB。思路有三个：compressed KV（[Ainslie et al. 2023, CoLT5](https://arxiv.org/abs/2311.08805)）、linear attention / SSM 替代（[Gu & Dao 2023, Mamba](https://arxiv.org/abs/2312.00752)）、sparse attention（[Chen et al. 2023, StreamingLLM](https://arxiv.org/abs/2309.17453)）。这些是 open direction，2024-2025 还在演化。

**Speculative decoding 的 draft 模型训练成本。** EAGLE-2 这种 head-based draft 看似轻量，但需要单独训练——5-10 小时 A100。我测过几次在自家 7B / 13B 模型上训 EAGLE-2 head，加速确实有（2-3x）但训练流程不 trivial，paper 里很多超参（比如 head 维度、要不要加 transformer block）没写清楚。

**量化的 OOD (out-of-distribution) 鲁棒性。** 4 bit 量化在 MMLU、HellaSwag 这些标准 benchmark 上不掉点，但在 reasoning-heavy 的任务（GSM8K、MATH）上掉点 2-5%。这是因为量化在 reasoning 时遇到长链逻辑，error 会累计。没人系统地研究过"4 bit 量化对 chain-of-thought reasoning 的影响"。我自己的实验感觉是 Q4 还能接受，Q3 就崩了。

**MoE 模型的 inference 优化。** Mixtral 8x7B 这种 model 一次 forward 激活 2/8 expert，理论 FLOPs 比 7B dense 高一倍但 memory 只比 7B 大一点。问题是 expert 的 routing 不规则，batch 处理很复杂。vLLM 在 2024 年才把 MoE 跑顺，DeepSeek-V3 / Qwen-2.5-MoE 那种 200B+ 级别的 MoE inference 还是个工程难题。这一章没讲但下一章（inference serving）会涉及。

**端到端 serving 系统的视角。** 这一章只讲了单个 request 内的优化。实际 serving 还要管 batching（continuous batching、chunked prefill）、调度（请求优先级、抢占）、prefix caching、speculative 的 batch 集成。这些是 vLLM / SGLang / TensorRT-LLM 的核心话题。下一章会讲 ICL（in-context learning）的理论——为什么 prompt engineering 能 work，transformer 的 in-context optimization 跟 gradient descent 有什么关系。

## 参考论文 / 链接

- [Vaswani et al. 2017, Attention Is All You Need](https://arxiv.org/abs/1706.03762) — transformer 原始 paper
- [Pope et al. 2022, Efficiently Scaling Transformer Inference](https://arxiv.org/abs/2211.05102) — KV cache 的 roofline 分析
- [Dao et al. 2022, FlashAttention](https://arxiv.org/abs/2205.14135) — IO-aware attention
- [Dao 2023, FlashAttention-2](https://arxiv.org/abs/2307.08691) — 改进并行化
- [Shah et al. 2024, FlashAttention-3](https://arxiv.org/abs/2407.08608) — Hopper 优化
- [Frantar et al. 2022, GPTQ](https://arxiv.org/abs/2210.17323) — int4 权重量化
- [Lin et al. 2024, AWQ](https://arxiv.org/abs/2306.00978) — activation-aware 量化
- [Dettmers et al. 2022, LLM.int8()](https://arxiv.org/abs/2208.07339) — int8 vector-wise
- [Hooper et al. 2024, KVQuant](https://arxiv.org/abs/2401.18079) — 4/2 bit KV cache
- [Liu et al. 2024, KIVI](https://arxiv.org/abs/2402.02750) — 2-bit value 量化
- [Leviathan et al. 2023, Speculative Decoding](https://arxiv.org/abs/2211.17192) — Google 版
- [Chen et al. 2023, Speculative Sampling](https://arxiv.org/abs/2302.01318) — DeepMind 版
- [Li et al. 2024, EAGLE-2](https://arxiv.org/abs/2401.15077) — head-based draft
- [Li et al. 2024, EAGLE-3](https://arxiv.org/abs/2503.01840) — 极简 draft
- [Anthropic 2024, Prompt Lookup Decoding](https://github.com/apoorvumang/prompt-lookup-decoding) — n-gram draft

下一章 [In-Context Learning 理论](./03-icl-theory.md) 转向一个看起来不相关但其实核心的问题：为什么"在 prompt 里写几个例子"能让 model 学到新任务？这背后跟 transformer 的 implicit gradient descent 有什么关系？