"""
04-orchestration-patterns / 04_swarm.py

模式 4: Swarm（蜂群）
Agent 之间动态交接，去中心化。
用 OpenAI Swarm 实现。

安装：
    pip install git+https://github.com/openai/swarm.git

运行：
    export OPENAI_API_KEY=sk-xxx
    python 04_swarm.py
"""
from swarm import Agent, Swarm


# ============================================================
# 3 个 Agent，每个可以交接给其他 Agent
# ============================================================
def handoff_to_writer():
    """交接给写作员的函数"""
    return writer


def handoff_to_reviewer():
    """交接给评审员的函数"""
    return reviewer


researcher = Agent(
    name="研究员",
    instructions="你是研究员，做完调研后调用 handoff_to_writer 把任务交给写作员。",
    functions=[handoff_to_writer],
)

writer = Agent(
    name="写作员",
    instructions="你是写作员，写完后调用 handoff_to_reviewer 把任务交给评审员。",
    functions=[handoff_to_reviewer],
)

reviewer = Agent(
    name="评审员",
    instructions="你是评审员，给出最终评审意见。不再交接。",
)


# ============================================================
# Swarm 客户端
# ============================================================
client = Swarm()


# ============================================================
# 演示
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Swarm 模式：Agent 之间动态交接")
    print("=" * 60)

    response = client.run(
        agent=researcher,
        messages=[{"role": "user", "content": "调研 Multi-Agent 系统，写一篇 100 字短文，然后评审。"}],
    )

    print("\n=== 交接链路 ===")
    for msg in response.messages:
        print(f"[{msg.get('role', '?')}] {msg.get('content', '')[:200]}")

    print(f"\n=== 最终 Agent: {response.agent.name} ===")