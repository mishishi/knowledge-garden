"""
05-state-and-communication / 04_state_management.py

状态管理：单一大 State vs 分层 State vs 外部数据库
用 LangGraph 的 TypedDict State 演示分层方案。

安装：
    pip install langgraph langchain-openai

运行：
    export OPENAI_API_KEY=sk-xxx
    python 04_state_management.py
"""
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

llm = ChatOpenAI(model="gpt-4o-mini")


# ============================================================
# 反模式 1：单一大 State（所有字段所有节点都能读写）
# ============================================================
class MegaState(TypedDict, total=False):
    """一个超大的 State，每个节点都能读写所有字段"""
    research_result: str
    draft: str
    review: str
    final: str
    # 问题：researcher 节点可能不小心写 review 字段
    #      writer 节点可能不小心改 research_result
    #      调试时不知道谁改了哪个字段


# ============================================================
# 推荐方案：分层 State（每个节点只读写自己的字段）
# ============================================================
class ResearchState(TypedDict):
    """研究员节点只能读写这些字段"""
    topic: str
    research_result: str


class WriteState(TypedDict):
    """写作员节点只能读写这些字段"""
    research_result: str  # 从 ResearchState 传入
    draft: str


class ReviewState(TypedDict):
    """评审员节点只能读写这些字段"""
    draft: str
    review: str


class OverallState(TypedDict):
    """整个系统的 State（聚合各节点的子 State）"""
    topic: str
    research_result: str
    draft: str
    review: str
    final: str


# ============================================================
# 节点实现
# ============================================================
def researcher_node(state: OverallState) -> dict:
    """研究员节点：只读写 research_result"""
    response = llm.invoke([
        SystemMessage(content="你是研究员，调研给定 topic。"),
        HumanMessage(content=state["topic"]),
    ])
    # 只返回这个节点负责的字段
    return {"research_result": response.content}


def writer_node(state: OverallState) -> dict:
    """写作员节点：只读写 draft"""
    response = llm.invoke([
        SystemMessage(content="你是写作员，基于研究结果写文章。"),
        HumanMessage(content=f"研究：{state['research_result']}"),
    ])
    return {"draft": response.content}


def reviewer_node(state: OverallState) -> dict:
    """评审员节点：只读写 review"""
    response = llm.invoke([
        SystemMessage(content="你是评审员，评审草稿。"),
        HumanMessage(content=f"草稿：{state['draft']}"),
    ])
    return {"review": response.content}


def finalizer_node(state: OverallState) -> dict:
    """最终汇总节点：读 review，写 final"""
    final = f"[评审] {state['review']}\n\n[草稿] {state['draft']}"
    return {"final": final}


# ============================================================
# 构图
# ============================================================
workflow = StateGraph(OverallState)

workflow.add_node("researcher", researcher_node)
workflow.add_node("writer", writer_node)
workflow.add_node("reviewer", reviewer_node)
workflow.add_node("finalizer", finalizer_node)

workflow.add_edge(START, "researcher")
workflow.add_edge("researcher", "writer")
workflow.add_edge("writer", "reviewer")
workflow.add_edge("reviewer", "finalizer")
workflow.add_edge("finalizer", END)

app = workflow.compile()


# ============================================================
# 演示
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("分层 State：每个节点只读写自己的字段")
    print("=" * 60)

    result = app.invoke({"topic": "Multi-Agent 系统"})

    print("\n=== 最终 State ===")
    for key, value in result.items():
        if value:
            print(f"\n[{key}]")
            print(str(value)[:300])