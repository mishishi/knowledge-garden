# 03. 离线评测设计

> 数据集不是越大越好，而是越能"咬人"越好——一份 200 条的评测集救过我们三次。

去年十一月，我们给客服 Agent 做第一次大规模离线评测时，团队里有人拉了一份 12,000 条历史工单数据，跑了三天，得出结论：模型 A 比模型 B 准确率高 4.2%。我盯着那个数字看了很久，越看越不对劲。后来我抽样检查了 200 条，发现有 31 条标注本身就是错的——标注员把"用户骂人"标成了"用户咨询"，把"已退款"标成了"待处理"。4.2% 这个优势，小于标注噪声。

这事儿给我一个教训：离线评测的根基不是模型，是数据集。从那之后我们重构了评测流程，今天这一章把整套方法摊开讲。

## 第一节：为什么"做个测试集"比想象中难十倍

很多团队第一次做 AI Evals 的姿势是这样的：找一批人，每个人凭直觉写几十条 case，拼成一个 CSV，跑一次模型，得出一个数字，发邮件给老板，结束。我见过太多次了。

问题在于，"凭直觉写"这件事隐含了一个假设：写 case 的人知道模型会怎么错。实际操作中，写 case 的人往往想的是"正常用户会怎么问"，于是数据集全是 happy path——"我的快递到哪了""怎么修改收货地址"。等模型上线，真正出问题的全是边界 case：用户用方言骂人、用户截图发一半、用户同时问三个问题、用户假装自己是客服要退款。

我们后来统计过一组数字：纯直觉构建的 500 条数据集，上线后模型在上面的失败率是 1.2%，看着很漂亮；但同一批用户真实流量里，模型失败率是 14.8%。差了 12 倍。这就是离线评测和线上表现的鸿沟，我们叫它 "eval gap"。

怎么缩小这个 gap？三条经验。

第一条，**从线上失败案例反推数据集**。每周拉一次线上 bad case（用户差评、人工兜底、低评分会话），人工归类，连续四周你会看到 80% 的失败其实集中在 15-20 个 pattern 上。这 15-20 个 pattern 就是你数据集的骨架。我有个具体的例子：我们做医疗问答时发现，模型最大的雷区是"用户问禁忌症时模型没问清楚用药史"——这个 pattern 在我们最初的数据集里一条都没有，因为我们写数据集的人默认"用户会主动说"。但真实用户不会。

第二条，**每个分类至少有 30 条**。30 是个 magic number，少于这个数，统计显著性就没了——你分不清模型是真强还是运气好。我们后来把所有分类都按 30 条基线补齐，超出的再按重要性加权。

第三条，**保留 10% 的"对抗集"**。这些 case 不来自真实用户，而是评测工程师故意设计的刁钻问题，目的是给模型"下马威"。比如在客服场景里，我们故意写"如果我是你老板我就把客服全开除"这种带情绪诱导的输入，看模型会不会被带跑。这部分占比 10%-15%，效果比单纯堆量好得多。

数据集不是静态资产，是会"钝化"的工具。一个数据集用半年，模型对它就过拟合了——开发者会针对里面的 case 做 prompt 调优，分数虚高，但泛化没变。所以每季度要补一轮新 case，每年要做一次大重构。这是后话，先记着。

## 第二节：怎么搭一个能用的评测框架

讲理论太干，我直接上代码。我们用 Python 写一个最简版的离线评测框架，能跑通"读数据集 → 调模型 → 评分 → 出报告"全流程。先看核心结构：

```python
# eval_runner.py
# 离线评测最小可运行框架
import json
import asyncio
from dataclasses import dataclass, field
from typing import Callable, Awaitable

@dataclass
class EvalCase:
    """单条评测样本"""
    case_id: str
    input: str
    expected: str          # 期望输出（或参考输出）
    tags: list = field(default_factory=list)  # 分类标签
    difficulty: int = 1    # 1-5, 5 最难

@dataclass
class EvalResult:
    """单条评测结果"""
    case_id: str
    predicted: str
    score: float           # 0-1
    latency_ms: int
    error: str = ""

async def run_eval(
    cases: list[EvalCase],
    model_fn: Callable[[str], Awaitable[str]],
    judge_fn: Callable[[str, str], float],
    concurrency: int = 8,
) -> dict:
    """主评测函数，concurrency 控制并发避免打爆 API"""
    sem = asyncio.Semaphore(concurrency)
    results = []

    async def one(case: EvalCase):
        async with sem:
            t0 = time.perf_counter()
            try:
                pred = await model_fn(case.input)
                err = ""
            except Exception as e:
                pred = ""
                err = str(e)
            dt = int((time.perf_counter() - t0) * 1000)
            score = 0.0 if err else judge_fn(pred, case.expected)
            results.append(EvalResult(case.case_id, pred, score, dt, err))

    await asyncio.gather(*[one(c) for c in cases])

    # 按 tag 聚合
    by_tag = {}
    for r, c in zip(results, cases):
        for t in c.tags or ["_all"]:
            by_tag.setdefault(t, []).append(r.score)
    report = {
        tag: {"mean": sum(s)/len(s), "n": len(s)}
        for tag, s in by_tag.items()
    }
    return report
```

这个框架 60 行，但五脏俱全：并发控制用 `asyncio.Semaphore`，避免 500 条 case 同时打过去把 API 限流；按 tag 聚合分数，能看出模型在哪个分类上弱；`difficulty` 字段我们没在 runner 里用，但在分析时会单独看 4-5 分的 case 表现。

接下来是评分函数。这一块是评测的"心脏"，水也最深。我把 LLM-as-judge 和规则评分都封装了：

