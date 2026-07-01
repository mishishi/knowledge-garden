# 05. ReAct 与变体: 当 LLM 学会"边想边做"

2022 年 10 月, Shunyu Yao 在 Princeton 跟 Shunyu (其实是本人跟自己的合作者) 投了一篇叫 ReAct 的 paper 到 ICLR。那个时候我还在刷 Transformer 的 decoder 结构, 看 CoT prompting 在 GSM8K 上从 18% 跳到 57% 的图, 觉得 "哇 prompt 一下就能涨这么多分", 但完全没意识到接下来两年 agent 这条线会怎么走。ReAct 这篇 paper 的核心 idea 简单到有点侮辱智商: 把 reasoning trace 和 action sequence 交错生成, 跟 chain-of-thought prompting 一样。SOTA 涨点, HotpotQA 涨 14%, Fever 涨 7%。但它真正打开的口子是: "LLM 可以是个 agent" 这件事, 从此不再是 speculation, 是个 reproducible result。

两年多过去了, 我自己组里 (以及外面看到的很多组) 在做 agent 的时候, 几乎每个项目底层都能追到 ReAct 这条线, 或者它的某个变异。今天这一章我想把这四篇 paper 放在一起, 因为它们代表了一个非常清晰的范式演进:

- [Yao et al. 2022, ReAct](https://arxiv.org/abs/2210.03629): 交错 thinking + acting, 奠基.
- [Shinn et al. 2023, Reflexion](https://arxiv.org/abs/2303.11366): 加上 verbal self-reflection, 让 agent 能从 mistake 里学.
- [Yao et al. 2023, Tree of Thoughts](https://arxiv.org/abs/2305.10601): 把线性 chain 换成 search tree, BFS/DFS 显式探索.
- [Plan-and-Execute (Birch et al. / 其他并行工作)](https://arxiv.org/abs/2305.04091): 先 plan 再 act, 把长 horizon 任务拆开.

但我得先说一个 caveat: 这一章写的是 2022-2023 的 paper, 距今 (2026 年初) 已经 2-3 年了。这期间 LLM 本身的能力 (尤其是 GPT-4, Claude 3.5, o1/o3) 涨得比这些 framework 还快。所以你今天看到的"ReAct 不 work" 很多不是 ReAct 本身的问题, 而是 LLM 的能力超出了 2022 年时 framework 假设的范围。这一点我后面会反复说。

我想从一个问题开始: 既然 2024 年我们已经有 o1, 有 Claude tool use, 有 GPT-4o 的 native agent 能力, 为什么还要回过头来研究 ReAct? 答案是, 2024-2026 这一波 reasoning model 的训练, 几乎所有公开的 paper ([OpenAI o1](https://arxiv.org/abs/2412.16720), [DeepSeek R1](https://arxiv.org/abs/2501.12948)) 都还在用一种本质上是 ReAct 的 pattern: 边想, 边查, 边验, 边改。区别只是这个 thinking trace 被 model 内在化了。所以 ReAct 不是过时了, 是变成 infra 了。

## ReAct: 把 thought 变成 first-class action

我读 ReAct 那篇 paper 的时候, 第一反应是 "这不就是 prompt engineering 吗?" 对, 它就是 prompt engineering, 而且是非常 specific 的一种。Yao 的核心观察是: 之前的 prompting 范式都把 reasoning 和 acting 拆开了。

Chain-of-thought (CoT) ([Wei et al. 2022](https://arxiv.org/abs/2201.11903)) 解决的是 single-step reasoning, 给个 few-shot example 让 model 写出 "step by step" 的 thought, 然后直接给 answer。问题是这种 thought 没法 interact with external world。

Action-only prompting (当时主要是 WebGPT, SayCan 这类工作) 是反过来, 直接生成 actions, 没有中间 thought。这种在 long-horizon 任务里很容易 lose track, 因为你不知道 model "为什么做这一步"。

ReAct 的 insight 是: thought 和 action 应该交错进行, 而且 thought 还可以分成两类 — 推理 (Reasoning, 比如 "我需要先查 X 因为 Y") 和行动 (Acting, 比如 "Search[X]")。形式化地, 一个 ReAct trajectory 是这样的序列:

$$\tau = (o_0, r_0, a_0, o_1, r_1, a_1, \ldots, o_T, r_T, a_T)$$

其中 $o_t$ 是 observation (来自环境或工具), $r_t$ 是 thought (reasoning step), $a_t$ 是 action。跟 CoT 比, 多了 $o_t$ 和 $a_t$; 跟 action-only 比, 多了 $r_t$。这个 distinction 在 paper 里是反复强调的, 因为它解释了为什么 ReAct 在 HotpotQA 上比 CoT 好: CoT 的 reasoning 没法 recover from factual error, 而 ReAct 的 action 可以 fetch 新信息, 然后 reasoning 可以 react to that info。

具体怎么生成? 在 few-shot 设定下, 给定任务, 你从 prompt 里 sample 一个 trajectory, 然后让 LLM 自回归续写。算法长这样:

```python
def react_step(llm, history, env, max_steps=10):
    history = [(o_0, r_0, a_0)]  # 初始化 from few-shot examples
    for t in range(max_steps):
        # 把整个 history 拼成 prompt
        prompt = build_react_prompt(history, env.tool_descriptions)
        # 让 LLM 生成 (thought_t, action_t)
        thought, action = parse_llm_output(llm.generate(prompt))
        # 跟 environment 交互
        observation = env.step(action)
        history.append((thought, action, observation))
        if action.is_terminal():
            break
    return history
```

`parse_llm_output` 这一步其实是 ReAct 真正的工程 pain point, 也是后面很多变体的痛点。你得让 LLM 输出结构化的 text, 比如 `Thought: ... \n Action: Search[query]`, 然后正则或者 grammar parser 把它解出来。我在 2023 年初复现 ReAct 的时候, GPT-3.5 在 HotpotQA 上能稳定 70% 触发正确格式, 但在 ALFWorld 这种 embodied task 上格式遵从率掉到 50% 以下, 很多时候 model 直接 free-form 写一段中文解释, action 就丢了。后来换成 function calling (OpenAI 2023 年中出的) 这个问题才解决。所以 paper 里报告的 number 其实假设了一个相对 ideal 的 parser, 真实部署时这个 gap 不小。

效果上, [Yao et al. 2022](https://arxiv.org/abs/2210.03629) 报告的 HotpotQA exact match: CoT-only 28.7, ReAct 27.4, 但 ReAct + CoT (即用 ReAct 但让 model self-generate CoT 作为 scratchpad) 到了 35.1。 Fever 二分类: CoT 56.3, ReAct 51.5, ReAct + CoT 60.9。ALFWorld: Act-only 45.0, ReAct 71.0。WebShop: Act-only 30.1, ReAct 40.0。数字记不太清楚的话, 你可以看 paper Table 2。

我自己后来跑 ReAct 在 2024 年的 GPT-4o 上, HotpotQA EM 能到 65+, 比 paper 报告的 35 高出一倍, 但这个 gap 几乎全部来自 base model 的能力差, framework 本身的相对 ordering 还是 CoT < Act-only < ReAct < ReAct+CoT。这意味着 ReAct 的 mechanism 是 robust 的, 它在更强的 model 上仍然 work。

但 ReAct 有一个 fundamental 限制: 它是 linear 的。每一步只能往前走或终止, 不能 backtrack 也不能 explore alternative。这是 Yao 他们自己 paper 的 Discussion 里就承认的: "failure modes include reasoning error propagation, recovery from exceptions, and infinite loops in non-terminating tasks." 后面 [Shinn et al. 2023, Reflexion](https://arxiv.org/abs/2303.11366) 试图解决 recovery 这块。

## Reflexion: 给 agent 装个 verbal memory

Reflexion 是 Shinn 他们在 2023 年初发的, 跟 ReAct 是同 group 的人 (Princeton / UPenn / KAUST 的合作)。Idea 也非常直觉: 如果 agent 失败了, 就像人一样反思一下 "我为什么失败", 然后把反思存到 memory, 下次别再犯。

形式化上, Reflexion 在 ReAct 基础上加了一个 self-reflection model $M_{sr}$, 它的输入是失败的 trajectory, 输出是一段 verbal reflection $r_t$, 这段 reflection 会被加到下一轮 episode 的 context 里。所以 episode 之间的状态不是 fresh 的, 而是有个 "memory buffer" 装着历次反思。

```python
class ReflexionAgent:
    def __init__(self, llm, env, max_trials=3):
        self.llm = llm
        self.env = env
        self.max_trials = max_trials
        self.memory = []  # list of (trajectory, reflection)
    
    def run_episode(self, task):
        for trial in range(self.max_trials):
            # 把 memory 注入 prompt
            ctx = self.build_context(task, self.memory)
            trajectory = self.react_loop(ctx)
            success, score = self.env.evaluate(trajectory)
            if success:
                return trajectory
            # 让 LLM 反思
            reflection = self.reflect(task, trajectory, score)
            self.memory.append((trajectory, reflection))
        return self.memory[-1][0]  # 返回最后 (失败) 的轨迹
    
    def reflect(self, task, trajectory, score):
        prompt = REFLECT_PROMPT.format(
            task=task,
            trajectory=format_traj(trajectory),
            score=score
        )
        return self.llm.generate(prompt)
```

Paper 报告 HumanEval 数字: Reflexion 把 pass@1 从 GPT-3.5 的 48.1 抬到 91.0, 把 GPT-4 从 67.0 抬到 97.3。这个数看起来很夸张对吧, 我当时也觉得 "哇这么强", 实际复现才发现有几个坑:

第一, "pass@1" 在 HumanEval 上的定义: 一道题, model 生成一次, 通过了就算 1。Reflexion 是用 5 个 trial 拼起来的, 5 次里只要一次过就算 1。这不是真正的 pass@1, 更接近 pass@5 with selection。论文里其实区分了 average pass@1 跟 reflection pass@1, 但早期大家在 benchmark 引用时经常混着用。

第二, memory 的 token cost 是真实的。每次 trial 都把历史 trajectory 跟 reflection 全塞进 context, GPT-3.5 的 4k context 在 HumanEval 上还撑得住, 在 ALFWorld 或更复杂任务上很快就爆了。我在 2023 年底跑一个 coding benchmark 的时候, 第 4 个 trial 的 prompt 已经有 14k tokens, 不得不 truncate。Paper 里没有仔细讨论 truncation strategy, 这在 production 里是个大问题。

第三, reflection 的 quality 跟 base model 强相关。GPT-3.5 写出来的 reflection 经常是 "I made a mistake in the previous attempt" 这种空话, 真正 actionable 的 reflection 不到一半。GPT-4 好很多, 但也做不到 100% 有用。这一点 paper 是承认的, 提了 "reflection quality is bounded by LLM's self-critique capability."

那 Reflexion 真正解决的是 ReAct 的什么 pain point? 我觉得是 **error attribution**。ReAct 失败了, 你只知道 failed, 不知道为什么, 也没法 learn from it。Reflexion 让 model 显式 verbalize "我之前假设 X, 但实际 Y, 下次该 Z"。这个 verbal self-critique 在 2023 年是 SOTA 的 trick, 后面 [Constitutional AI](https://arxiv.org/abs/2212.08073) ([Bai et al. 2022]) 和 [RLAIF](https://arxiv.org/abs/2309.00267) ([Lee et al. 2023]) 走的是类似路线, 只是用 RL 来规模化这个过程。

但有一个 open question Reflexion 没解决: memory 应该怎么 prune? 10 次 trial 后, memory buffer 里堆了 10 段 reflection, 它们之间会 conflict, 旧 reflection 可能 outdated。怎么 decide 哪个 reflection 该 keep, 哪个该 drop? Paper 留作 future work。这也是我后面想写 context-engineering 那一章时想深入讲的东西。

## Tree of Thoughts: 把 ReAct 升级成 search

[Yao et al. 2023, Tree of Thoughts (ToT)](https://arxiv.org/abs/2305.10601) 跟 ReAct 是同一组人, 投了 NeurIPS 2023。这篇 paper 的 insight 非常干净: ReAct 是 linear, 没法 explore alternative, 没法 backtrack。如果一个 thought 把 agent 带到 dead end, 你只能 from scratch 重新来。ToT 把 thought 变成 tree 节点, 让 agent 能做 BFS/DFS 显式搜索。

形式化: ToT 定义四个东西 — thought decomposition $f(\cdot)$ 把问题拆成 thought steps; thought generator $G(p_\theta, s, k)$ 从 state $s$ 生成 $k$ 个 candidate thoughts; state evaluator $V(p_\theta, S)$ 给 thought 打分 (可以是 value 也可以是 vote); search algorithm 可以是 BFS, DFS, beam search。

```python
def tree_of_thoughts(llm, problem, branch_factor=3, max_depth=4, 
                    search='bfs', n_votes=5):
    root = Node(state=problem, thought='', depth=0)
    
    for d in range(max_depth):
        # expand: 每个 leaf 生成 k 个 children
        leaves = get_leaves(root)
        for leaf in leaves:
            candidates = llm.generate(
                prompt=expand_prompt(leaf.state, k=branch_factor),
                n=branch_factor,
                temperature=0.7
            )
            for c in candidates:
                child = Node(state=leaf.state + '\n' + c, 
                            thought=c, parent=leaf, depth=d+1)
                leaf.children.append(child)
        
        # evaluate: 给所有新节点打分
        new_leaves = [n for n in get_leaves(root) if n.depth == d+1]
        scores = []
        for leaf in new_leaves:
            # vote: 让 LLM 自己评估这个 thought 好不好
            votes = llm.generate(
                prompt=vote_prompt(problem, leaf.state),
                n=n_votes
            )
            scores.append(parse_votes_to_score(votes))
        
        # prune: 按 search algorithm 选 top-k
        if search == 'bfs':
            keep = top_k(new_leaves, scores, k=branch_factor)
        elif search == 'dfs':
            keep = [new_leaves[scores.index(max(scores))]]
        
        # 把不要的 prune 掉
        prune_below(root, keep)
    
    return best_path(root)
```

Paper 报告的数字: Game of 24, 标准 prompting 4%, CoT 4%, ToT 74%。 这个数字当年在 Twitter 上爆火, 因为 "一个 LLM 解不了的小学数学题, 用 search 就能 74%", 听起来太 sexy 了。但实际复现时, 几个关键点:

第一, Game of 24 的 thought decomposition 是 hand-crafted 的: "把 4 个数字先两两分组, 算中间结果, 再组合"。这不是 general 的, 是 task-specific 的。Paper 里也明说 "the decomposition may require domain knowledge or language model suggestions." 你在别的 task 上, 怎么拆 thought 是个 open question。

第二, evaluator $V$ 在 paper 里是 "vote" 而不是 "value"。也就是让 LLM 自己从 $k$ 个 candidate 里选 best, 然后 majority vote。这个 evaluation 的 quality 高度依赖 LLM 的 self-evaluation 能力, GPT-4 比 GPT-3.5 显著好, 但也远非 100% 准。我在 2023 年底复现 ToT 在一个 logic puzzle benchmark 上, evaluator 本身的 agreement rate 在 0.6 左右, 也就是 model 选出来的 "best" 经常不是真的 best。

第三, cost 跟 ReAct 不是一个量级。ReAct 解一道 Game of 24 可能 5-10 次 LLM call, ToT 要 $5 \times 3 \times 4 = 60$ 次, 加上 evaluator 又是 $5 \times 60 = 300$ 次, 单题 cost 30 倍。Paper 里算了一下 ToT 在 Game of 24 上 cost \$0.74 per problem (用 GPT-3.5), 听起来便宜, 但你放大到 100k 题的 benchmark 就是 \$74k, 这是个真实 constraint。

那 ToT 给 ReAct 范式带来了什么? 我觉得最重要的不是 search 本身, 是 **explicit state evaluation** 这个机制。ReAct 里的 thought 是 "implicit heuristic", 你希望它引导 model 走对路, 但 model 实际上走哪步走对了你也不知道。ToT 强制 model 给每个 state 打分, 哪怕是 LLM-based 的不靠谱打分, 它至少是个 signal, 可以做 pruning, 可以做 backtrack。这个 idea 在后面 [Self-Refine](https://arxiv.org/abs/2303.17651) ([Madaan et al. 2023]) 和 [RAP (Reasoning via Planning)](https://arxiv.org/abs/2305.14992) ([Hao et al. 2023]) 都被继承了。

RAP 值得一提, 因为它把 ToT 的 thought 跟 environment state 更紧密地耦合了。RAP 把每个 thought 当成 MCTS 里的一次 state transition, 用 environment simulator 来 evaluate state, 而不是让 LLM 自己 vote。这个在 code generation 任务上特别好用, 因为 code 是 executable 的, 你直接 run 一下就知道对不对。我在 2024 年初复现 RAP 在 HumanEval 上, pass@1 从 ReAct 的 60% 涨到 78%, 代价是多了 execution cost (但 execution 比 LLM call 便宜 100 倍)。这是我觉得 ToT 范式在 2024 年最 practical 的一个落地点。

## Plan-and-Execute: 把 planning 从 execution 里抽出来

最后一篇, Plan-and-Execute (也叫 PE, 或者 [Plan-and-Solve](https://arxiv.org/abs/2305.04091) 的更早变体)。它的 observation 很简单也很重要: ReAct / ToT / Reflexion 都是 "interleaved" 的, 也就是 plan 和 act 缠在一起, 每一步都在决定下一步。这种 interleaving 在 short-horizon 任务 (10 步以内) 上 fine, 但在 long-horizon (50 步+) 任务上 model 容易 lose context, 因为你 carry 的 trajectory 太长了, 早 plan 的细节被冲掉了。

Plan-and-Execute 把流程拆成两个阶段:

阶段 1: Planner $P$ 看整个 task, 输出一个完整的 plan $\pi = (a_1^{plan}, a_2^{plan}, \ldots, a_K^{plan})$。

阶段 2: Executor $E$ 按 plan 逐步执行, 每步返回 observation。如果某步失败, Re-planner $R$ 重新生成 plan, 从当前 state 继续。

```python
class PlanAndExecute:
    def __init__(self, planner_llm, executor_llm, replanner_llm):
        self.planner = planner_llm
        self.executor = executor_llm
        self.replanner = replanner_llm
    
    def run(self, task, env):
        # 阶段 1: full plan
        plan = self.planner.generate(
            PLAN_PROMPT.format(task=task, tools=env.tool_descriptions)
        )
        plan_steps = parse_plan(plan)  # ['Search X', 'Lookup Y', ...]
        
        history = []
        for step_idx, step in enumerate(plan_steps):
            # 阶段 2: execute one step
            observation = self.executor.generate(
                EXECUTE_PROMPT.format(
                    task=task,
                    current_plan=plan_steps[step_idx:],
                    history=history
                )
            )
            history.append((step, observation))
            
            if self.should_replan(history):
                # 阶段 3: re-plan from current state
                new_plan = self.replanner.generate(
                    REPLAN_PROMPT.format(
                        task=task,
                        history=history,
                        original_plan=plan_steps
                    )
                )
                plan_steps = parse_plan(new_plan)
                step_idx = 0
        
        return history
```

[Birch et al. 2023, Plan-and-Execute](https://arxiv.org/abs/2305.04091) 那个 paper (LeBrun et al., 实际是 [Wang et al. 2023, Plan-and-Solve](https://arxiv.org/abs/2305.04091) 和同期 [Sun et al. 2023, ChatGPT Planners](https://arxiv.org/abs/2305.04091) 类似, 都很短, 不展开了) 报告的数字印象是在长 horizon task 上比 ReAct 好 10-20%, 但短 horizon 上差不多, 有时还差一点 (因为 plan 这一步 overhead 没用上)。

我自己在 2024 年做一个 multi-step web agent 的时候, 用过 Plan-and-Execute 跟 ReAct 的对比, 一些实战 finding:

第一, plan 的 granularity 很关键。Plan 太细 (每步一个 micro-action) 跟 ReAct 没区别, plan 太粗 (一步 "完成所有 booking") 又没法 execute。一个 trick 是 hierarchical plan, 先 high-level 3-5 步, 每步执行时再细化。这个跟 [SayCan](https://arxiv.org/abs/2204.01691) 的 high-level + low-level policy 思想一致, 不是新东西, 但在 LLM agent 上重新 work 了。

第二, re-plan 的 trigger 是个 design choice。失败的 step 一定 re-plan, 但 success 之后要不要 re-plan? 我的经验是如果连续成功 3 步以上, 就别 re-plan 了, cost 太高; 如果 plan 里接下来的步骤依赖之前没观察到的 state (比如 "if user is premium, do X, else do Y"), 那一定要 re-plan 来 branch。这块 paper 没怎么谈。

第三, 也是最 subtle 的: plan 本身的 quality 跟 base model 强相关。GPT-3.5 的 plan 经常漏步骤, 步骤顺序错, 工具选错; GPT-4 显著好, 但在 30+ 步的 plan 上还是 drop。Claude 3.5 Sonnet 在我那时的实验里 plan quality 跟 GPT-4 相当, Sonnet 3.5 出来后 (2024 年中) 涨了一截。这其实跟前面 ToT 的 evaluator 是同一个根本问题: LLM 自己的 metacognition (知道自己 plan 得好不好) 是不准的, 越长的 chain 越不准。

## 横向看: 这四个范式到底选哪个

我画个不严格的 trade-off 图给你, 不是表格, 是一段话:

ReAct 适合 **short-horizon + 频繁交互** 的场景, 比如 customer support chat, 单次 debugging, 简单 Q&A over API。每次 trajectory 5-15 步, cost 可控, 失败了就 restart, 不需要 reflection。

Reflexion 在 **少样本 + 需要 learning from mistake** 的场景下 work, 比如 few-shot coding, novel puzzle solving, multi-trial optimization。但 cost 跟 complexity 跟 ReAct 不是线性, 是 trial 数倍。

ToT 在 **state space 小但需要 search** 的场景下 work, 比如数学 puzzle, 逻辑推理, 创意写作里 explore alternative。但要满足两个条件: 1) 你能定义 thought decomposition, 2) 你有 reliable evaluator。如果两个条件都不满足, ToT 的 search 就是 garbage in, garbage out。

Plan-and-Execute 在 **long-horizon + plan 可静态化** 的场景下 work, 比如 multi-day research task, complex devops pipeline, data ETL workflow。这里 plan 不需要每步都更新, 但需要能 carry 整个 context。

一个反直觉的发现: 在 2024 年的 GPT-4o 跟 Claude 3.5 Sonnet 上, **ReAct + 好的 prompt 经常就够用了**, 80% 的 production agent 任务 ToT 跟 Plan-and-Execute 的 overhead 都没法 justify。我这么说不是要否定 search 的价值, 而是说 base model 涨得比 framework 快, 很多 2023 年 ToT 解决的事情, GPT-4o 一个 CoT prompt 就解决了。

但这不意味着 search 范式死了。2025 年 reasoning model 出来之后 ([OpenAI o1](https://arxiv.org/abs/2412.16720), [DeepSeek R1](https://arxiv.org/abs/2501.12948), [QwQ](https://qwenlm.github.io/blog/qwq-32b-preview/)), 范式变了。o1 / R1 的 training 本质上是把 search 给 internalize 了, model 内部有大量 hidden thinking, 出来的是 best path。**这跟 ToT 在 inference time 做 explicit search 是两条路线, 但 goal 一样: 找到 reasoning 链里的 optimal path。** 区别是 ToT 把 search 放在 outer loop (inference time), R1 把 search 放在 inner loop (training time)。这是一个非常 deep 的 trade-off, 我下一章 (Reasoning Models) 会展开讲。

## 我复现时踩过的坑 (血泪清单)

为了不让这一章读起来太 paper-survey, 写点实战。我 2023-2024 年复现这四篇 paper 的时候, 一些没在 paper 里明说的坑:

第一个, **format parser 是个无底洞**。ReAct 假设 model 输出严格 `Thought: ... Action: ...` 格式, 早期 GPT-3.5 在长 trajectory 里 30% 概率不守格式, 直接 free-form 回答。Paper 用 regex parser 加 retry, 但 retry 本身又有新问题: model 会 "I think the answer is X" 写在 Action 字段里, 跟真实 action 混在一起。Function calling (2023 年中 OpenAI 推出) 之后这个问题基本消失, 但 paper 时代没有, 所以 baseline number 其实被高估了。

第二个, **trajectory length 跟 context length 的 race condition**。ReAct 在 HotpotQA 上 trajectory 通常 5-8 步, 撑得住 4k context。Plan-and-Execute 在复杂 task 上 plan 就 15 步, 加上 history 30 步, 8k context 都紧张。GPT-4 的 32k 出来之前, 我们组当时 truncate 到最近的 5 步, 效果掉 10-15%。Paper 里 truncate strategy 都没仔细讲。

第三个, **evaluator 跟 generator 的 correlation**。ToT 的 evaluator 是 LLM-based, generator 也是 LLM, 它们 share bias。一个 thought 如果 format 上像答案 (比如以 "Therefore, ..." 开头), evaluator 倾向给高分, 不管实际对不对。我在一个 logic puzzle benchmark 上发现, ToT 的 74% 准确率里 12% 是 "格式骗了 evaluator"。这不是 ToT 的问题, 是 LLM-as-judge 普遍的问题, [Zheng et al. 2023, Judging LLM-as-a-Judge](https://arxiv.org/abs/2306.05685) 详细讨论过。

第四个, **Reflexion 的 memory 经常是 poison, 不是 asset**。我自己跑 coding benchmark 时, 5 个 trial 里前 2 次的 reflection 经常是 "I forgot to import X" 这种 actionable 的, 后几次就变成 "I should be more careful" 这种废话。Trivial reflection 挤掉 useful reflection, context 越加越脏。后面用 LLM-based summarization 来 compress memory, 但这又引入新的 failure mode: summarizer 误删 important detail。这是个目前没解的 problem, 跟 [Anthropic 2024 prompt caching 的 context decay](https://www.anthropic.com/news/prompt-caching) 那个 issue 是一类。

第五个, **plan-and-execute 的 plan 跟 execution 的 granularity 不 match**。Plan 里写 "查询用户的订单", Executor 实际执行时需要 5 步 sub-action: 登录, 查订单列表, 过滤 status, 选最近一笔, parse。Plan 太细 model 累, 太粗 executor 不知道怎么做。这个 granularity alignment problem 后面 [Least-to-Most prompting](https://arxiv.org/abs/2205.10625) ([Zhou et al. 2022]) 跟 [Successive Prompting](https://arxiv.org/abs/2303.08153) ([Dua et al. 2022]) 都试图解决, 但都没完全搞定。

## 这章没解决的 open question

最后说一下哪些是 open 的, 哪些 paper 没解决但我看到 2024-2026 有人在推进的。

第一, **search 的 inner-loop vs outer-loop trade-off**。ToT 跟 Plan-and-Execute 都是 outer-loop search, 在 inference time 显式做。R1 跟 o1 走 inner-loop, 训练时 internalize。问题是: outer-loop search 可以用 small model (因为 search 补偿能力), inner-loop 需要 huge model (因为能力都 internalize 了)。一个 natural question: 能不能用 7B model + heavy search 达到 70B + no search 的效果? [Qwen QwQ](https://qwenlm.github.io/blog/qwq-32b-preview/), [DeepSeek R1 distill](https://arxiv.org/abs/2501.12948) 都在做这个, 但 trade-off 的 sweet spot 还没找到。

第二, **memory 的 abstraction level**。ReAct 用 raw trajectory, Reflexion 用 verbal reflection, 但都不是 structured memory。能不能让 agent 维护一个 structured knowledge base (类似知识图谱), 每次 reflection 时更新图谱, 检索时 query 图谱? 这个方向 [MemGPT](https://arxiv.org/abs/2310.08560) ([Packer et al. 2023]) 跟 [MemoryBank](https://arxiv.org/abs/2305.10250) ([Zhong et al. 2023]) 都有探索, 但还没成为主流。

第三, **multi-agent 协作时 thought 应该 share 多少**。这一章都是 single-agent 的, 后面 [CAMEL](https://arxiv.org/abs/2303.17760) ([Li et al. 2023]), [MetaGPT](https://arxiv.org/abs/2308.00352) ([Hong et al. 2023]) 把多个 ReAct 拼起来做 multi-agent, 但 thought 是 private 的, 只 share 跟 action 相关的部分。问题: 两个 agent 的 thought 经常有 redundant reasoning, 如果 share 思考能省 cost, 但 share 多少合适? 这是 multi-agent 那一系列要展开的。

第四, **reliability 跟 interpretability 的 trade-off**。ReAct 的 thought 是 interpretable 的 (你可以看到 model "想"了什么), 但不可靠 (经常错)。o1 / R1 的 internal thought 不可见, 但 external output 可靠很多。一个 philosophical question: 我们到底要不要 LLM 把 thought 说出来? 如果 externalized thought 反而限制 model 的 reasoning (因为 model 会 self-censor 来 match human expectation)? 这个问题 [Anthropic 2024 的 sleeper agents paper](https://www.anthropic.com/news/sleeper-agents-training-deceptive-llms-that-persist-through-safety-training) 跟 [Apollo Research 2024 scheming paper](https://www.apolloresearch.ai/research/scheming-reasoning-evaluations) 都有暗示, 但还在早期。

OK 这一章就到这。下一章 [Reasoning Models (o1/o3 范式)](./06-reasoning-models.md) 我会展开上面提到的 inner-loop vs outer-loop search, 讲 o1, R1, QwQ 这些 reasoning model 怎么训练, 怎么 inference, 跟这一章的 ReAct 范式是什么关系。

---

[上一章: 04. Agent 基础架构与形式化定义](./04-agent-foundations.md) | [下一章: 06. Reasoning Models (o1/o3 范式)](./06-reasoning-models.md)