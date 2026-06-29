# 09. 实战案例剖析

> 把一个真实 AI 项目从零做到上线的全部取舍摊在桌上

我记得第一次给别人做 AI 项目复盘的时候，听众里有个工程师直接举手问：「你说的『模型效果不错』到底是多少？」我愣了三秒。当时我以为「不错」是个形容词，落在数字上才发现它根本站不住脚。三个月后我做的内部 PPT 改成「意图识别 F1 从 0.71 升到 0.89，幻觉率从 12% 降到 1.8%，P95 延迟从 1.4s 压到 420ms」，台下再没人追问。这章要写的就是这种程度的具体：一个从零到上线的 AI 项目，每一步我都标了数字和报错信息，不是为了好看，是为了让下次你遇到差不多的问题时，能少走一段弯路。

项目本身不复杂——一个面向 SaaS 客户的智能工单分类系统，要把客服每天涌进来的 4000+ 工单自动分成 23 个业务类目，然后路由到对应团队。听起来很标准对吧？但凡做过的人都知道，「标准」这两个字在 AI 项目里是个诅咒。我会用三节讲完它：第一节先把场景和立项时的几个真实分歧摆出来；第二节贴两段真正跑在生产环境里的核心代码；第三节写那些让整个团队熬到凌晨三点的坑和最后沉淀下来的经验。

## 立项那周我们吵了什么

项目冷启动是在去年九月。客服团队把诉求写在了一张 A4 纸上，第一条是「每天节省 2 小时人工分单时间」，第二条是「分错类的不许超过 3%」。业务方代表拍着桌子说「我们不要 ChatGPT 那种大模型，太贵，我们只要一个分类器」。我当时的反驳很直接：分类器遇到「我付了钱但收不到货」这种明显是物流问题、却混了 8 个产品线关键词的句子，规则系统会死，大模型反而一句话搞定。会议室里僵了四十分钟，最后双方各退一步——做一个混合方案：先用一个小模型做主干分类，置信度低于 0.78 的兜底给大模型，预算上限是单次推理 ¥0.008。

但分歧不止这一处。第二周我们围绕「评测集怎么造」又开了一次会。我坚持认为评测集必须全部来自真实历史工单，不能用 LLM 生成。原因是 LLM 生成的样本会带有它自己的偏见——你拿 GPT-4 生成工单，再用 GPT-4 去分类，那评测结果就是个回音壁。会议结论是：从过去 6 个月的历史工单里抽样 8000 条做种子集，再用主动学习的方式从线上捞难例补充。主动学习的代码我放在下一节。

第三周还吵过一次，这次是关于「评测指标」。产品经理说「我们看准确率就行」，我差点把咖啡泼到屏幕上。23 个类目里 5 个长尾类目（每个不到 200 条样本）准确率会被大头类目淹没，对长尾类目单独看 F1 才有意义。争吵的结果是上线了一个「分层指标看板」，长尾类目任何一个 F1 低于 0.75 就触发告警。这个看板后来救了我们两次——一次是「账户安全问题」从 F1 0.81 掉到 0.62，一次是「发票与税务」从 0.79 掉到 0.71。两次都和上游一个内部知识库迁移有关，那又是另一段血泪了。

还有一件事我必须提到，因为它影响了我后来所有项目的早期决策。我们在 day 0 就建了一个「failure bank」——一个共享文档，团队任何人碰到模型分错的例子就往里丢，按「沉默错误」「客户投诉」「潜在风险」三档归类。这个文档到上线那天积累了 612 条样本，其中 137 条直接变成了 v2 模型的训练数据。花的时间呢？每天 15 分钟。回报呢？我只能说，CEO 在周会上说「这个项目上线比预期顺利」时，我心里是有数的。

## 两段真在生产里跑过的代码

下面这段是主动学习的循环。当时我的设计目标是：每周一早上系统自动跑一次，从上周线上收到的工单里挑出 200 条「模型最没把握」的，扔到标注平台让人标，标完直接进训练集。这套机制跑了 7 周，把模型 F1 从 0.71 推到 0.89。

