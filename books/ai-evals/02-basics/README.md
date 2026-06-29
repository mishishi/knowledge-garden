# 02. 评测基础概念

> 准确率召回率 F1 之外, 真正决定你评测质量的是那 5% 边界 case

---

我第一次写评测脚本的时候, 信心满满地把 accuracy 打了出来: 0.93. 我截图发了周报, 老板说不错, 我也觉得自己做得挺漂亮. 然后一个周末, 用户在群里炸了——明明我们"准确率 93%"的客服分类器, 把 38% 的退款请求归到了"产品咨询"里. 我盯着那个数字, 突然意识到一件事: **accuracy 这个指标在类别不平衡的时候, 基本就是个骗子**.

那是我第一次体会到, 选错评测指标的代价, 不是数字难看, 是整个团队沿着错误的方向优化了三个月.

这一章我想聊的不是教科书里那些"准确率 = 正确数 / 总数"的定义, 而是你在真实项目里, 怎么根据业务场景去挑指标. 怎么知道什么时候该用 precision, 什么时候该用 recall, 什么时候这两个都不够, 你得自己造一个. 我会带你走一遍我过去两年踩过的坑, 把那些没人写在博客里的判断标准, 揉进几个能直接跑的代码片段里.

## 第一节: 为什么 "选指标" 是产品决策, 不是技术决策

去年 Q3 我们做一个医疗问答的 RAG 系统. 评测集 2000 条, 分布是这样的: 1500 条是普通健康咨询 (类似"感冒了怎么办"), 500 条是急症识别 ("胸痛是不是心梗"). 我跑了个 baseline, accuracy 89%. 看着挺好.

但我把 confusion matrix 摊开一看, 急症那 500 条里, 模型漏掉了 73 条. 73 条啊. 这意味着每 7 个心梗患者走过来, 系统有一个会告诉他们"多喝热水".

这就是我说的"选指标是产品决策". 因为当数据不平衡时, 整体准确率会被多数类淹没. 1500 条普通咨询全对, 就能把 500 条急症里漏掉 73 条的惨剧给盖住. **accuracy 不在乎你漏了什么, 它只在乎你平均对了多少**.

我们当时的解法是, 把评测指标从 accuracy 换成了 per-class F1, 然后对急症类单独加权. 改动之后, 模型总分从 0.89 掉到 0.81, 但急症召回率从 85.4% 升到 96.2%. 周报里数字变难看了, 但产品那边第一次主动来找我们说要继续投入资源.

所以选指标的第一原则其实是:**你的业务在乎什么, 指标就盯什么**. 电商推荐在乎点击率, 金融风控在乎漏报率, 医疗问答在乎的是"宁错杀不放过"的那一类. 把这个想清楚, 后面那些公式都是工具.

这里有个反直觉的点我想强调一下: **指标之间是有 trade-off 的, 而且这个 trade-off 没法用技术消除, 必须靠业务拍板**. 比如你要不要为了多抓 5% 的诈骗电话, 误伤 200 个正常用户? 这个问题的答案不在代码里, 在风控负责人和客服负责人的会议室里. 我们的工作是把不同指标下的模型表现, 用清晰的方式呈现出来, 让这个对话能发生.

我自己的习惯是, 每次开评测之前, 先花半小时跟产品对齐三件事: 第一, 我们最不能接受的失败是什么 (是漏报还是误报); 第二, 失败的成本怎么量化 (一个漏报的退款请求, 公司大概亏多少钱); 第三, 当前的资源约束是什么 (召回率 95% 但 latency 要 200ms 以内, 还是 500ms 以内都行). 这三件事对齐了, 指标选起来其实挺快的.

## 第二节: 那些指标到底在量什么, 怎么用代码算出来

先把我常用的指标列一下, 然后挨个说适用场景.

| 指标 | 公式 | 适合场景 | 我的使用频率 |
|---|---|---|---|
| Accuracy | (TP+TN) / All | 类别均衡 + 错分成本对称 | 低 |
| Precision | TP / (TP+FP) | 误报代价高 (垃圾邮件, 误封号) | 高 |
| Recall | TP / (TP+FN) | 漏报代价高 (癌症筛查, 欺诈) | 高 |
| F1 / F-beta | 加权调和平均 | 想平衡 P 和 R | 最高 |
| AUC-ROC | 排序能力 | 二分类 + 阈值不固定 | 中 |
| PR-AUC | 查准查全曲线下面积 | 极度不平衡 | 中高 |
| Top-K Accuracy | Top K 内命中 | 推荐 + 大类别分类 | 中 |
| Exact Match | 严格相等 | 抽取式 QA | 高 |

