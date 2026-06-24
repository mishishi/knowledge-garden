"""
03-five-abstractions / 02_goal.py

Goal 抽象演示：同一个任务用不同颗粒度的 Goal，看 LLM 输出的差别。

运行：
    export OPENAI_API_KEY=sk-xxx
    python 02_goal.py
"""
from crewai import Agent, Crew, Task


def make_crew(goal_text: str, expected_output: str):
    """构造一个相同 Role 但不同 Goal 的 Crew"""
    agent = Agent(
        role="研究员",
        goal=goal_text,
        backstory="你是一个专业研究员。",
        allow_delegation=False,
    )

    task = Task(
        description="调研主题：Multi-Agent 系统",
        expected_output=expected_output,
        agent=agent,
    )

    return Crew(agents=[agent], tasks=[task], verbose=True)


# ============================================================
# Goal 颗粒度对比
# ============================================================
if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "good"

    if mode == "bad":
        # 反模式 1：太宽
        print("=" * 60)
        print("Goal 反模式 1: 太宽（没法验证）")
        print("=" * 60)
        crew = make_crew(
            goal_text="帮助用户理解 Multi-Agent",
            expected_output="一段输出",
        )
        result = crew.kickoff()
        print(result)
        print("\n问题：'一段输出'没法验证，不知道算不算'帮助'")

    elif mode == "good":
        # 推荐：细粒度 + 可验证
        print("=" * 60)
        print("Goal 推荐写法: 细粒度 + 可验证")
        print("=" * 60)
        crew = make_crew(
            goal_text=(
                "调研 Multi-Agent 系统，输出 3 条关键事实，"
                "每条事实不超过 30 字，必须包含'通信'、'编排'、'工具' 3 个关键词"
            ),
            expected_output=(
                "3 行输出，每行包含一个关键词："
                "1. 通信: ... "
                "2. 编排: ... "
                "3. 工具: ..."
            ),
        )
        result = crew.kickoff()
        print(result)
        print("\n验证：3 行？每行 30 字内？包含 3 个关键词？能机械检查")

    elif mode == "contradict":
        # 反模式 2：矛盾
        print("=" * 60)
        print("Goal 反模式 2: 矛盾（目标互相打架）")
        print("=" * 60)
        crew = make_crew(
            goal_text=(
                "用 100 字以内的篇幅完整介绍 Multi-Agent 的 5 个核心抽象的所有细节，"
                "包含每个抽象的定义、对比、案例和踩坑"
            ),
            expected_output="100 字以内的完整介绍",
        )
        result = crew.kickoff()
        print(result)
        print("\n问题：100 字根本讲不完 5 个抽象的所有细节 → LLM 只能瞎取舍")

    else:
        print(f"未知模式: {mode}")
        print("用法: python 02_goal.py [bad|good|contradict]")