```python
# active_loop.py
# 每周一凌晨 2 点跑的主动学习采样任务
import json
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

# 1) 从线上数据库捞过去 7 天的工单
engine = create_engine("postgresql://eval_user:***@prod-db/ai_eval")
sql = text("""
    SELECT id, text, model_pred, model_conf
    FROM inference_log
    WHERE created_at >= :since AND created_at < :until
""")
since = (datetime.utcnow() - timedelta(days=7)).isoformat()
until = datetime.utcnow().isoformat()
rows = engine.execute(sql, since=since, until=until).fetchall()
print(f"拉到了 {len(rows)} 条线上样本")

# 2) 按熵排序，挑最没把握的 200 条
def entropy(p):
    p = np.clip(p, 1e-9, 1)
    return -np.sum(p * np.log(p))

candidates = []
for r in rows:
    # model_conf 是 softmax 后的概率分布，已经 JSON 化存库
    probs = np.array(json.loads(r.model_conf))
    e = entropy(probs)
    # 过滤掉 top-1 概率 > 0.95 的，太确定了
    if probs.max() < 0.95:
        candidates.append((r.id, r.text, e, probs.tolist()))

candidates.sort(key=lambda x: -x[2])  # 熵高的排前面
top_pick = candidates[:200]

# 3) 推送到 Label Studio 标注队列
import requests
for cid, text_, ent, probs in top_pick:
    requests.post("http://label-studio/api/tasks", json={
        "data": {"text": text_, "entropy": ent, "probs": probs},
        "project": 7,  # 工单分类项目 ID
    }, headers={"Authorization": "Token xxx"})
print(f"已推送 {len(top_pick)} 条到标注平台")
```

跑这套循环的过程中我们发现一个反直觉的现象：每周推 200 条标注，但其中真正「对模型提升大」的只有 40 条左右——剩下 160 条是「看起来不确定，其实原因只是文本里出现了生僻词」这种噪声。我们后来加了一层预过滤，要求熵高的同时 top-2 概率之差小于 0.15，才推标注。这一改，标注效率提升了 3.2x，原来一周要标 200 条，现在每周 60 条就够。

下面这段是评测系统里最关键的一环：分层指标的收集。我之前在别的项目里栽过跟头——只看总体 F1，等到客户投诉了才发现在某个长尾类目上模型已经崩了。这段代码会把每次模型推理的结果按类目归档，存到时序数据库里，供 Grafana 拉取画图。

```python
# stratified_eval.py
# 每次模型批量推理后跑一次，统计分层指标
import json
from collections import defaultdict
from sklearn.metrics import f1_score, precision_recall_fscore_support

def collect_predictions(inference_results, ground_truth=None):
    """
    inference_results: [{"text":..., "pred": "账户安全", "conf": 0.91}, ...]
    ground_truth: {"id_123": "账户安全", ...}  可选，有标注时才算 F1
    """
    bucket_pred = defaultdict(list)
    bucket_true = defaultdict(list)

    for item in inference_results:
        pred = item["pred"]
        if ground_truth and item["id"] in ground_truth:
            true = ground_truth[item["id"]]
            bucket_pred[true].append(pred)
            bucket_true[true].append(true)

    report = {}
    for cls in sorted(set(ground_truth.values()) if ground_truth else []):
        y_true = bucket_true[cls]
        y_pred = bucket_pred[cls]
        if len(y_true) < 5:  # 样本太少，F1 不稳
            report[cls] = {"status": "insufficient", "n": len(y_true)}
            continue
        p, r, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, labels=[cls], average="binary", zero_division=0
        )
        report[cls] = {
            "precision": round(float(p), 4),
            "recall": round(float(r), 4),
            "f1": round(float(f1), 4),
            "n": len(y_true),
            "status": "alert" if f1 < 0.75 else "ok",
        }
    return report

# 实际接入：每 6 小时跑一次
if __name__ == "__main__":
    with open("/var/log/ai/inference_6h.jsonl") as f:
        results = [json.loads(l) for l in f]
    with open("/opt/ai/data/labeled_sample_2k.json") as f:
        gt = json.load(f)
    report = collect_predictions(results, gt)
    # 推送告警
    for cls, m in report.items():
        if m["status"] == "alert":
            send_slack_alert(channel="#ai-eval-alert",
                             text=f"类目 [{cls}] F1={m['f1']} 触发告警")
```