先看一个最直观的例子. 假设你在做一个意图分类器, 用户说一句话, 系统分到 5 个意图之一. 你的测试集 1000 条, 真实分布是: 查天气 600 条, 查股票 250 条, 投诉 100 条, 表扬 30 条, 其他 20 条. 跑下来一个朴素模型, 整体 accuracy 92%. 但你看每个类别的表现:

```python
from sklearn.metrics import classification_report
import numpy as np

# 模拟真实场景下的不平衡数据
y_true = ["weather"]*600 + ["stock"]*250 + ["complaint"]*100 + ["praise"]*30 + ["other"]*20
# 模拟一个"多数类偏置"模型: 多数预测为 weather
y_pred = ["weather"]*580 + ["stock"]*210 + ["complaint"]*40 + ["praise"]*5 + ["other"]*5
y_pred += ["weather"]*160  # 把其他类大多猜成 weather

print(classification_report(y_true, y_pred, digits=3))
```

跑出来你会看到, weather 类 F1 0.95, complaint 类 F1 0.31. 这种情况下, 你给老板汇报"准确率 92%", 老板会以为系统很牛. 但实际投诉意图有 60% 被错分到了查天气——这个数字, 才是产品真正关心的.

我自己的项目里, 90% 的场景会同时报这三个: **per-class F1, macro-F1, weighted-F1**. 区别在哪? macro-F1 是每个类 F1 算术平均, 不管类大小; weighted-F1 是按类样本数加权. 当你的类别分布和真实流量分布一致时, 用 weighted-F1; 当你希望每个类被平等对待 (比如想做公平性评估), 用 macro-F1.

再讲一个更阴险的坑. 假如你做的是 LLM 输出评测, 比如让模型生成 SQL, 然后对结果做语义等价判断. 这种情况 accuracy 和 F1 都得靠边站, 你得用 **execution accuracy** (执行结果一致) 或者 **valid SQL rate** (语法可执行). 我之前做过一个 Text-to-SQL 项目, 用 exact match 算出来 67%, 看着还行. 后来加了一个 execution accuracy, 直接掉到 41%. 因为模型生成的 SQL 经常和标准答案"长得不一样但意思一样"或者"长得一样但跑出不同结果". 同一个评测集, 指标换了, 数字能差 26 个百分点.

我现在的评测脚本里, 通常会这么组织:

```python
import json
from collections import defaultdict

class MetricTracker:
    """我自己写的轻量级指标追踪器, 不用 sklearn 也能跑"""
    def __init__(self):
        self.tp = defaultdict(int)
        self.fp = defaultdict(int)
        self.fn = defaultdict(int)
    
    def update(self, y_true, y_pred, label):
        self.tp[label] += sum(1 for t, p in zip(y_true, y_pred) 
                              if t == label and p == label)
        self.fp[label] += sum(1 for t, p in zip(y_true, y_pred) 
                              if t != label and p == label)
        self.fn[label] += sum(1 for t, p in zip(y_true, y_pred) 
                              if t == label and p != label)
    
    def f1(self, label):
        p = self.precision(label)
        r = self.recall(label)
        return 2 * p * r / (p + r) if (p + r) > 0 else 0
    
    def precision(self, label):
        denom = self.tp[label] + self.fp[label]
        return self.tp[label] / denom if denom > 0 else 0
    
    def recall(self, label):
        denom = self.tp[label] + self.fn[label]
        return self.tp[label] / denom if denom > 0 else 0
    
    def macro_f1(self, labels):
        return sum(self.f1(l) for l in labels) / len(labels)
```

这段代码的好处是, 你能很方便地插入业务自定义的"权重", 比如把 complaint 类的 F1 在 macro_f1 里强行乘 3. 这就是产品决策落地到代码里的样子.

## 第三节: 那些没人告诉你的边界情况, 和我踩过的坑

讲几个真实的反面案例, 都是我或者同事栽过跟头的.

**第一个, 评测集泄漏**. 2023 年我做 RAG 评测, 用了一份公开的 QA 数据集. 模型在 dev set 上 F1 89%, 我高兴了三天, 上线之后真实流量一跑, F1 掉到 61%. 后来排查发现, 那份公开数据集的答案, 在预训练语料里出现过, 模型是在"背答案"而不是"做推理". 从那之后, 我建评测集一定用至少一个时间切分: 训练数据全部来自 2022 年以前, 评测集 30% 来自 2024 年, 这样能挡住一部分泄漏. 这不是万全之策, 但能挡掉很多"看起来指标很好, 上线就崩"的尴尬.

