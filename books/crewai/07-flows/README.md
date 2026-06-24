# 07. Flows：状态化的事件驱动编排

> Crew 适合「一组人干一件事」。但生产里你常需要「先让 Crew A 跑，结果喂给 Crew B，再让 Crew C 收尾」——这时候 Crew 不够用，需要 Flow。v1.14 引入的状态化事件驱动层就是干这个的。

## 为什么需要 Flow

我自己的 production multi-agent 第一版全是 Crew——3 个 Crew 串行（研究 → 写 → 审）。Crews 之间传数据靠文件——研究 Crew 写 `research_result.json`、写 Crew 读这个文件、审 Crew 再读。看起来能用，问题一堆：

- 研究 Crew 写文件成功、写 Crew 读文件失败（路径错），整个链路挂
- 想做「如果研究结果超过 1000 字就再调一次 research Crew」这种条件分支，Crew 不支持
- 跑一半进程挂了，重启必须从头跑
- 想加 Human-in-the-Loop，Crew 没有原生支持

Crew 的局限：它是一次性「全员上、一起干、输出完事」。但真实生产场景需要「多 Crew 串行 + 状态共享 + 条件分支 + 错误恢复 + 人机协同」。

Flow 就是 CrewAI 给这些场景的解决方案。v1.14 官方说法：「生产应用推荐用 Flow 包 Crew」。我自己迁移 3 个 production 项目到 Flow 后，retry 逻辑、Human-in-the-Loop、断点恢复这些之前要自己包的事都开箱即用了。

## Flow 的核心概念

把 Flow 想成 React 组件 + useState：

- State（状态，跨步骤共享）—— 相当于 useState，所有方法都能读写
- @start()（入口点）—— 相当于 useEffect mount，Flow 启动时调一次
- @listen(method)（监听某个方法完成）—— 相当于 props callback，方法 A 完成后自动跑方法 B
- @router()（根据状态路由）—— 相当于 if/else 决定下一步走 A 还是 B
- @human_feedback（让人介入）—— 暂停 + 等用户输入 + 恢复
- 普通方法（业务流程）—— 普通 Python 函数
- 1..N 个 Crew（在步骤里调用）—— Flow 里嵌 Crew，Crew 跑完更新 State

Flow 不是替代 Crew——是包 Crew 的外层。CrewAI 自己的设计哲学是「Crew 是脑，Flow 是身体」。

## Flow 实例：从研究到发布的完整链路

```python
from crewai.flow.flow import Flow, listen, start, router, human_feedback
from pydantic import BaseModel

class PublishState(BaseModel):
    topic: str = ""
    facts: list[str] = []
    draft: str = ""
    review: str = ""
    approved: bool = False

class ContentFlow(Flow[PublishState]):
    
    @start()
    def get_topic(self):
        # 用户输入 topic
        return {"topic": "Multi-Agent 系统"}
    
    @listen(get_topic)
    def research(self, payload):
        # 调研究 Crew
        research_crew = ResearchCrew()
        result = research_crew.kickoff(inputs={"topic": self.state.topic})
        return {"facts": result.facts}
    
    @listen(research)
    def write_draft(self, payload):
        # 调写作 Crew
        write_crew = WriteCrew()
        result = write_crew.kickoff(inputs={"facts": self.state.facts})
        return {"draft": result.draft}
    
    @router(write_draft)
    def review_router(self):
        # 条件分支：draft 太短就重写，太长就润色
        if len(self.state.draft) < 50:
            return "rewrite"
        else:
            return "review"
    
    @listen("rewrite")
    def rewrite_draft(self):
        # 重新调写作 Crew
        write_crew = WriteCrew()
        result = write_crew.kickoff(inputs={"facts": self.state.facts, "feedback": "太短"})
        return {"draft": result.draft}
    
    @listen("review")
    def review(self):
        # 调评审 Crew
        review_crew = ReviewCrew()
        result = review_crew.kickoff(inputs={"draft": self.state.draft})
        return {"review": result.review}
    
    @human_feedback()
    def human_approve(self):
        # 让人评审 + 批准
        return {"approved": True}  # 默认假设批准
    
    @listen(human_approve)
    def publish(self, payload):
        if payload["approved"]:
            publish_to_blog(self.state.draft)
            return {"published": True}

flow = ContentFlow()
flow.kickoff(inputs={"topic": "Multi-Agent 系统"})
```

