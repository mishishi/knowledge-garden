"""
06-failure-handling / 05_human_in_loop.py

Human-in-the-Loop：关键决策点暂停，让人类介入。
用 LangGraph 的 interrupt 实现。

安装：
    pip install langgraph langchain-openai

运行：
    export OPENAI_API_KEY=sk-xxx
    python 05_human_in_loop.py
"""
from typing import Literal, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

llm = ChatOpenAI(model="gpt-4o-mini")


# ============================================================
# 状态
# ============================================================
class State(TypedDict):
    action: str
    risk_level: str
    approved: bool
    final_result: str


# ============================================================
# 节点：评估风险
# ============================================================
def assess_risk(state: State) -> State:
    """评估操作的风险等级"""
    response = llm.invoke([
        SystemMessage(content="你是风险评估员。判断 action 的风险等级（low / medium / high）。只输出一个词。"),
        HumanMessage(content=f"操作: {state['action']}"),
    ])
    risk = response.content.strip().lower()
    if "high" in risk:
        risk = "high"
    elif "medium" in risk:
        risk = "medium"
    else:
        risk = "low"
    return {"risk_level": risk}


# ============================================================
# 节点：低风险自动通过
# ============================================================
def auto_approve(state: State) -> State:
    return {"approved": True, "final_result": f"自动通过 (风险: {state['risk_level']})"}


# ============================================================
# 节点：高风险需要人类批准
# ============================================================
def human_approval(state: State) -> State:
    """暂停，让人类决策"""
    decision = interrupt({
        "question": f"操作 '{state['action']}' 是高风险操作，是否批准？",
        "risk_level": state["risk_level"],
    })
    # decision 来自人类输入
    approved = decision.lower() in ["yes", "y", "approve", "批准"]
    return {
        "approved": approved,
        "final_result": f"人类{'批准' if approved else '拒绝'} (风险: {state['risk_level']})",
    }


# ============================================================
# 路由
# ============================================================
def route_by_risk(state: State) -> Literal["auto_approve", "human_approval"]:
    if state["risk_level"] == "low":
        return "auto_approve"
    return "human_approval"


# ============================================================
# 构图
# ============================================================
workflow = StateGraph(State)
workflow.add_node("assess_risk", assess_risk)
workflow.add_node("auto_approve", auto_approve)
workflow.add_node("human_approval", human_approval)

workflow.add_edge(START, "assess_risk")
workflow.add_conditional_edges("assess_risk", route_by_risk)
workflow.add_edge("auto_approve", END)
workflow.add_edge("human_approval", END)

# 用 checkpointer 支持 interrupt + resume
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)


# ============================================================
# 演示
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("HITL 演示：低风险自动通过，高风险需要人类批准")
    print("=" * 60)

    thread_config = {"configurable": {"thread_id": "demo-1"}}

    # 场景 1：低风险操作
    print("\n场景 1: 查询天气（低风险）")
    result = app.invoke({"action": "查询北京天气"}, config=thread_config)
    print(f"  结果: {result.get('final_result')}")

    # 场景 2：高风险操作（会触发 interrupt）
    print("\n场景 2: 删除数据库（高风险）")
    thread_config2 = {"configurable": {"thread_id": "demo-2"}}
    result = app.invoke({"action": "删除生产数据库"}, config=thread_config2)

    if "__interrupt__" in str(result) or "interrupt" in str(result).lower():
        print("  → Agent 暂停，请求人类决策")
        print(f"  → interrupt: {result.get('__interrupt__')}")

        # 模拟人类决策：批准
        print("\n  人类输入: yes（批准）")
        result = app.invoke(Command(resume="yes"), config=thread_config2)
        print(f"  最终结果: {result.get('final_result')}")
    else:
        print(f"  结果: {result.get('final_result')}")