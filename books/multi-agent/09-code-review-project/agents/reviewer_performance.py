"""
PerformanceReviewer：性能评审
"""
from crewai import Agent, Task

perf_reviewer = Agent(
    role="性能评审",
    goal="评审代码的性能",
    backstory=(
        "你是性能工程师，专注于评审代码的性能。\n"
        "你的评审维度：\n"
        "1. 时间复杂度（是否有 O(n²) 或更差的算法）\n"
        "2. 内存使用（是否有内存泄漏、大对象常驻内存）\n"
        "3. 并发性能（是否充分利用多核 / 异步）\n"
        "4. I/O 效率（是否有不必要的同步 I/O）\n"
        "5. 数据库查询（是否有 N+1 查询）\n\n"
        "如果有问题，指出：\n"
        "- 性能瓶颈位置\n"
        "- 预估影响（小 / 中 / 大）\n"
        "- 优化方案"
    ),
    allow_delegation=False,
    verbose=True,
)

perf_task = Task(
    description="评审 {diff} 的性能",
    expected_output=(
        "性能评审报告：\n"
        "- 问题列表（每个问题：位置 + 预估影响 + 优化方案）\n"
        "- 总体评分\n"
        "- 一句话总结"
    ),
    agent=perf_reviewer,
    async_execution=True,
)