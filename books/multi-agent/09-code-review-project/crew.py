"""
09-code-review-project / crew.py

组装 6 个 Agent 组成 CodeReviewer Multi-Agent Crew。
所有 Agent 和 Task 都在这里装配 context 关系。
"""
from crewai import Crew

from agents.code_reader import code_reader, read_task
from agents.lead_reviewer import lead_reviewer, lead_task
from agents.reviewer_architecture import arch_reviewer, arch_task
from agents.reviewer_performance import perf_reviewer, perf_task
from agents.reviewer_security import sec_reviewer, sec_task
from agents.reviewer_test import test_reviewer, test_task


def create_review_crew() -> Crew:
    """组装 CodeReviewer Multi-Agent"""
    # ============================================================
    # 配置 Task 之间的 context 依赖关系
    # ============================================================
    # 4 个 Reviewer 都依赖 CodeReader 的输出
    arch_task.context = [read_task]
    perf_task.context = [read_task]
    sec_task.context = [read_task]
    test_task.context = [read_task]

    # Lead 汇总依赖 4 个 Reviewer 的输出
    lead_task.context = [arch_task, perf_task, sec_task, test_task]

    return Crew(
        agents=[
            code_reader,
            arch_reviewer,
            perf_reviewer,
            sec_reviewer,
            test_reviewer,
            lead_reviewer,
        ],
        tasks=[
            read_task,      # 1. 读取 diff
            arch_task,      # 2a. 架构评审（并行）
            perf_task,      # 2b. 性能评审（并行）
            sec_task,       # 2c. 安全评审（并行）
            test_task,      # 2d. 测试评审（并行）
            lead_task,      # 3. 汇总
        ],
        verbose=True,
    )