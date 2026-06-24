"""
05-state-and-communication / 02_pass_by_value.py

Pass-by-Value：A 的输出作为 B 的输入
用 CrewAI 的 context=[] 实现。

运行：
    export OPENAI_API_KEY=sk-xxx
    python 02_pass_by_value.py
"""
from crewai import Agent, Crew, Task


researcher = Agent(
    role="研究员",
    goal="调研 {topic}",
    backstory="只做调研，输出 3 条事实。",
    allow_delegation=False,
)

writer = Agent(
    role="写作员",
    goal="基于上游事实写作",
    backstory="基于上游 Agent 的输出写作，不引入新事实。",
    allow_delegation=False,
)

reviewer = Agent(
    role="评审员",
    goal="基于上游文章评审",
    backstory="基于写作员的输出评审。",
    allow_delegation=False,
)

# ============================================================
# Pass-by-Value：A → B → C
# ============================================================
t1 = Task(description="调研 {topic} 的 3 个关键事实", expected_output="3 条事实", agent=researcher)
t2 = Task(
    description="基于事实写 100 字短文",
    expected_output="100 字短文",
    agent=writer,
    context=[t1],  # ← Pass-by-Value：t1 的输出自动注入 t2 的 input
)
t3 = Task(
    description="评审短文",
    expected_output="评审意见",
    agent=reviewer,
    context=[t2],  # ← t2 的输出注入 t3
)

crew = Crew(agents=[researcher, writer, reviewer], tasks=[t1, t2, t3], verbose=True)


# ============================================================
# 对比：不传 context 会怎样？
# ============================================================
writer_no_context = Agent(
    role="写作员（无 context）",
    goal="写 100 字短文",
    backstory="你没有任何上游信息，只能凭印象写。",
    allow_delegation=False,
)

t_no_context = Task(
    description="写 100 字短文介绍 {topic}",
    expected_output="100 字短文",
    agent=writer_no_context,
    # ← 没有 context=[]，writer 完全不知道 researcher 调研了什么
)

crew_no_context = Crew(agents=[writer_no_context], tasks=[t_no_context], verbose=True)


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "with"

    if mode == "with":
        print("=" * 60)
        print("Pass-by-Value: 3 个 Agent 顺序传值")
        print("=" * 60)
        result = crew.kickoff(inputs={"topic": "Multi-Agent"})
        print(result)
        print("\nWriter 看到 Researcher 的事实，Reviewer 看到 Writer 的文章")

    elif mode == "without":
        print("=" * 60)
        print("无 Pass-by-Value: Writer 不知道 Researcher 调研了什么")
        print("=" * 60)
        result = crew_no_context.kickoff(inputs={"topic": "Multi-Agent"})
        print(result)
        print("\nWriter 凭印象写 → 内容可能与事实不一致")

    else:
        print(f"未知模式: {mode}")
        print("用法: python 02_pass_by_value.py [with|without]")