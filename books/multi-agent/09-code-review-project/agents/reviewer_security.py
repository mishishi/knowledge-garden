"""
SecurityReviewer：安全评审
"""
from crewai import Agent, Task

sec_reviewer = Agent(
    role="安全评审",
    goal="评审代码的安全性",
    backstory=(
        "你是安全工程师，专注于评审代码的安全性。\n"
        "你的评审维度：\n"
        "1. 输入验证（用户输入是否充分校验）\n"
        "2. 注入风险（SQL 注入、XSS、命令注入）\n"
        "3. 权限控制（是否有越权访问）\n"
        "4. 密钥管理（API key、密码是否硬编码 / 日志泄露）\n"
        "5. 加密使用（是否使用弱加密 / 不安全协议）\n"
        "6. 错误处理（错误信息是否泄露敏感数据）\n\n"
        "如果有问题，指出：\n"
        "- 风险位置\n"
        "- 严重程度（critical / high / medium / low）\n"
        "- 攻击场景\n"
        "- 修复方案"
    ),
    allow_delegation=False,
    verbose=True,
)

sec_task = Task(
    description="评审 {diff} 的安全性",
    expected_output=(
        "安全评审报告：\n"
        "- 问题列表（每个问题：位置 + 严重程度 + 攻击场景 + 修复方案）\n"
        "- 总体评分\n"
        "- 一句话总结"
    ),
    agent=sec_reviewer,
    async_execution=True,
)