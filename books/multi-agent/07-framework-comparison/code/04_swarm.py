"""
07-framework-comparison / 04_swarm.py

OpenAI Swarm 实现：Agent 之间动态 handoff

安装：
    pip install git+https://github.com/openai/swarm.git

运行：
    export OPENAI_API_KEY=sk-xxx
    python 04_swarm.py
"""
from swarm import Agent, Swarm


def handoff_to_writer():
    return writer


def handoff_to_reviewer():
    return reviewer


researcher = Agent(
    name="researcher",
    instructions=(
        "你是研究员，做完调研后必须调用 handoff_to_writer。"
        "输出 3 条关键事实再交接。"
    ),
    functions=[handoff_to_writer],
)

writer = Agent(
    name="writer",
    instructions="你是写作员，写完 100 字短文后必须调用 handoff_to_reviewer。",
    functions=[handoff_to_reviewer],
)

reviewer = Agent(
    name="reviewer",
    instructions="你是评审员，给出最终评审意见，不再交接。",
)

client = Swarm()


if __name__ == "__main__":
    response = client.run(
        agent=researcher,
        messages=[{"role": "user", "content": "调研 Multi-Agent 系统，写 100 字短文，评审。"}],
    )

    print("\n=== 交接链路 ===")
    for msg in response.messages:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if content:
            print(f"[{role}] {content[:200]}")

    print(f"\n=== 最终 Agent: {response.agent.name} ===")
    print("\n=== Swarm 特点 ===")
    print("- 代码量：~20 行")
    print("- 调试：几乎无")
    print("- 适合：极简 demo，不建议生产")