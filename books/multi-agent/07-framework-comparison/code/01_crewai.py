"""
07-framework-comparison / 01_crewai.py

CrewAI 实现：调研 + 写作 + 评审

安装：
    pip install crewai

运行：
    export OPENAI_API_KEY=sk-xxx
    python 01_crewai.py
"""
from crewai import Agent, Crew, Task


researcher = Agent(
    role="研究员",
    goal="调研 {topic} 的关键事实",
    backstory="你只做调研，深度优先。",
    allow_delegation=False,
)

writer = Agent(
    role="写作员",
    goal="基于事实写 100 字短文",
    backstory="你只做表达。",
    allow_delegation=False,
)

reviewer = Agent(
    role="评审员",
    goal="评审文章质量",
    backstory="你只评审。",
    allow_delegation=False,
)

t1 = Task(description="调研 {topic} 的 3 个关键事实", expected_output="3 条事实", agent=researcher)
t2 = Task(description="基于事实写 100 字短文", expected_output="100 字短文", agent=writer, context=[t1])
t3 = Task(description="评审文章", expected_output="评审意见", agent=reviewer, context=[t2])

crew = Crew(agents=[researcher, writer, reviewer], tasks=[t1, t2, t3], verbose=True)


if __name__ == "__main__":
    result = crew.kickoff(inputs={"topic": "Multi-Agent 系统"})
    print("\n=== 最终输出 ===")
    print(result)
    print("\n=== CrewAI 特点 ===")
    print("- 代码量：~15 行")
    print("- 调试：verbose=True 看打印")
    print("- 适合：快速验证业务逻辑")