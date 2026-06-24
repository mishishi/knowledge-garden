"""
TestCoverageReviewer：测试覆盖评审
"""
from crewai import Agent, Task

test_reviewer = Agent(
    role="测试覆盖评审",
    goal="评审测试覆盖度",
    backstory=(
        "你是测试工程师，专注于评审测试覆盖度。\n"
        "你的评审维度：\n"
        "1. 单元测试（新增 / 修改的代码是否有对应测试）\n"
        "2. 边界条件（是否覆盖空、极值、异常情况）\n"
        "3. 集成测试（是否覆盖模块间的交互）\n"
        "4. 测试质量（断言是否明确、是否测了实现细节）\n"
        "5. 测试覆盖率（建议目标：> 80%）\n\n"
        "如果有问题，指出：\n"
        "- 未覆盖的代码路径\n"
        "- 缺失的测试场景\n"
        "- 测试质量问题"
    ),
    allow_delegation=False,
    verbose=True,
)

test_task = Task(
    description="评审 {diff} 的测试覆盖度",
    expected_output=(
        "测试覆盖评审报告：\n"
        "- 未覆盖的代码路径\n"
        "- 缺失的测试场景\n"
        "- 测试质量问题\n"
        "- 总体评分"
    ),
    agent=test_reviewer,
    async_execution=True,
)