这段代码看着朴素，但踩过的坑有：第一版我没加 `zero_division=0`，结果有一个长尾类目某一轮全错，F1 算出来是 `nan`，Grafana 上一片空白页，监控系统以为「指标正常」。第二版我加了 `zero_division=0`，结果所有长尾类目一全错就 F1=0，开始疯狂告警，告警疲劳了一周。第三版才定下现在的「样本少于 5 条就标 insufficient，不参与告警」这个规则，告警才安静下来。

## 我们栽过的跟头和沉淀下来的判断

我得先说最疼的那次：上线第三周，我们接到一封客户邮件，语气很冲，说「你们把我『我想取消订阅』分到了『账户安全』里，害我多等了 6 小时才有人联系我」。当时我整个人是懵的，立刻去翻 failure bank，发现这条工单的文本是「我密码忘了想取消订阅」。模型一看到「密码忘了」就锚定到了「账户安全」类目，置信度 0.83。但人类看一眼就知道这是「订阅管理」。这就是典型的「关键词陷阱」——bag-of-words 类模型对强信号的偏好。

我们的解法不是改模型，是改了 prompt——给模型的输入里强制加了一行「请先判断客户的最终意图，而不是被中间提到的细节带偏」。这一行字让这个具体案例的分类从 0.83 的错误置信度直接降到了 0.41，让兜底机制接管，路由到「订阅管理」团队。改一行字，省了 6 小时人工，0 训练成本。

第二个坑是评测集的时间漂移。第 1 周我们用 6 月数据造评测集，到了第 8 周，模型在 6 月评测集上 F1 还是 0.89，但客户投诉率明显上升。把评测集换成 9 月数据，F1 直接掉到 0.74。原因是 9 月电商大促，「发货」「物流」类目涌进了大量之前没出现过的句式。从那以后我定了一个铁律：评测集每月必须刷新 20%，而且这部分必须从最近 30 天线上捞，不许用历史数据凑数。

第三个坑是上线切流的策略。我们第一版切流是「灰度 5% → 20% → 50% → 100%」，每一档跑 24 小时。结果在 50% 这一档，模型在一个长尾类目上 F1 从 0.78 掉到 0.61，我们花了 3 天定位原因——上游一个内部 API 返回格式变了，把「退款」类目的关键特征字符串给吃掉了。回滚之后我们重写了切流策略：每一档必须分层看指标，长尾类目单独监控，且任何长尾类目 F1 跌幅超过 0.1 立即全量回滚，不再等 24 小时。改完之后再没出过类似事故。

还有几个小但很折磨的细节我列一下：一是别相信模型自己写的解释，理由上面提过的回音壁效应；二是评测集要保留「金标 + 银标」两套，金标人审，银标 LLM 标，用来跑高频回归和月度深度回归；三是延迟预算要分 P50 和 P95 两套，主流用户卡 P50，长尾用户卡 P95，我们项目最后压到 P50 180ms / P95 420ms，超时率 0.3%。四是任何「准确率 99%」的承诺别写进合同，AI 项目里这种数字迟早会变。

最后我想说一个不那么技术的判断：复盘会上大家最喜欢问「下次能不能少花点时间」，我的回答是不能。少花时间的方法只有一个——别在生产里学东西。但生产里学东西恰恰是 AI 项目最值钱的环节。我们这个项目前后花了 11 周，其中 6 周是在生产里迭代。这 6 周的学费交了 612 条 failure、3 次切流事故、2 次长尾告警。换来的是模型 F1 0.71 → 0.89，幻觉率 12% → 1.8%，单次推理成本从 ¥0.012 降到 ¥0.0043，每年给公司省下大概 47 秒 × 4000 工单 × 300 天的人工等待时间。

把这些数字写在 PPT 上的时候，我又一次意识到：当你能把一个项目的结果折算成「每年 1,560 小时人工时间」的时候，任何一句「模型效果不错」都不再值得说出口。

[下一章](./10-chapter.md)