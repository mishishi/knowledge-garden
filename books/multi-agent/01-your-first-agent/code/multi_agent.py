"""
01-your-first-agent / multi_agent.py

用 CrewAI 演示两个 Agent 协作：Researcher（调研）→ Writer（写作）。
这是 Multi-Agent 最简单的形式：两个角色，顺序执行。

运行：
    pip install -r requirements.txt
    export OPENAI_API_KEY=sk-xxx
    python multi_agent.py

为什么要拆成两个 Agent？看 single_agent.py 末尾的"单 Agent 的局限"。
"""
from crewai import Agent, Crew, Task


# ============================================================
# 1. 定义 Agent：研究员
# ============================================================
researcher = Agent(
    role="研究员",
    goal="调研 {topic} 的 3 个关键事实",
    backstory=(
        "你是一个专业研究员，擅长快速找到关键事实。"
        "你会直奔主题，言简意赅，每条事实不超过 30 字。"
    ),
    allow_delegation=False,  # 不允许把任务再委托给其他 Agent
    verbose=True,
)


# ============================================================
# 2. 定义 Agent：写作员
# ============================================================
writer = Agent(
    role="写作员",
    goal="基于研究员的事实，写一段 100 字以内的中文短文",
    backstory=(
        "你是一个技术写作员，文笔清晰，擅长把复杂概念讲简单。"
        "你只基于事实写作，不引入未经验证的内容。"
    ),
    allow_delegation=False,
    verbose=True,
)


# ============================================================
# 3. 定义任务
# ============================================================
research_task = Task(
    description="调研主题：{topic}。输出 3 条关键事实，每条不超过 30 字。",
    expected_output="3 条事实的列表，每条一行",
    agent=researcher,
)

write_task = Task(
    description=(
        "根据研究员提供的 3 条事实，写一段 100 字以内的中文短文介绍 {topic}。"
        "直接写正文，不要写'以下是...'这种开头。"
    ),
    expected_output="一段 100 字以内的中文短文",
    agent=writer,
    context=[research_task],  # 关键：写作任务依赖调研任务的输出
)


# ============================================================
# 4. 编排：让两个 Agent 顺序执行
# ============================================================
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    verbose=True,  # 打印每个 Agent 的中间思考过程
)


# ============================================================
# 5. 跑起来
# ============================================================
if __name__ == "__main__":
    result = crew.kickoff(inputs={"topic": "Multi-Agent AI 系统"})
    print("\n" + "=" * 60)
    print("=== 最终输出 ===")
    print("=" * 60)
    print(result)