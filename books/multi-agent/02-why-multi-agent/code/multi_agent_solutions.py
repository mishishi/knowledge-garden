"""
02-why-multi-agent / multi_agent_solutions.py

演示 Multi-Agent 如何解决单 Agent 的 3 个局限。
对比 single_agent_problems.py 看，每个场景的解法都更干净。

运行：
    export OPENAI_API_KEY=sk-xxx
    python multi_agent_solutions.py
"""
import sys

from crewai import Agent, Crew, Task


# ============================================================
# 场景 1 解法：上下文爆炸
# ============================================================
# 拆分：Reader / Analyzer / Coder / Tester
# 每个 Agent 只做一件事，context 干净
def build_scenario_1_crew():
    reader = Agent(
        role="文件读取员",
        goal="读取 5 个文件并提取关键 API 列表",
        backstory="你只负责读文件并提取 API（函数签名 + 1 行说明），输出简洁列表。",
        allow_delegation=False,
    )

    analyzer = Agent(
        role="方案分析员",
        goal="基于 API 列表设计修改方案",
        backstory="你只设计修改方案，不执行修改。",
        allow_delegation=False,
    )

    coder = Agent(
        role="编码员",
        goal="执行代码修改",
        backstory="你只负责执行 edit_file，不做其他事。",
        allow_delegation=False,
    )

    tester = Agent(
        role="测试员",
        goal="跑测试验证",
        backstory="你只跑 pytest 并报告结果。",
        allow_delegation=False,
    )

    t1 = Task(
        description="读取 5 个文件，输出 API 列表",
        expected_output="API 列表（每条一行）",
        agent=reader,
    )
    t2 = Task(
        description="基于 API 列表设计修改方案",
        expected_output="修改方案（伪代码）",
        agent=analyzer,
        context=[t1],
    )
    t3 = Task(
        description="执行修改",
        expected_output="修改后的代码",
        agent=coder,
        context=[t2],
    )
    t4 = Task(
        description="跑测试",
        expected_output="测试结果（通过/失败）",
        agent=tester,
        context=[t3],
    )

    return Crew(agents=[reader, analyzer, coder, tester], tasks=[t1, t2, t3, t4], verbose=True)


# ============================================================
# 场景 2 解法：角色冲突
# ============================================================
# 拆分：Researcher（深调研）/ Writer（好表达）
def build_scenario_2_crew():
    researcher = Agent(
        role="研究员",
        goal="深入调研 3 个框架的事实",
        backstory="你只做研究。深度优先，每条事实要有数据支撑。",
        allow_delegation=False,
    )

    writer = Agent(
        role="写作员",
        goal="基于事实写流畅推荐文",
        backstory="你只做表达。基于事实，不引入未经验证的内容。",
        allow_delegation=False,
    )

    t1 = Task(
        description="调研 2026 年 3 个 Python Web 框架，每个框架输出 3 条关键事实",
        expected_output="3 个框架 × 3 条事实的列表",
        agent=researcher,
    )
    t2 = Task(
        description="基于事实写 1000 字推荐文",
        expected_output="1000 字推荐文",
        agent=writer,
        context=[t1],
    )

    return Crew(agents=[researcher, writer], tasks=[t1, t2], verbose=True)


# ============================================================
# 场景 3 解法：可调试
# ============================================================
# 同样拆分：Researcher / Writer
# 但关键差别：每个 Agent 的输出可独立检查
def build_scenario_3_crew():
    researcher = Agent(
        role="研究员",
        goal="调研 3 个框架的事实",
        backstory="你只做研究，输出事实列表。",
        allow_delegation=False,
    )

    writer = Agent(
        role="写作员",
        goal="基于事实写推荐文",
        backstory="你必须严格基于研究员的事实写作，禁止编造。",
        allow_delegation=False,
    )

    t1 = Task(
        description="调研 3 个 Python Web 框架，每个输出 3 条事实",
        expected_output="事实列表",
        agent=researcher,
    )
    t2 = Task(
        description="基于事实写 1000 字推荐文",
        expected_output="推荐文",
        agent=writer,
        context=[t1],
    )

    return Crew(agents=[researcher, writer], tasks=[t1, t2], verbose=True)


if __name__ == "__main__":
    scenario = sys.argv[1] if len(sys.argv) > 1 else "2"

    if scenario == "1":
        crew = build_scenario_1_crew()
        result = crew.kickoff()
        print("\n=== 4 个 Agent 顺序执行完毕 ===")
        print(result)
        print("\n=== 对比 single_agent 的好处 ===")
        print("1. 每个 Agent 的 backstory 只有 30 字，prompt 干净")
        print("2. context 自动隔离（不会全堆在一起）")
        print("3. 失败可定位：是 Reader 读错了？还是 Analyzer 方案错了？还是 Coder 改错了？")

    elif scenario == "2":
        crew = build_scenario_2_crew()
        result = crew.kickoff()
        print("\n=== Researcher + Writer 协作完成 ===")
        print(result)
        print("\n=== 对比 single_agent 的好处 ===")
        print("1. Researcher 输出深度事实，Writer 输出流畅表达，互不干扰")
        print("2. 两个 backstory 都聚焦一件事，prompt 干净")
        print("3. 角色单一 → 深度足")

    elif scenario == "3":
        crew = build_scenario_3_crew()
        result = crew.kickoff()
        print("\n=== 输出 ===")
        print(result)
        print("\n=== 调试技巧 ===")
        print("如果推荐文错了（比如推荐 Flask 但事实里没列 Flask），")
        print("看 verbose 输出，定位是 Researcher 没调研还是 Writer 没引用。")
        print("CrewAI verbose=True 会打印每个 Agent 的中间输出，可以 step into。")

    else:
        print(f"未知场景: {scenario}")
        print("用法: python multi_agent_solutions.py [1|2|3]")