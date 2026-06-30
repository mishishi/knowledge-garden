# 评测: Agent 怎么打分

第一次在生产环境跑 agent,我盯着后台的调用日志发呆了很久。任务成功率 92%,看起来很漂亮。但点开 fail 的那 8%,我发现一个严重的问题: 一个客服 agent 把"我要退款"理解成了"我要换货",然后一步一步帮用户换完了,任务流程全部走通,工具调用全部成功,但用户最后打电话来骂街。

传统 NLP 评测那套,几乎完全失效了。

后面两年我一直在想这个问题——agent 到底怎么打分? 这件事跟我们做文本分类、做 QA 的评分,根本不是一回事。文本分类看输出对不对,QA 看答案对不对,agent 看什么? 看它怎么走过去的。每一步调用、每一次决策、每一个上下文状态,都可能让最终结果偏离。

这一章我想聊的是: 我们 2024-2026 这两年,agent 评测这套东西是怎么从一片空白演化到现在的样子的,工程师实际能用的方法和工具,以及我在多个项目里踩过的坑。

## 从 "答对了" 到 "走对了" 的范式转移

传统评测的核心问题是: 它假设模型是一个函数,输入 → 输出,打分就是比输出。但 agent 不是函数。Agent 是一个会自己规划、调用工具、读结果、再规划的循环体。你给它一个"帮我查下明天北京到上海的航班",它可能调了 5 次航班 API、中间走错一次重新规划、最后告诉你正确的结果;也可能调了 3 次 API,一气呵成给你同样正确的答案。两者用户体验几乎一样,但内部轨迹天差地别。

更麻烦的是,有些任务根本没有标准答案。客服场景下"我该怎么办"有 10 种合理回答;代码 agent 写出来的代码只要能跑过测试就行,但实现路径千差万别。这意味着 final-answer 准确率这个指标,在 agent 评测里被严重稀释了。

我自己早期犯过一个错误: 用 GPT-4 当 judge,只看最终答案对不对,给我们的一个内部 RAG agent 打分。结果分数一直在 0.85 左右,我还以为稳了。后来手工抽查 fail case,发现 30% 的"答对"其实是模型猜对了关键词,推理过程完全是胡说八道。这玩意儿上线肯定翻车。

所以 agent 评测必须转向三个新维度: 过程(轨迹)、能力(工具调用成功率、规划质量)、结果(任务完成度)。这三者不是替代关系,是互补的。

轨迹相关的指标,业界 2024 年开始普遍用几个具体的度量。一个是 tool call precision/recall——预测要调的工具,实际正确率多少。另一个是 trajectory optimality——实际走的步骤数和最优步骤数的比值,这个比值越接近 1 越好。还有 trajectory robustness——同样的任务换种说法,agent 走的路径是否稳定。

工具调用成功率这块,我们一般拆成两层。第一层是 schema-level: 参数对不对、工具名字有没有拼错、必填字段填没填。第二层是 semantic-level: 调用的语义意图对不对。比如用户问"查天气",agent 调用了 `get_weather(city="上海")`,虽然 schema 完全正确,但如果用户当时定位在北京,这就是语义错误。

任务完成度是最难的部分。我个人经验是,要么用人工标注(贵但准),要么用 LLM-as-judge 但要严格设计 prompt,要么用 deterministic check(能写就尽量写)。我们组当时做了一个内部工具叫 task-completion-evaluator,核心逻辑是让 LLM 根据任务描述和最终输出,判断"这个任务是否被完成",返回 0-1 的分数加上 reasoning。Prompt 写了几十个版本,最后稳定在:

```python
completion_prompt = """
你是任务完成度评估专家。给定原始任务和 agent 的最终输出,判断任务是否被完成。

评估标准:
1. 任务的所有明确要求是否被满足
2. 输出是否解决了用户的核心问题
3. 如果任务有隐含要求(如时效性、准确性),是否被满足

输出 JSON:
{
  "score": 0.0-1.0,
  "completed": true/false,
  "reasoning": "具体说明为什么给这个分数"
}

任务: {task}
Agent 最终输出: {output}
"""
```

这套打分一开始很烂,因为 LLM 倾向于"温柔打分"——什么都给 0.7-0.9。后来我们加了 calibration: 每次评测混入 20% 的人工标注样本作为 anchor,如果 judge 在 anchor 上的偏差超过阈值,就触发 prompt 重新校准。这套机制上线后,judge 的稳定性从 ±0.15 降到了 ±0.05。

## 工具与平台: 2024-2026 的演进