这就是真实生产里的 multi-agent 链路——3 个 Crew 串行 + 1 个 router（决定重写还是评审）+ 1 个 human feedback（发布前让人批准）。

## @router 条件分支

@router() 让 Flow 根据 State 决定下一步走哪个 path：

```python
@router(write_draft)
def review_router(self):
    if len(self.state.draft) < 50:
        return "rewrite"  # 走 @listen("rewrite")
    elif "敏感词" in self.state.draft:
        return "block"    # 走 @listen("block")
    else:
        return "review"   # 走 @listen("review")
```

我自己的客服 agent 用 router 做：根据用户情绪评分决定转人工还是 AI 继续回复；根据 query 复杂度决定走「快速回复 Crew」还是「深度研究 Crew」。

## @human_feedback 让人介入

```python
from crewai.flow.human_feedback import human_feedback

class PublishFlow(Flow[PublishState]):
    
    @human_feedback()
    def approve_publish(self):
        # Flow 自动暂停，等用户输入
        # CLI / Web UI 提示「批准发布？(y/N)」
        return input("Approve? [y/N] ")
```

Flow 暂停后 State 序列化保存到磁盘（默认 SQLite），用户输入后 Flow 从断点恢复——进程崩了重启能从断点继续。这是 Crew 没有的能力。

## State 持久化与断点恢复

Flow 用 SQLite 存 State（默认 `flow.db`），每个 step 完成后自动持久化。进程挂了重启：

```python
flow = ContentFlow()
flow.kickoff(inputs={"topic": "X"}, uuid="session-123")  # 第一次跑

# 进程挂了，重启
flow = ContentFlow()
flow.kickoff(inputs={"topic": "X"}, uuid="session-123")  # 从断点继续
```

我自己的 4 小时研究 + 写 + 审 + 发布链路，挂掉重启不需要从头跑——Flow 自动从上次完成的 step 继续。

## Flow vs Crew 何时用

不要所有 multi-agent 都上 Flow——Flow 有学习成本（要理解 state / router / listen 概念）。我自己用的决策：

**用 Crew 的场景**：单次任务、不需要状态共享、不需要断点恢复。比如「给个 topic 写 100 字短文」。

**用 Flow 的场景**：多 Crew 串行、需要条件分支、需要 Human-in-the-Loop、跑时间可能很长（需要断点恢复）。

迁移路径：先 Crew 跑通业务，3 个月后发现编排需求复杂再包 Flow。Flow 的学习曲线比 Crew 陡。

## Flow vs LangGraph

CrewAI Flow 和 LangGraph 都是 state-based multi-agent 编排。区别：

| 维度 | CrewAI Flow | LangGraph |
|---|---|---|
| 学习曲线 | 中（要懂装饰器） | 陡（要懂 state graph） |
| Crew 集成 | 原生 | 自己包 |
| 断点恢复 | SQLite 自动 | checkpointer 自己配 |
| Human-in-the-Loop | `@human_feedback()` 一行 | interrupt + Command 自己写 |
| Observability | 自带 trace | LangSmith（商业产品） |

我自己的 production：业务明确 + CrewAI 生态 → Flow；复杂编排 + 多语言 → LangGraph。两个都用，不二选一。

[08. Skills & Production](../08-skills-and-prod/) 讲 CrewAI 的 Skills 机制（agent 复用技能）+ 上 production 的 checklist。
