"""
04-orchestration-patterns / 01_pipeline.py

模式 1: Pipeline（流水线）
A → B → C，顺序执行，最简单。

运行：
    export OPENAI_API_KEY=sk-xxx
    python 01_pipeline.py
"""
from crewai import Agent, Crew, Task

# ============================================================
# 4 步 Pipeline：读代码 → 分析 → 改 → 测试
# ============================================================
reader = Agent(
    role="代码读取员",
    goal="读取 3 个文件并输出内容摘要",
    backstory="你只读取和摘要，不做任何分析。",
    allow_delegation=False,
)

analyzer = Agent(
    role="分析员",
    goal="基于摘要分析代码结构",
    backstory="你只做结构分析，不输出修改方案。",
    allow_delegation=False,
)

coder = Agent(
    role="编码员",
    goal="基于分析输出修改代码",
    backstory="你只输出代码，不做解释。",
    allow_delegation=False,
)

tester = Agent(
    role="测试员",
    goal="基于代码输出测试用例",
    backstory="你只输出 pytest 测试代码。",
    allow_delegation=False,
)

t1 = Task(description="读取 3 个文件并摘要", expected_output="3 个文件摘要", agent=reader)
t2 = Task(description="分析代码结构", expected_output="结构分析", agent=analyzer, context=[t1])
t3 = Task(description="输出修改代码", expected_output="修改后的代码", agent=coder, context=[t2])
t4 = Task(description="输出测试用例", expected_output="pytest 测试代码", agent=tester, context=[t3])

crew = Crew(agents=[reader, analyzer, coder, tester], tasks=[t1, t2, t3, t4], verbose=True)


if __name__ == "__main__":
    result = crew.kickoff()
    print("\n=== Pipeline 完成 ===")
    print(result)