2024 年初的时候,这块基本是空白。我们当时想跑 agent 评测,只能自己写脚本,调 OpenAI API,自己解析 log。那时候最痛苦的是 trajectory 的可视化——agent 跑完一轮,你看到的只是一堆 JSON,你得自己写代码把步骤拆开看。

2024 年中 LangSmith 出来,稍微缓解了一点。它能记录每次 run 的完整轨迹,包括每一步的输入输出、token 用量、延迟。UI 也做得不错,可以拖时间轴看每一步发生了什么。但它的问题是: 评测能力很弱,只能跑简单的 correctness check,做不了复杂的轨迹分析。

2024 年底到 2025 年初,这块开始爆发。几个值得关注的方向:

第一个是 Braintrust 这类专门做 LLM 评测的平台开始支持 agent 场景。它们的核心能力是把 trajectory 当成一等公民,允许你在轨迹的任意节点插入评估函数。比如你可以单独评估"第 3 步的工具调用是否合理"或者"第 5 步到第 8 步之间有没有冗余"。

第二个是学术界开始出 benchmark。最有名的是 τ-bench (tau-bench),Stanford 和 Sierra 联合做的,模拟真实客服场景,测试 agent 的多轮对话和工具调用能力。SWE-bench 也被扩展成了 SWE-bench Multimodal 和 SWE-agent 专用版本,评估 agent 在真实 GitHub issue 上的修复能力。还有 GAIA、HLE 这些通用 agent benchmark。

第三个是 Anthropic 和 OpenAI 自己开始放评测工具。Anthropic 的 Claude 在 2024 年底开放了一些 internal eval 的最佳实践,包括 trajectory grading 的具体做法。OpenAI 的 evals 平台也开始支持 multi-step task 的评估。

我自己 2025 年跑得最多的是 LangSmith + 自研脚本的组合。LangSmith 负责跑和记录,自研脚本负责评分。代码大致长这样:

```python
from langsmith import Client
from langsmith.evaluation import evaluate

client = Client()

# 定义轨迹评分函数
def trajectory_evaluator(run, example):
    trajectory = run.outputs.get("trajectory", [])
    
    # 1. 工具调用准确率
    expected_tools = example.outputs.get("expected_tools", [])
    actual_tools = [step["tool"] for step in trajectory if "tool" in step]
    tool_precision = len(set(expected_tools) & set(actual_tools)) / len(actual_tools) if actual_tools else 0
    
    # 2. 步骤效率
    optimal_steps = example.outputs.get("optimal_steps", len(trajectory))
    step_efficiency = optimal_steps / len(trajectory) if trajectory else 0
    
    # 3. 任务完成度 (用 LLM judge)
    completion = llm_judge(run.outputs.get("final_answer"), example.outputs.get("reference"))
    
    return {
        "key": "trajectory_metrics",
        "score": (tool_precision + step_efficiency + completion) / 3,
        "details": {
            "tool_precision": tool_precision,
            "step_efficiency": step_efficiency,
            "completion": completion
        }
    }

# 跑评测
results = evaluate(
    lambda inputs: my_agent.run(inputs["task"]),
    data="agent-eval-dataset",
    evaluators=[trajectory_evaluator],
    experiment_prefix="agent-eval-v3"
)
```

这套流程的缺点是: 评分函数还是要自己写。LLM judge 的 prompt 也得自己调。如果你不想自己搞这些,Braintrust、LangSmith 的最新版本、Arize Phoenix 都能提供不同程度的开箱即用。

我个人对 2025 年下半年的判断是,agent 评测会进一步标准化。可能的演进方向: trajectory-level 的评估会有更标准的 schema(类似 OpenTelemetry 的 span 结构);工具调用成功率会成为 agent 的"基础体检指标",就像 latency 是服务的 SLA;任务完成度的 LLM judge 会有更成熟的 calibration 工具。

## 我踩过的坑: 评测指标的选择

讲几个真实场景,这些坑我在不同项目里都遇到过。

第一个坑: final-answer 准确率高的 agent,不一定好用。我们当时做了一个内部知识库 agent,final-answer 准确率 0.91,但用户反馈很差。原因是 agent 经常答非所问,但运气好蒙到了关键词,或者用户问 A 它答 B 但 B 里恰好有 A 的答案。改用 trajectory + task-completion 联合打分后,这个 agent 的真实质量评分只有 0.62。后来换了一个 reasoning 更稳的版本,虽然 final-answer 准确率掉到 0.86,但实际用户体验评分涨了 30%。

第二个坑: 工具调用成功率这个指标,会骗人。我们当时有一个 SQL agent,工具调用成功率 0.95(几乎从不调错工具),但生成 SQL 的质量很差——经常查错表、用错 join。最后这个 agent 上线后业务方抱怨"查出来数据不对"。后来我们拆出了 semantic-correctness 这个独立指标,才把问题暴露出来。工具调用成功率看的是"调没调对",不看你"调的内容对不对"。