```python
# judge.py
# 评分模块：规则 + LLM-as-judge 混合策略
import re
from openai import AsyncOpenAI

client = AsyncOpenAI()

def exact_match(pred: str, expected: str) -> float:
    """严格匹配，适合事实型问答"""
    return 1.0 if pred.strip() == expected.strip() else 0.0

def contains_keywords(pred: str, expected: str) -> float:
    """检查 expected 中的关键事实是否被提到"""
    kws = re.findall(r"[\u4e00-\u9fa5]+|[A-Za-z]+", expected)
    if not kws:
        return 1.0
    hit = sum(1 for k in kws if k in pred)
    return hit / len(kws)

async def llm_judge(pred: str, expected: str, rubric: str) -> float:
    """LLM-as-judge，用于开放式回答"""
    prompt = f"""你是评分员，根据 rubric 给模型回答打分 0-1。
rubric: {rubric}
参考答案: {expected}
模型回答: {pred}
只输出一个 0-1 之间的小数，不要解释。"""
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    try:
        return float(resp.choices[0].message.content.strip())
    except ValueError:
        return 0.0

# 路由：哪种 case 用哪种评分
def make_judge(case: EvalCase):
    if "fact" in case.tags:
        return lambda p, e: exact_match(p, e)
    if "open" in case.tags:
        return lambda p, e: contains_keywords(p, e)
    # 默认用 LLM judge
    rubric = "回答是否准确、完整、无幻觉"
    return lambda p, e: llm_judge(p, e, rubric)
```

注意 `make_judge` 这个路由函数。不同类型的 case 用不同评分器，这一行决定了整个评测的可信度。我们踩过的坑是：早期所有 case 都用 LLM judge，结果发现 LLM judge 本身有偏好——它喜欢长回答、喜欢结构化输出、喜欢"看起来自信"的措辞，导致两个真实能力差不多的模型分数差出 8 个点。后来改成"事实类用 exact match，开放类用关键词覆盖率 + 偶尔 LLM judge"，分数方差立刻小了一半。

还有个小细节：`temperature=0` 一定要写。不写的话，同一条 case 跑两次可能给出不同分数，评测就没法复现。我们有次发现两次跑同一份数据集，分数差了 1.3 个点，排查了一上午，最后发现是 LLM judge 默认 temperature=0.7。

## 第三节：数据集规模、采样、和那些年我踩过的坑

聊几个具体数字。

**规模问题。**很多人问我"数据集到底要多大"，我的回答是：分阶段。MVP 阶段（验证方向）50-100 条够了；Beta 阶段（对比模型）300-500 条；上线守门（CI 必跑）1000-2000 条。再大边际收益递减，而且维护成本陡增。我们目前客服 Agent 的核心评测集是 1,800 条，跑了八个月，每条至少改了两次版本。

**采样问题。**线上 12,000 条历史工单不能直接用——里面 70% 是模板化的简单查询（"查物流""开发票"），20% 是重复 case，剩下 10% 才是真正有信号的。我写的采样脚本核心逻辑是：先按 intent 聚类，每个 cluster 最多取 5 条代表性 case，再人工补齐长尾 cluster。这一步把 12,000 条压到了 1,200 条，信号密度提升了 9 倍。

**标注一致性。**这是个隐形大坑。一条 case 三个标注员，Kappa 系数 0.6 以下，这份数据集就是废的。我们有过一次惨痛教训：一份 400 条的标注集，Kappa 只有 0.48，跑出来的分数和我们肉眼判断完全相反——模型明明答得更好看，分数却低。后来花了三周重新标注，所有人在标注前要过 50 条 calibration 集，Kappa 才爬到 0.81。**省下来的那 47 秒沟通时间，远抵不上重做的成本。**

**对抗集的设计哲学。**这一段单拎出来讲，因为太容易被忽略。对抗集不是"刁难"模型，是测模型在真实压力下的稳定性。我列几个我们用过的对抗 pattern：

- **格式诱导**：用 markdown 表格、emoji 列表、纯文本混排的输入
- **多意图混淆**：一条消息里塞三个问题，看模型能不能识别全部
- **情绪压力**：开篇就是"你们客服太烂了我要投诉"
- **语义模糊**：用代词指代不明确的内容
- **幻觉诱导**：直接问"请详细说明 XX 的副作用"（XX 是编造的药名）

最后一个最阴。我们发现模型在面对"看起来合理但事实不存在"的实体时，有 23% 的概率顺着用户的问法编造答案。这个问题在 happy path 数据集里完全测不出来，必须靠对抗集。

**版本管理。**数据集也是代码，要进 git。我们吃过亏：一版数据集跑出 87 分，三个月后再跑只有 79 分，查了一周发现是中间有人手动改了 23 条 case 但没记录。从此强制所有数据集变更走 PR + diff review + 锁版本（用 DVC 或简单的 JSON 快照 + hash）。

**最后讲一个边界情况：**当你的产品迭代速度远快于数据集更新速度时，离线评测的指导价值会断崖式下降。模型一周迭代三次，但数据集一个月才更新一次，评测分数和线上体感完全脱钩。这种情况怎么办？我们的解法是引入"金丝雀 case"——每周从线上抓 20-30 条最新 bad case，扔进数据集，保持新鲜感。这部分不进入正式评分，只作为"信号灯"。等积累到一定量，再正式 merge 进主集。

写到这里你应该感觉到了：离线评测不是"跑一次分"这么简单的动作，而是一整套数据工程。我把它压缩成一句话：**好数据集 = 真实失败模式的浓缩 + 对抗样本的覆盖 + 标注一致性的纪律 + 版本可追溯的工程习惯。**

掌握这些，你就有了判断"我该不该信这个评测结果"的能力。下一章我们聊怎么把这些离线结果和线上表现对齐——也就是 eval gap 的测量与校准。

[下一章](./04-chapter.md)