"""
04-orchestration-patterns / 02_supervisor.py

模式 2: Supervisor（监督者）
中央调度决定下一步交给哪个 Worker。
用 LangGraph 实现。

安装：
    pip install langgraph langchain-openai

运行：
    export OPENAI_API_KEY=sk-xxx
    python 02_supervisor.py
"""
from typing import Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

llm = ChatOpenAI(model="gpt-4o-mini")


# ============================================================
# 状态定义
# ============================================================
class State(TypedDict):
    messages: list
    next_worker: str  # Supervisor 决定下一步给谁


# ============================================================
# 3 个 Worker
# ============================================================
def researcher(state: State) -> State:
    """调研员"""
    response = llm.invoke([
        SystemMessage(content="你是研究员，只做调研，输出 3 条关键事实。"),
        *state["messages"],
    ])
    return {"messages": state["messages"] + [response]}


def writer(state: State) -> State:
    """写作员"""
    response = llm.invoke([
        SystemMessage(content="你是写作员，基于研究员的事实写 100 字短文。"),
        *state["messages"],
    ])
    return {"messages": state["messages"] + [response]}


def reviewer(state: State) -> State:
    """评审员"""
    response = llm.invoke([
        SystemMessage(content="你是评审员，检查文章质量问题并给出改进建议。"),
        *state["messages"],
    ])
    return {"messages": state["messages"] + [response]}


# ============================================================
# Supervisor：决定下一步
# ============================================================
def supervisor(state: State) -> State:
    """监督者：判断当前状态，决定下一步给哪个 Worker"""
    last_msg = state["messages"][-1].content if state["messages"] else ""

    prompt = f"""你是 Supervisor。判断当前任务进度，决定下一步交给谁。

可用 Worker：
- researcher（调研）
- writer（写作）
- reviewer（评审）

如果还没调研过 → FINISH/下一步：researcher
如果调研过但没写作 → FINISH/下一步：writer
如果写作完成 → FINISH/下一步：reviewer
如果评审完成 → FINISH

当前最后一条消息：{last_msg}

只输出一行：FINISH/下一步：<worker_name 或 FINISH>
"""

    response = llm.invoke([SystemMessage(content=prompt)])
    decision = response.content.strip().lower()

    if "researcher" in decision:
        next_worker = "researcher"
    elif "writer" in decision:
        next_worker = "writer"
    elif "reviewer" in decision:
        next_worker = "reviewer"
    else:
        next_worker = END

    return {"next_worker": next_worker}


# ============================================================
# 路由函数
# ============================================================
def route(state: State) -> Literal["researcher", "writer", "reviewer", "__end__"]:
    return state["next_worker"]


# ============================================================
# 构图
# ============================================================
workflow = StateGraph(State)

workflow.add_node("supervisor", supervisor)
workflow.add_node("researcher", researcher)
workflow.add_node("writer", writer)
workflow.add_node("reviewer", reviewer)

workflow.add_edge(START, "supervisor")

# Supervisor 决定后路由到对应 Worker
workflow.add_conditional_edges(
    "supervisor",
    route,
    {
        "researcher": "researcher",
        "writer": "writer",
        "reviewer": "reviewer",
        "__end__": END,
    },
)

# Worker 执行完后回到 Supervisor 重新决策
workflow.add_edge("researcher", "supervisor")
workflow.add_edge("writer", "supervisor")
workflow.add_edge("reviewer", "supervisor")

app = workflow.compile()


# ============================================================
# 演示
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Supervisor 模式：中央调度")
    print("=" * 60)

    initial_state = {
        "messages": [HumanMessage(content="调研 Multi-Agent 系统，写一篇 100 字短文，然后评审。")],
        "next_worker": "supervisor",
    }

    result = app.invoke(initial_state)
    print("\n=== 最终状态 ===")
    for msg in result["messages"]:
        print(f"[{type(msg).__name__}] {msg.content}\n")