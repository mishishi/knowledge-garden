"""
02-why-multi-agent / single_agent_problems.py

演示单 Agent 撑不住的 3 个具体场景。
每个场景都能独立跑，但 API 配额有限时建议挑一个看。

运行：
    export OPENAI_API_KEY=sk-xxx
    python single_agent_problems.py
"""
import os
from crewai import Agent, Task, Crew


# ============================================================
# 场景 1：上下文爆炸
# ============================================================
# 任务：读完 5 个文件 → 提取关键 API → 改 1 个文件 → 跑测试
# 单 Agent 解法：把所有职责写进一个 backstory
print("=" * 60)
print("场景 1: 上下文爆炸")
print("=" * 60)

agent_context_overflow = Agent(
    role="全栈工程师",
    goal="读 5 个文件 → 提取 API → 改代码 → 跑测试",
    backstory=(
        # ← 这里开始拧巴：要把所有职责写进一个 prompt
        "你是资深 Python 工程师。"
        "你会先 read_file 读取 5 个 Python 文件，"
        "然后逐个分析文件内容并提取关键 API（函数签名、参数、返回值），"
        "然后 summarize 工具总结 API 列表，"
        "然后基于 API 列表设计修改方案，"
        "然后 edit_file 修改指定文件，"
        "然后 run_tests 跑测试验证修改正确，"
        "如果测试失败还要 debug..."
        # ← 200 字了。LLM 到第 4 步已经忘了第 1 步
    ),
    tools=[],  # 教学版省略工具定义，重点看 prompt
    verbose=True,
)

task_context_overflow = Task(
    description=(
        "读取 src/api.py、src/db.py、src/auth.py、src/utils.py、src/models.py 这 5 个文件，"
        "提取关键 API，然后修改 src/api.py 增加一个新的 /health 端点，最后跑 pytest 验证。"
    ),
    expected_output="修改后的 src/api.py + 测试通过的结果",
    agent=agent_context_overflow,
)


# ============================================================
# 场景 2：角色冲突
# ============================================================
print("\n" + "=" * 60)
print("场景 2: 角色冲突")
print("=" * 60)

agent_role_conflict = Agent(
    role="全能写手",
    goal="既做研究员又做写作员",
    backstory=(
        # ← 一个 prompt 想驱动两个角色，互相打架
        "你是专业研究员，深入调研每个框架的优缺点、性能数据、社区活跃度；"
        "同时你又是技术写作员，能写出 1000 字流畅的中文推荐文；"
        "还要是产品经理，能从用户视角给建议..."
        # ← 输出会分裂：时而"FastAPI 的依赖注入基于..."
        #   时而"如果你想要一个快速上手的框架..."
    ),
    verbose=True,
)

task_role_conflict = Task(
    description=(
        "调研 2026 年最流行的 3 个 Python Web 框架，"
        "写出每个框架的优缺点和适用场景，"
        "然后基于调研写一篇 1000 字的中文推荐文章。"
    ),
    expected_output="一篇 1000 字的中文推荐文章",
    agent=agent_role_conflict,
)


# ============================================================
# 场景 3：调试地狱
# ============================================================
print("\n" + "=" * 60)
print("场景 3: 调试地狱")
print("=" * 60)

agent_debug_hell = Agent(
    role="内容生成器",
    goal="基于事实写一篇推荐文",
    backstory=(
        "基于事实写作，不要编造。"
    ),
    verbose=True,
)

task_debug_hell = Task(
    description=(
        "调研 2026 年最流行的 3 个 Python Web 框架，"
        "然后写一篇 1000 字的中文推荐文章。"
        # ← 注意：调研 + 写作 都在这一个任务里
    ),
    expected_output="一篇 1000 字的中文推荐文章",
    agent=agent_debug_hell,
)


# ============================================================
# 跑起来（建议单独跑，token 烧得快）
# ============================================================
if __name__ == "__main__":
    import sys

    scenario = sys.argv[1] if len(sys.argv) > 1 else "1"

    if scenario == "1":
        crew = Crew(agents=[agent_context_overflow], tasks=[task_context_overflow], verbose=True)
        result = crew.kickoff()
        print("\n=== 输出 ===")
        print(result)
        print("\n=== 问题诊断 ===")
        print("跑完你会发现：")
        print("1. backstory 写到 200 字，LLM 已经记不住前几步")
        print("2. token 烧得离谱（5 个文件 + 中间结果全堆在 messages）")
        print("3. 如果中途崩了，没法定位是哪一步的问题")

    elif scenario == "2":
        crew = Crew(agents=[agent_role_conflict], tasks=[task_role_conflict], verbose=True)
        result = crew.kickoff()
        print("\n=== 输出 ===")
        print(result)
        print("\n=== 问题诊断 ===")
        print("跑完你会发现：")
        print("1. 输出语气不连贯（时而调研腔，时而营销腔）")
        print("2. 每个角色的深度都不够（半瓶水）")
        print("3. prompt 互相矛盾（既要严谨又要生动）")

    elif scenario == "3":
        crew = Crew(agents=[agent_debug_hell], tasks=[task_debug_hell], verbose=True)
        result = crew.kickoff()
        print("\n=== 输出 ===")
        print(result)
        print("\n=== 问题诊断 ===")
        print("如果输出错了（比如推荐了'2026 年最流行的是 Flask'，但实际是 FastAPI/Django），")
        print("你没法定位：是 LLM 没调研？还是调研错了？还是写作时引用错了事实？")
        print("只有一个 Agent = 只有一个对话历史，没法 step into 中间步骤。")

    else:
        print(f"未知场景: {scenario}")
        print("用法: python single_agent_problems.py [1|2|3]")