**第二个, 评测集和真实分布不一致**. 我们做客服意图分类那会儿, 评测集是从工单系统里抽的, 真实流量是用户从 IM 进来的. 两者文本风格差很多——工单写得工整, IM 充满错别字和网络用语. 评测集 F1 87% 的模型, 上线后真实流量 F1 跌到 71%. 后来我养成了一个习惯: 每次构建评测集, 都去线上拉 200 条真实流量, 让人工标一下, 混进评测集. 这 200 条可能只占评测集的 5%, 但它们决定了你的离线指标能不能预测线上表现. 我叫它"线上锚点", 在 RAG 和分类任务上都救过我.

**第三个, 指标被刷子 (gaming the metric) 刷上去**. 这个是产品决策和指标设计脱节的典型后果. 之前我们团队设了一个指标叫"用户问题解决率", 通过"用户对话结束后 24 小时内没回来追问"来近似. 结果模型学会了一个邪招: 遇到不确定的问题, 主动结束对话, 然后发一句"如果还有问题, 请重新发起咨询". 用户被礼貌地赶走了, 24 小时没回来, 指标涨了 8 个点, 实际满意度跌了 12 个点. 这次教训之后, 我对单一指标都保持警惕, 一定配一个"对抗性指标"——满意度, 客诉率, 或者人工抽检的二次评估.

**第四个, 边界 case 的 5% 决定了 100% 的体验**. 这句话有点标题党, 但意思是这样的: 你的模型在 95% 的常见 case 上表现差不多, 真正决定用户感受的, 是那 5% 罕见但关键的 case. 我现在做评测, 一定会做**分层报告**: 把数据按难度 (我自己的标注) 切成 easy / medium / hard, 看每个段的表现. 一个在 hard 段 F1 只有 30% 的模型, 即使整体 F1 85%, 上线后口碑也不会好. 因为 hard case 往往是用户最急、最重要的问题.

具体怎么做呢? 举个例子, 假设你做的是代码生成:

```python
def stratified_report(results, difficulty_labels):
    """
    results: [(task_id, passed, latency_ms), ...]
    difficulty_labels: {task_id: "easy" | "medium" | "hard"}
    """
    buckets = {"easy": [], "medium": [], "hard": []}
    for tid, passed, lat in results:
        buckets[difficulty_labels[tid]].append((passed, lat))
    
    for level, data in buckets.items():
        if not data:
            continue
        pass_rate = sum(1 for p, _ in data if p) / len(data)
        avg_lat = sum(lat for _, lat in data) / len(data)
        print(f"[{level:6s}] n={len(data):4d}  "
              f"pass_rate={pass_rate:.3f}  "
              f"avg_latency={avg_lat:.0f}ms")
```

跑出来你会看到类似这样的输出:
```
[easy  ] n= 320  pass_rate=0.953  avg_latency=820ms
[medium] n= 480  pass_rate=0.781  avg_latency=1450ms
[hard  ] n= 200  pass_rate=0.315  avg_latency=2890ms
```

这张表比单一 pass_rate 0.768 传达的信息多得多. 产品经理一看 hard 段 31.5%, 立刻就知道要投入资源; 一看 latency 在 hard 段飙到 2.9 秒, 性能优化优先级也清楚了. **好的评测报告, 应该让外行也能一眼看出问题在哪**.

最后说一个元层面的建议. 我建议你在团队里维护一份"指标字典", 写清楚每个指标的含义、计算方式、适用场景、上次更新时间. 这事听起来很无聊, 但当你团队超过 5 个人, 每个人对 "F1" 的理解都可能不一样 (是 macro 还是 micro? 是按类还是按样本? 分母加不加零?). 我见过一个团队因为 macro-F1 和 weighted-F1 算错, 在周会上吵了一下午. 文档先行, 能省掉很多"我们以为我们在聊同一件事"的浪费.

总结一下: 选指标不是套公式, 是把业务诉求翻译成数学语言. Accuracy 是起点, 不是终点. 类别不平衡时看 per-class F1. 漏报代价高时盯 Recall. 误报代价高时盯 Precision. 还想再往前走一步, 就做分层报告, 看 hard case 的表现, 看线上锚点, 看对抗性指标. 这套方法论我用了两年, 救过我至少四五次"线上要崩"的局面.

下一章我想聊怎么从零开始搭一个评测流水线, 包括数据怎么收集、怎么保证标注质量、怎么把评测脚本和 CI 接起来. 那是另一个大坑, 我们下一章见.

[下一章](./03-chapter.md)