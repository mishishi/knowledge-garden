"""
07-framework-comparison / 02_langgraph.py

LangGraph 实现：调研 + 写作 + 评审

安装：
    pip install langgraph langchain-openai

运行：
    export OPENAI_API_KEY=sk-xxx
    python 02_langgraph.py
"""
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

llm = ChatOpenAI(model="gpt-4o-mini")


class State(TypedDict):
    topic: str
    facts: str
    draft: str
    review: str


def research_node(state: State) -> dict:
    response = llm.invoke([
        SystemMessage(content="你是研究员，调研给定 topic，输出 3 条关键事实。"),
        HumanMessage(content=state["topic"]),
    ])
    return {"facts": response.content}


def write_node(state: State) -> dict:
    response = llm.invoke([
        SystemMessage(content="你是写作员，基于事实写 100 字短文。"),
        HumanMessage(content=f"事实：{state['facts']}"),
    ])
    return {"draft": response.content}


def review_node(state: State) -> dict:
    response = llm.invoke([
        SystemMessage(content="你是评审员，评审文章质量。"),
        HumanMessage(content=f"文章：{state['draft']}"),
    ])
    return {"review": response.content}


workflow = StateGraph(State)
workflow.add_node("research", research_node)
workflow.add_node("write", write_node)
workflow.add_node("review", review_node)

workflow.add_edge(START, "research")
workflow.add_edge("research", "write")
workflow.add_edge("write", "review")
workflow.add_edge("review", END)

app = workflow.compile()


if __name__ == "__main__":
    result = app.invoke({"topic": "Multi-Agent 系统"})

    print("\n=== 最终输出 ===")
    print(f"[评审] {result['review']}")
    print(f"\n[文章] {result['draft']}")
    print(f"\n[事实] {result['facts']}")

    print("\n=== LangGraph 特点 ===")
    print("- 代码量：~30 行")
    print("- 调试：LangSmith 可视化 trace")
    print("- 适合：生产级复杂系统")