"""
03-five-abstractions / 04_memory.py

Memory 抽象演示：短期 / 长期 / 共享 3 种记忆的对比。

运行：
    export OPENAI_API_KEY=sk-xxx
    python 04_memory.py
"""
from crewai import Agent, Crew, Task


# ============================================================
# 短期记忆：默认就有（对话历史）
# ============================================================
short_term_agent = Agent(
    role="助手",
    goal="回答用户问题，记住当前会话的内容",
    backstory="你能记住当前对话的所有内容。",
    allow_delegation=False,
)


# ============================================================
# 长期记忆：跨会话保留
# ============================================================
# CrewAI 的 memory=True 会自动用向量数据库（默认 ChromaDB）保存
# 用户的偏好、历史问题等
long_term_agent = Agent(
    role="个性化助手",
    goal="记住用户的偏好和历史问题",
    backstory="你能记住跨会话的信息。",
    memory=True,  # ← 启用长期记忆
    allow_delegation=False,
)


# ============================================================
# 共享记忆：多个 Agent 共享的状态
# ============================================================
researcher = Agent(
    role="研究员",
    goal="调研 {topic}，输出事实到共享状态",
    backstory=(
        "你只做调研。"
        "你的输出会自动进入共享状态，下游 Agent 可以看到。"
    ),
    allow_delegation=False,
)

writer = Agent(
    role="写作员",
    goal="基于共享状态里的事实写作",
    backstory=(
        "你会读到上游 Agent 的输出（在共享状态里）。"
        "严格基于事实，不引入未经验证的内容。"
    ),
    allow_delegation=False,
)

research_task = Task(
    description="调研 {topic} 的 3 个关键事实",
    expected_output="3 条事实",
    agent=researcher,
)

write_task = Task(
    description="基于共享的事实写 100 字短文",
    expected_output="100 字短文",
    agent=writer,
    context=[research_task],  # ← 这一行就是"共享记忆"的实现
)


# ============================================================
# 演示：3 种记忆的实际使用
# ============================================================
if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "shared"

    if mode == "short":
        # 短期记忆 demo
        print("=" * 60)
        print("短期记忆：当前会话")
        print("=" * 60)
        crew = Crew(
            agents=[short_term_agent],
            tasks=[
                Task(description="我叫张三", expected_output="记住", agent=short_term_agent),
                Task(description="我叫什么？", expected_output="你的名字", agent=short_term_agent),
            ],
            verbose=True,
        )
        crew.kickoff()

    elif mode == "long":
        # 长期记忆 demo
        print("=" * 60)
        print("长期记忆：跨会话")
        print("=" * 60)
        crew = Crew(
            agents=[long_term_agent],
            tasks=[
                Task(description="我喜欢 Python", expected_output="记住", agent=long_term_agent),
            ],
            verbose=True,
        )
        crew.kickoff()
        print("\n再次跑这个脚本，问'我喜欢什么'，Agent 能记住。")

    elif mode == "shared":
        # 共享记忆 demo
        print("=" * 60)
        print("共享记忆：多 Agent 状态共享")
        print("=" * 60)
        crew = Crew(
            agents=[researcher, writer],
            tasks=[research_task, write_task],
            verbose=True,
        )
        result = crew.kickoff(inputs={"topic": "Multi-Agent 系统"})
        print("\n=== 最终输出 ===")
        print(result)
        print("\n注意 Researcher 的输出通过 context=[research_task] 自动传给 Writer")

    else:
        print(f"未知模式: {mode}")
        print("用法: python 04_memory.py [short|long|shared]")