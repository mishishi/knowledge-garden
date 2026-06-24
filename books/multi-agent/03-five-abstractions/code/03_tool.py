"""
03-five-abstractions / 03_tool.py

Tool 抽象演示：自定义工具的写法 + 工具设计原则。

运行：
    export OPENAI_API_KEY=sk-xxx
    python 03_tool.py
"""
from crewai import Agent, Crew, Task
from crewai.tools import tool


# ============================================================
# 自定义工具：3 种写法
# ============================================================

# 写法 1：@tool 装饰器（最简单）
@tool("Get Weather")
def get_weather(city: str) -> str:
    """查询指定城市的天气。

    Args:
        city: 城市名，比如 'Tokyo' 或 'Beijing'
    """
    mock = {
        "tokyo": "东京: 22°C, 晴",
        "beijing": "北京: 18°C, 多云",
    }
    return mock.get(city.lower(), f"{city}: 暂无数据")


# 写法 2：BaseTool 子类（更可控）
from crewai.tools import BaseTool
from pydantic import Field


class CalculatorTool(BaseTool):
    name: str = "Calculator"
    description: str = "执行数学计算。支持 +、-、*、/ 四则运算"

    def _run(self, expression: str) -> str:
        try:
            # 严格限制：只允许数字和四则运算符
            allowed = set("0123456789+-*/(). ")
            if not all(c in allowed for c in expression):
                return "错误：只支持数字和 + - * /"
            return str(eval(expression))
        except Exception as e:
            return f"错误：{e}"


# 写法 3：返回错误信息的工具（生产推荐）
@tool("Search Docs")
def search_docs(query: str) -> str:
    """在文档库中搜索关键词。

    返回匹配的文档片段。如果没有找到，返回空字符串而不是报错。
    """
    # Mock 数据
    docs = [
        "Multi-Agent 是多个 LLM 协作的系统",
        "CrewAI 是一个 Multi-Agent 框架",
        "LangGraph 用图结构编排 Agent",
    ]
    matches = [d for d in docs if query.lower() in d.lower()]
    if not matches:
        return ""  # ← 没找到就返回空字符串，不抛异常
    return "\n".join(matches)


# ============================================================
# 演示：3 种工具组合使用
# ============================================================
researcher = Agent(
    role="研究员",
    goal="回答用户的问题，可以使用工具查资料",
    backstory="你会用工具查准确信息，不凭印象回答。",
    tools=[get_weather, CalculatorTool(), search_docs],
    allow_delegation=False,
)

task = Task(
    description="回答用户问题：{question}",
    expected_output="准确答案",
    agent=researcher,
)

crew = Crew(agents=[researcher], tasks=[task], verbose=True)


# ============================================================
# 工具设计原则（注释里讲）
# ============================================================
"""
工具设计 5 个原则：

1. docstring 写清楚
   - LLM 是靠 docstring 决定要不要调、调什么参数
   - docstring 写"做什么"，不是"怎么实现"

2. 错误信息要可操作
   - 不要抛裸异常
   - 返回："错误：参数 X 必须是 Y 格式" 而不是 "ValueError"

3. 幂等性
   - 同一个输入应该返回同样的输出
   - 不要在工具里写"当前时间戳"这种随机性

4. 颗粒度合适
   - 太粗：get_weather_everything() - LLM 不知道调什么
   - 太细：get_temp() / get_humidity() / get_wind() - LLM 会被淹没
   - 合适：get_weather(city) - 一个城市一次调用

5. 鉴权和限流
   - 工具内部检查权限（不要假设 LLM 不会调"删除数据库"）
   - 加 rate limit 防止 LLM 死循环调用

"""


if __name__ == "__main__":
    import sys

    question = sys.argv[1] if len(sys.argv) > 1 else "东京今天天气怎么样？"
    result = crew.kickoff(inputs={"question": question})
    print("\n=== 输出 ===")
    print(result)