第三个坑: trajectory optimality 容易过度优化。我们曾经为了让 agent 走"最优路径",在 prompt 里写了非常死板的步骤规定。结果 agent 在一些异常 case 上完全不会变通,反而把成功率从 0.88 降到了 0.79。后来我们意识到 trajectory optimality 应该作为诊断工具,不是优化目标——你用它来找出哪些 case 走了明显冗余的路径,然后针对性优化,而不是全局要求所有 case 都走最短路径。

第四个坑: benchmark 上的分数和生产分数的鸿沟。这个老生常谈了,但 agent 比 LLM 更严重。benchmark 通常是"单轮任务+明确指令",生产环境是"多轮对话+模糊需求+上下文噪音"。我们的一个 code agent 在 SWE-bench 上能解决 40% 的 issue,但在我们的内部 codebase 上只能解决 15%。原因是内部 codebase 有大量隐性的工程规范、依赖关系、历史包袱,benchmark 完全没覆盖。

第五个坑,也是最隐蔽的一个: 评测集本身的分布漂移。Agent 系统的输入分布会随时间变化——用户的使用习惯在变、新工具在加进来、API 在更新。你半年前构建的评测集,半年后可能严重失真。我们后来强制要求每季度 refresh 一次评测集,至少 30% 的样本要更新。这个工作很枯燥但不做不行。

## 实操建议: 给工程师的两个 actionable thing

聊了这么多评测的坑和方法,最后给两个我觉得最实在的建议。

第一个建议: 搭一个最小可用的 trajectory 记录系统,立刻开始记录,不要等完美的评测方案。

很多团队的问题是想清楚"怎么评测"才开始干活,结果想半年还没动手。其实 trajectory 记录这件事今天就可以做:

```python
import json
from datetime import datetime

class TrajectoryRecorder:
    def __init__(self, task_id):
        self.task_id = task_id
        self.steps = []
        self.start_time = datetime.now()
    
    def record_step(self, step_type, input_data, output_data, metadata=None):
        self.steps.append({
            "step_index": len(self.steps),
            "step_type": step_type,  # "llm_call" / "tool_call" / "reasoning"
            "timestamp": datetime.now().isoformat(),
            "input": input_data,
            "output": output_data,
            "metadata": metadata or {}
        })
    
    def save(self, final_answer=None):
        record = {
            "task_id": self.task_id,
            "start_time": self.start_time.isoformat(),
            "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
            "steps": self.steps,
            "final_answer": final_answer,
            "step_count": len(self.steps)
        }
        # 存到数据库或文件
        with open(f"trajectories/{self.task_id}.json", "w") as f:
            json.dump(record, f, indent=2)
        return record
```

每个 agent run 都留一份完整的轨迹数据,先不管怎么打分。这些数据是后面所有评测的基础——你能做轨迹分析、能训练 reward model、能做 case study、能复现 bug。没有轨迹数据,后面想做精细化评测就只能干瞪眼。

第二个建议: 评分体系要分层,不要追求一个总分。

我个人强烈不建议搞一个 "agent_quality_score" 这样的总分,因为它会掩盖问题。你应该至少分四层:

- 基础层(必须有): 任务完成度、工具调用成功率。这两个不达标,其他都是白扯。
- 效率层(强烈建议有): trajectory 长度、token 消耗、延迟。这些是成本的代理指标。
- 稳健性层(规模化后要有): 同样任务不同 prompt 的表现方差、异常输入下的行为稳定性。
- 体验层(可选,难做): 用户满意度、对话自然度。这个用 LLM judge 或者人工评测。

每一层独立看,出问题的时候能定位是哪一层在掉分。如果只搞一个总分,你会面对"分数从 0.78 掉到 0.72,为什么"这种无法回答的问题。

说白了,agent 评测这件事,2026 年还在快速演进。SWE-bench、τ-bench 这些 benchmark 在更新,LangSmith、Braintrust、Langfuse 这些平台在加功能,LLM judge 的能力也在涨。但底层逻辑没变: agent 是过程导向的系统,评测必须覆盖过程。一个 final-answer 准确率高的 agent,可能是个糟糕的 agent;一个 trajectory 清晰稳健的 agent,即使 final-answer 不完美,也更容易迭代到完美。

下一章我想聊聊 agent 的安全边界——评测告诉你 agent 表现怎么样,但怎么确保 agent 不越界、不被滥用、不在生产里干蠢事。这块比评测更棘手,也更关乎生死。链接我放在这里了 [安全 & 边界](./10-safety.md)。