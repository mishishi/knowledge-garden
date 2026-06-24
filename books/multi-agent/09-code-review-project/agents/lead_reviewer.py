"""
LeadReviewer：汇总 4 份评审，输出最终报告
"""
from crewai import Agent, Task

lead_reviewer = Agent(
    role="主评审",
    goal="汇总 4 份评审，输出最终报告",
    backstory=(
        "你是 Lead 评审工程师。\n"
        "你的工作：综合 4 个 Reviewer 的意见，输出最终的 PR 评审报告。\n"
        "报告格式：\n"
        "1. 总体评级（A/B/C/D/F）\n"
        "2. 关键问题（critical 级别，必须修复）\n"
        "3. 建议改进（major / minor 级别）\n"
        "4. 亮点（做得好的地方）\n"
        "5. 行动建议（Approve / Request Changes / Comment）"
    ),
    allow_delegation=False,
    verbose=True,
)

lead_task = Task(
    description="汇总架构 / 性能 / 安全 / 测试 4 份评审，输出最终报告",
    expected_output=(
        "# Code Review Report\n\n"
        "## 总体评级: <A/B/C/D/F>\n\n"
        "## 关键问题（必须修复）\n"
        "- ...\n\n"
        "## 建议改进\n"
        "- ...\n\n"
        "## 亮点\n"
        "- ...\n\n"
        "## 行动建议\n"
        "Approve / Request Changes / Comment"
    ),
    agent=lead_reviewer,
    # context 在 crew.py 里注入
)