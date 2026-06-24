"""
03-five-abstractions / 05_handoff.py

Handoff 抽象演示：3 种交接模式（顺序 / 条件 / 并行）。

运行：
    export OPENAI_API_KEY=sk-xxx
    python 05_handoff.py
"""
from crewai import Agent, Crew, Task


# ============================================================
# 模式 A：顺序交接（Pipeline）
# ============================================================
# A → B → C
# 最简单，每个 Agent 完成后传给下一个
def pipeline_handoff():
    a = Agent(role="研究员", goal="调研 {topic}", backstory="只做调研", allow_delegation=False)
    b = Agent(role="分析员", goal="基于调研分析", backstory="只做分析", allow_delegation=False)
    c = Agent(role="写作员", goal="基于分析写作", backstory="只做写作", allow_delegation=False)

    t1 = Task(description="调研 {topic} 3 条事实", expected_output="3 条事实", agent=a)
    t2 = Task(description="分析事实", expected_output="分析结果", agent=b, context=[t1])
    t3 = Task(description="写 100 字短文", expected_output="短文", agent=c, context=[t2])

    return Crew(agents=[a, b, c], tasks=[t1, t2, t3], verbose=True)


# ============================================================
# 模式 B：条件交接（Conditional）
# ============================================================
#     ┌─ 紧急 → 加急处理
# A ──┤
#     └─ 普通 → 普通处理
#
# CrewAI 实现条件交接需要借助 router Agent
def conditional_handoff():
    classifier = Agent(
        role="分类员",
        goal="判断 {request} 是紧急还是普通",
        backstory="你只做分类，输出 'urgent' 或 'normal'。",
        allow_delegation=False,
    )

    urgent_handler = Agent(
        role="加急处理员",
        goal="加急处理请求",
        backstory="你只处理紧急请求。",
        allow_delegation=False,
    )

    normal_handler = Agent(
        role="普通处理员",
        goal="普通处理请求",
        backstory="你只处理普通请求。",
        allow_delegation=False,
    )

    t_classify = Task(
        description="判断 {request} 是紧急还是普通",
        expected_output="一行: 'urgent' 或 'normal'",
        agent=classifier,
    )

    t_handle = Task(
        description="基于分类结果处理 {request}",
        expected_output="处理结果",
        agent=urgent_handler,  # 默认走 urgent
        context=[t_classify],
    )

    # CrewAI 的限制：条件路由需要 LangGraph 实现更直观
    # 这里用两个 task 演示：classifier 输出决定后续 Agent 的选择
    # 实际生产用 LangGraph 的 add_conditional_edges 更清晰

    return Crew(agents=[classifier, urgent_handler, normal_handler], tasks=[t_classify, t_handle], verbose=True)


# ============================================================
# 模式 C：并行交接（Parallel / Broadcast）
# ============================================================
#     ┌─ B（架构评审）
# A ───┼─ C（性能评审）
#     └─ D（安全评审）
#
# 一个 Agent 的输出同时给多个 Agent
def parallel_handoff():
    reader = Agent(
        role="代码读取员",
        goal="读取 diff 并提取关键信息",
        backstory="只做读取，输出结构化信息。",
        allow_delegation=False,
    )

    arch_reviewer = Agent(
        role="架构评审",
        goal="基于 diff 评审架构",
        backstory="你只评审架构层面。",
        allow_delegation=False,
    )

    perf_reviewer = Agent(
        role="性能评审",
        goal="基于 diff 评审性能",
        backstory="你只评审性能层面。",
        allow_delegation=False,
    )

    sec_reviewer = Agent(
        role="安全评审",
        goal="基于 diff 评审安全",
        backstory="你只评审安全层面。",
        allow_delegation=False,
    )

    t_read = Task(
        description="读取 diff 并提取关键信息",
        expected_output="diff 摘要",
        agent=reader,
    )

    # 关键：async_execution=True 让 task 可以并行
    t_arch = Task(
        description="评审架构",
        expected_output="架构评审意见",
        agent=arch_reviewer,
        context=[t_read],
        async_execution=True,  # ← 关键：异步执行
    )

    t_perf = Task(
        description="评审性能",
        expected_output="性能评审意见",
        agent=perf_reviewer,
        context=[t_read],
        async_execution=True,
    )

    t_sec = Task(
        description="评审安全",
        expected_output="安全评审意见",
        agent=sec_reviewer,
        context=[t_read],
        async_execution=True,
    )

    # Lead 汇总
    lead = Agent(role="主评审", goal="汇总 3 份评审", backstory="你汇总输出最终报告。", allow_delegation=False)
    t_lead = Task(
        description="汇总 3 份评审",
        expected_output="最终评审报告",
        agent=lead,
        context=[t_arch, t_perf, t_sec],
    )

    return Crew(
        agents=[reader, arch_reviewer, perf_reviewer, sec_reviewer, lead],
        tasks=[t_read, t_arch, t_perf, t_sec, t_lead],
        verbose=True,
    )


# ============================================================
# 演示
# ============================================================
if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "pipeline"

    if mode == "pipeline":
        print("=" * 60)
        print("模式 A: 顺序交接 (Pipeline)")
        print("=" * 60)
        result = pipeline_handoff().kickoff(inputs={"topic": "Multi-Agent"})
        print(result)
        print("\nA → B → C 顺序执行")

    elif mode == "conditional":
        print("=" * 60)
        print("模式 B: 条件交接 (Conditional)")
        print("=" * 60)
        print("注意：CrewAI 条件路由不如 LangGraph 直观")
        print("生产推荐用 LangGraph 的 add_conditional_edges")
        result = conditional_handoff().kickoff(inputs={"request": "服务器挂了"})
        print(result)

    elif mode == "parallel":
        print("=" * 60)
        print("模式 C: 并行交接 (Parallel)")
        print("=" * 60)
        result = parallel_handoff().kickoff()
        print(result)
        print("\n3 个 Reviewer 并行执行，Lead 汇总")

    else:
        print(f"未知模式: {mode}")
        print("用法: python 05_handoff.py [pipeline|conditional|parallel]")