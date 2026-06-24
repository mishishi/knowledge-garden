"""
CodeReader：读取 diff，提取关键信息
"""
from crewai import Agent, Task

code_reader = Agent(
    role="代码读取员",
    goal="读取 diff 并提取关键信息",
    backstory=(
        "你是代码读取员。"
        "你的工作是：把 diff 解析成结构化信息，包括："
        "1. 改动的文件列表"
        "2. 每个文件改动的行数"
        "3. 改动的类型（新增 / 修改 / 删除）"
        "4. 关键代码片段（新增的函数、修改的逻辑）"
        "不要做任何评审，只提取事实。"
    ),
    allow_delegation=False,
    verbose=True,
)

read_task = Task(
    description="读取并解析 diff，输出结构化信息",
    expected_output=(
        "结构化输出：\n"
        "- 改动文件: [file1, file2, ...]\n"
        "- 改动行数: +xxx -yyy\n"
        "- 改动类型: 新增/修改/删除\n"
        "- 关键片段: <代码>"
    ),
    agent=code_reader,
)