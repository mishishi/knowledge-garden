"""
04-orchestration-patterns / 05_graph.py

模式 5: Graph（图）
最通用的编排模式，能表达任意拓扑。
用 LangGraph 实现：3 个并行评审 + 1 个 Lead 汇总。

安装：
    pip install langgraph langchain-openai

运行：
    export OPENAI_API_KEY=sk-xxx
    python 05_graph.py
"""
from typing import TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

llm = ChatOpenAI(model="gpt-4o-mini")


# ============================================================
# 状态定义
# ============================================================
class State(TypedDict):
    diff: str
    arch_review: str
    perf_review: str
    sec_review: str
    final_report: str


# ============================================================
# 3 个并行评审节点
# ============================================================
def arch_reviewer(state: State) -> State:
    response = llm.invoke([
        SystemMessage(content="你是架构评审专家，只评审代码的架构设计、模块划分、依赖关系。"),
        HumanMessage(content=f"评审以下 diff：\n\n{state['diff']}"),
    ])
    return {"arch_review": response.content}


def perf_reviewer(state: State) -> State:
    response = llm.invoke([
        SystemMessage(content="你是性能评审专家，只评审时间复杂度、内存使用、并发性能。"),
        HumanMessage(content=f"评审以下 diff：\n\n{state['diff']}"),
    ])
    return {"perf_review": response.content}


def sec_reviewer(state: State) -> State:
    response = llm.invoke([
        SystemMessage(content="你是安全评审专家，只评审输入验证、权限控制、注入风险。"),
        HumanMessage(content=f"评审以下 diff：\n\n{state['diff']}"),
    ])
    return {"sec_review": response.content}


# ============================================================
# Lead 汇总
# ============================================================
def lead_reviewer(state: State) -> State:
    combined = f"""
[架构评审]
{state.get('arch_review', '')}

[性能评审]
{state.get('perf_review', '')}

[安全评审]
{state.get('sec_review', '')}
"""
    response = llm.invoke([
        SystemMessage(content="你是 Lead 评审，综合 3 份评审形成最终报告。"),
        HumanMessage(content=f"综合以下评审：\n\n{combined}"),
    ])
    return {"final_report": response.content}


# ============================================================
# 构图：并行 + 汇总
# ============================================================
workflow = StateGraph(State)

workflow.add_node("arch_reviewer", arch_reviewer)
workflow.add_node("perf_reviewer", perf_reviewer)
workflow.add_node("sec_reviewer", sec_reviewer)
workflow.add_node("lead_reviewer", lead_reviewer)

# START 分 3 路并行
workflow.add_edge(START, "arch_reviewer")
workflow.add_edge(START, "perf_reviewer")
workflow.add_edge(START, "sec_reviewer")

# 3 路汇总到 Lead
workflow.add_edge("arch_reviewer", "lead_reviewer")
workflow.add_edge("perf_reviewer", "lead_reviewer")
workflow.add_edge("sec_reviewer", "lead_reviewer")

# Lead → END
workflow.add_edge("lead_reviewer", END)

app = workflow.compile()


# ============================================================
# 演示
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Graph 模式：3 个并行评审 + Lead 汇总")
    print("=" * 60)

    sample_diff = """
diff --git a/api/auth.py b/api/auth.py
+def login(username, password):
+    query = f"SELECT * FROM users WHERE name='{username}' AND pwd='{password}'"
+    return db.execute(query)
"""

    result = app.invoke({"diff": sample_diff})

    print("\n=== 最终报告 ===")
    print(result["final_report"])