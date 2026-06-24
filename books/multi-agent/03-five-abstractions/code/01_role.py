"""
03-five-abstractions / 01_role.py

Role 抽象演示：同一个"调研 + 写文章"任务，
用 3 种不同的 Role 拆分方式，看哪种最清晰。

运行：
    export OPENAI_API_KEY=sk-xxx
    python 01_role.py
"""
from crewai import Agent, Crew, Task


# ============================================================
# 拆分方式 A：粗粒度（不推荐）
# ============================================================
def bad_split():
    """粗粒度拆分：只分两个 Role，但每个 Role 还是做多件事"""
    worker = Agent(
        role="内容生成器",
        goal="写一篇 1000 字的推荐文章",
        backstory=(
            "你要先调研 3 个 Python Web 框架的优缺点，"
            "然后基于调研写一篇流畅的中文推荐文章。"
            # ← 调研 + 写作 都在这一个 Role 里
            # 上一章场景 2 已经演示了这种拆法的问题
        ),
        allow_delegation=False,
    )

    task = Task(
        description="调研 3 个 Python Web 框架并写一篇 1000 字推荐文",
        expected_output="1000 字推荐文",
        agent=worker,
    )

    return Crew(agents=[worker], tasks=[task], verbose=True)


# ============================================================
# 拆分方式 B：细粒度（推荐）
# ============================================================
def good_split():
    """细粒度拆分：每个 Role 只做一件事"""
    researcher = Agent(
        role="研究员",
        goal="调研 {topic} 的关键事实",
        backstory="你只做调研，输出事实列表。深度优先。",
        allow_delegation=False,
    )

    writer = Agent(
        role="写作员",
        goal="基于事实写文章",
        backstory="你只做表达，不引入未经验证的内容。",
        allow_delegation=False,
    )

    t1 = Task(
        description="调研 {topic} 的 3 个关键事实",
        expected_output="3 条事实",
        agent=researcher,
    )

    t2 = Task(
        description="基于事实写 1000 字文章",
        expected_output="1000 字文章",
        agent=writer,
        context=[t1],
    )

    return Crew(agents=[researcher, writer], tasks=[t1, t2], verbose=True)


# ============================================================
# 拆分方式 C：过度拆分（反例）
# ============================================================
def over_split():
    """过度拆分：每个 Role 只做太细的子任务，反而失去意义"""
    fact_finder = Agent(
        role="事实查找员",
        goal="找到一个事实",
        backstory="你只找一个事实就停。",
    )

    fact_formatter = Agent(
        role="事实格式化员",
        goal="把事实格式化成列表",
        backstory="你只做格式化。",
    )

    # 这种拆分会让 Agent 之间通信成本 >> 工作本身
    # 结果：3 个事实需要 6 次 Agent 切换，token 翻 6 倍

    t1 = Task(description="找一个事实", agent=fact_finder, expected_output="1 条事实")
    t2 = Task(description="格式化事实", agent=fact_formatter, expected_output="格式化的事实", context=[t1])

    return Crew(agents=[fact_finder, fact_formatter], tasks=[t1, t2], verbose=True)


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "good"

    if mode == "bad":
        print("=" * 60)
        print("拆分方式 A: 粗粒度（不推荐）")
        print("=" * 60)
        result = bad_split().kickoff(inputs={"topic": "Python Web 框架"})
        print(result)

    elif mode == "good":
        print("=" * 60)
        print("拆分方式 B: 细粒度（推荐）")
        print("=" * 60)
        result = good_split().kickoff(inputs={"topic": "Python Web 框架"})
        print(result)

    elif mode == "over":
        print("=" * 60)
        print("拆分方式 C: 过度拆分（反例）")
        print("=" * 60)
        result = over_split().kickoff()
        print(result)
        print("\n注意 token 消耗：2 个 Agent + 6 次切换")

    else:
        print(f"未知模式: {mode}")
        print("用法: python 01_role.py [bad|good|over]")