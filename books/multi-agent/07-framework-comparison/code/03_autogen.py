"""
07-framework-comparison / 03_autogen.py

AutoGen 实现：3 个 Agent 轮流发言

安装：
    pip install autogen-agentchat~=0.4

运行：
    export OPENAI_API_KEY=sk-xxx
    python 03_autogen.py
"""
import asyncio

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.teams import RoundRobinGroupChat


researcher = AssistantAgent(
    name="researcher",
    model_client="gpt-4o-mini",
    system_message="你是研究员，调研 topic，输出 3 条关键事实。",
)

writer = AssistantAgent(
    name="writer",
    model_client="gpt-4o-mini",
    system_message="你是写作员，基于事实写 100 字短文。",
)

reviewer = AssistantAgent(
    name="reviewer",
    model_client="gpt-4o-mini",
    system_message="你是评审员，评审文章。",
)

team = RoundRobinGroupChat(
    participants=[researcher, writer, reviewer],
    termination_condition=MaxMessageTermination(max_messages=6),
)


async def run():
    result = await team.run(task="调研 Multi-Agent 系统并写 100 字短文")

    print("\n=== 对话历史 ===")
    for msg in result.messages:
        print(f"\n[{msg.source}] {msg.content}")

    print("\n=== AutoGen 特点 ===")
    print("- 代码量：~25 行")
    print("- 调试：console 输出")
    print("- 适合：群聊模式 / 头脑风暴")


if __name__ == "__main__":
    asyncio.run(run())