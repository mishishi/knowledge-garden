"""
05-state-and-communication / 01_message_protocol.py

消息协议对比：自然语言字符串 vs 结构化 JSON vs Pydantic 模型

运行：
    export OPENAI_API_KEY=sk-xxx
    python 01_message_protocol.py
"""
from typing import Literal

from crewai import Agent, Crew, Task
from pydantic import BaseModel, Field


# ============================================================
# 格式 1：自然语言字符串（反模式）
# ============================================================
def natural_language_demo():
    researcher = Agent(
        role="研究员",
        goal="调研 {topic}",
        backstory="你只输出自然语言调研结果。",
        allow_delegation=False,
    )

    task = Task(
        description="调研 {topic}，输出 3 个框架和它们的事实",
        expected_output="自然语言描述",
        agent=researcher,
    )

    return Crew(agents=[researcher], tasks=[task], verbose=True)
    # 输出：'我调研了 FastAPI，它的特点是... Django 是...'
    # 下游 Agent 收到这段话，需要自己解析 → 脆弱


# ============================================================
# 格式 2：结构化 JSON（中等推荐）
# ============================================================
def structured_json_demo():
    """在 expected_output 里要求 JSON 格式"""
    researcher = Agent(
        role="研究员",
        goal="调研 {topic}，输出 JSON 格式",
        backstory=(
            "你必须输出严格的 JSON，格式：\n"
            '{"frameworks": ["name1", "name2", "name3"], '
            '"facts": {"name1": ["fact1", "fact2"], ...}}'
        ),
        allow_delegation=False,
    )

    task = Task(
        description="调研 {topic}，输出 3 个框架和每个的 3 个事实，JSON 格式",
        expected_output="严格的 JSON 字符串",
        agent=researcher,
    )

    return Crew(agents=[researcher], tasks=[task], verbose=True)
    # 输出：'{"frameworks": ["FastAPI", ...], "facts": {...}}'
    # 下游 Agent 收到 JSON，但 LLM 可能输出格式不对的 JSON


# ============================================================
# 格式 3：Pydantic 模型（推荐）
# ============================================================
class Framework(BaseModel):
    """单个框架的信息"""
    name: str = Field(..., description="框架名")
    facts: list[str] = Field(..., min_length=3, max_length=3, description="3 条关键事实")
    use_case: Literal["api", "fullstack", "microservice"] = Field(..., description="主要用例")


class ResearchResult(BaseModel):
    """完整调研结果"""
    frameworks: list[Framework] = Field(..., min_length=3, max_length=3, description="恰好 3 个框架")


def pydantic_demo():
    """用 Pydantic 模型作为消息协议"""
    researcher = Agent(
        role="研究员",
        goal="调研 {topic}，输出 Pydantic 模型",
        backstory=(
            f"你必须输出符合以下 schema 的 JSON：\n"
            f"{ResearchResult.model_json_schema()}\n\n"
            "字段含义："
            "- frameworks: 恰好 3 个框架"
            "- 每个框架有 name、facts（3 条）、use_case"
        ),
        allow_delegation=False,
    )

    task = Task(
        description="调研 {topic}，输出符合 schema 的 JSON",
        expected_output="JSON 字符串，符合 ResearchResult schema",
        agent=researcher,
    )

    return Crew(agents=[researcher], tasks=[task], verbose=True)


# ============================================================
# 演示
# ============================================================
if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "pydantic"

    if mode == "nl":
        print("=" * 60)
        print("格式 1: 自然语言（脆弱）")
        print("=" * 60)
        result = natural_language_demo().kickoff(inputs={"topic": "Python Web 框架"})
        print(result)
        print("\n下游 Agent 需要自己解析这段自然语言")

    elif mode == "json":
        print("=" * 60)
        print("格式 2: 结构化 JSON（中等）")
        print("=" * 60)
        result = structured_json_demo().kickoff(inputs={"topic": "Python Web 框架"})
        print(result)
        print("\n下游 Agent 可以 json.loads() 解析")
        print("但 LLM 可能输出格式不对的 JSON（缺字段、嵌套错误）")

    elif mode == "pydantic":
        print("=" * 60)
        print("格式 3: Pydantic 模型（推荐）")
        print("=" * 60)
        result = pydantic_demo().kickoff(inputs={"topic": "Python Web 框架"})
        print(result)
        print("\n下游 Agent 可以直接 ResearchResult.model_validate_json(result.raw)")
        print("字段类型错误会被 Pydantic 自动捕获")

    else:
        print(f"未知模式: {mode}")
        print("用法: python 01_message_protocol.py [nl|json|pydantic]")