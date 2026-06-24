"""
05-state-and-communication / 03_broadcast.py

Broadcast：一个 Agent 的输出同时给多个 Agent
用 LangGraph 的 Send API 实现并行广播。

安装：
    pip install langgraph langchain-openai

运行：
    export OPENAI_API_KEY=sk-xxx
    python 03_broadcast.py
"""
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import START, StateGraph
from langgraph.constants import Send

llm = ChatOpenAI(model="gpt-4o-mini")


# ============================================================
# 状态定义
# ============================================================
class State(TypedDict):
    """主状态：广播源 + 多个接收方的输出"""
    source: str  # 广播源
    arch_view: str  # 接收方 A 的视角
    perf_view: str  # 接收方 B 的视角
    sec_view: str  # 接收方 C 的视角


# ============================================================
# 3 个接收方节点
# ============================================================
def arch_view(state: State) -> State:
    """架构视角"""
    response = llm.invoke([
        SystemMessage(content="你是架构师，从架构角度分析。"),
        HumanMessage(content=state["source"]),
    ])
    return {"arch_view": response.content}


def perf_view(state: State) -> State:
    """性能视角"""
    response = llm.invoke([
        SystemMessage(content="你是性能工程师，从性能角度分析。"),
        HumanMessage(content=state["source"]),
    ])
    return {"perf_view": response.content}


def sec_view(state: State) -> State:
    """安全视角"""
    response = llm.invoke([
        SystemMessage(content="你是安全工程师，从安全角度分析。"),
        HumanMessage(content=state["source"]),
    ])
    return {"sec_view": response.content}


# ============================================================
# 广播路由函数
# ============================================================
def broadcast_router(state: State) -> list[Send]:
    """把同一个 source 广播到 3 个接收方"""
    return [
        Send("arch_view", {"source": state["source"]}),
        Send("perf_view", {"source": state["source"]}),
        Send("sec_view", {"source": state["source"]}),
    ]


# ============================================================
# 构图
# ============================================================
workflow = StateGraph(State)

workflow.add_node("arch_view", arch_view)
workflow.add_node("perf_view", perf_view)
workflow.add_node("sec_view", sec_view)

# START → 广播到 3 个节点（并行）
workflow.add_conditional_edges(START, broadcast_router, ["arch_view", "perf_view", "sec_view"])

app = workflow.compile()


# ============================================================
# 演示
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Broadcast 模式：同一个 diff 广播到 3 个评审专家")
    print("=" * 60)

    sample = """
    我们的新代码：
    - 用 FastAPI 替代 Flask（性能考虑）
    - 加了 Redis 缓存层（性能考虑）
    - 用户的密码直接拼接到 SQL 查询（开发方便）
    """

    result = app.invoke({"source": sample})

    print("\n=== 架构视角 ===")
    print(result["arch_view"][:300])
    print("\n=== 性能视角 ===")
    print(result["perf_view"][:300])
    print("\n=== 安全视角 ===")
    print(result["sec_view"][:300])
    print("\n注意：3 个评审同时执行")