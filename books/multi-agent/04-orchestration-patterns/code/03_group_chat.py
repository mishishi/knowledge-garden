"""
04-orchestration-patterns / 03_group_chat.py

模式 3: GroupChat（群聊）
多个 Agent 自由讨论，谁都可以发言。
用 AutoGen 实现。

安装：
    pip install autogen-agentchat~=0.4

运行：
    export OPENAI_API_KEY=sk-xxx
    python 03_group_chat.py
"""
import os

from autogen import GroupChat, GroupChatManager

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat

# ============================================================
# 3 个 Agent 组成 GroupChat
# ============================================================
researcher = AssistantAgent(
    name="researcher",
    model_client="gpt-4o-mini",
    system_message="你是研究员，关注事实和数据。",
)

critic = AssistantAgent(
    name="critic",
    model_client="gpt-4o-mini",
    system_message="你是批评家，专门挑刺，关注风险和漏洞。",
)

synthesizer = AssistantAgent(
    name="synthesizer",
    model_client="gpt-4o-mini",
    system_message="你是综合者，综合大家意见形成最终结论。当大家达成共识时说 'TERMINATE'。",
)


# ============================================================
# RoundRobinGroupChat：轮流发言
# ============================================================
# 适合头脑风暴：每个 Agent 按顺序发言一次，反复循环
team = RoundRobinGroupChat(
    participants=[researcher, critic, synthesizer],
    termination_condition=MaxMessageTermination(max_messages=9),  # 最多 9 条
)


# ============================================================
# 演示
# ============================================================
if __name__ == "__main__":
    import asyncio

    async def run():
        print("=" * 60)
        print("GroupChat 模式：3 个 Agent 轮流讨论")
        print("=" * 60)

        result = await team.run(task="讨论：Multi-Agent 系统最大的风险是什么？")
        for msg in result.messages:
            print(f"\n[{msg.source}] {msg.content}")

    asyncio.run(run())