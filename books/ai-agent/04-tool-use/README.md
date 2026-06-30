# 04. 工具调用: Agent 的手

2024 年 6 月那个周五晚上,我盯着屏幕看 Claude 把一个 shell 命令吐出来,自己执行,然后根据 stdout 决定下一步该调哪个 tool。我当时的第一反应是 —— 这不就是 REPL 吗?二十年前我写 Perl 脚本的时候就这么干。但往深里想,这玩意儿跟 REPL 又不一样:REPL 是人驱动的,而这个是模型在驱动整条调用链。**工具调用是 Agent 区别于"会说话的 LLM"的核心分水岭**。一个只会聊天的模型,和一个能订机票、改数据库、跑浏览器脚本的模型,在工程复杂度上差了大概两个数量级。

我 2022 年底开始认真做 Agent 相关的东西,那时候 OpenAI 刚把 function call 这个东西稳定下来,大家都叫它 "function calling"。当时我第一版代码写得特别丑,把工具定义塞在 system prompt 里,然后让模型吐 JSON,再用正则 `json.loads(re.search(r'```json\n(.+?)\n```', text, re.DOTALL).group(1))` 去 parse。说出来都丢人,但 2023 年上半年我们组大部分人都是这么干的 —— 因为模型不听话,经常吐出来的东西不是合法 JSON,或者参数名拼错,或者直接给你一段自然语言解释"我接下来要调用 search 工具,参数是..."。

后来 OpenAI 出了结构化输出 (structured outputs),Anthropic 出了 tool use,Google 出了 function calling,大家才真正把"工具调用"从 prompt 工程的脏活里解放出来。这章我想跟你聊的,就是这件事在工程上到底是怎么演化的,以及我们做 Agent 的工程师在这一层应该关心什么。

## 工具调用协议:三家怎么打,怎么选

先说协议层,因为这是写代码最先碰到的。2024 年下半年到现在,主流的协议基本上收敛在三种格式上:**OpenAI 的 tools 字段、Anthropic 的 tools 字段,以及 Anthropic 在 2025 年推的 MCP (Model Context Protocol)**。这三种我全都用过,讲讲体感。

OpenAI 的格式最直观。一个 `tools` 数组,每个 tool 是一坨 JSON Schema,长这样(我直接从我们生产代码里截的,脱敏过):

```python
tools = [{
    "type": "function",
    "function": {
        "name": "search_orders",
        "description": "查询用户订单,支持按时间范围、状态、订单号过滤",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "date_from": {"type": "string", "format": "date"},
                "status": {"type": "string", "enum": ["pending", "shipped", "delivered"]}
            },
            "required": ["user_id"]
        }
    }
}]
```

然后 model 返回的时候,`choices[0].message.tool_calls` 给你一个数组,每个里面是 `{"id": "call_abc", "type": "function", "function": {"name": "...", "arguments": "..."}}`。注意 `arguments` 是个 string,你得自己再 `json.loads` 一次。

Anthropic 的格式逻辑差不多,但 message 结构不一样。Tool use 是 message block 的一种类型,长这样:

```python
response = {
    "content": [
        {"type": "text", "text": "我先查一下订单"},
        {"type": "tool_use", "id": "toolu_abc", "name": "search_orders", "input": {...}}
    ]
}
```

`input` 直接就是 dict,不用再 parse。这个细节小但很烦,因为你写 client 代码的时候经常要在两边之间做转换。我们当时用 LiteLLM 抽象了一层,这种痛苦就消失了,后面聊。

说个题外话但很关键的事:**2024 年 12 月左右,我们组在评估 GPT-4o 和 Claude 3.5 Sonnet 的工具调用稳定性**。具体怎么测的我后面接 AI Evals 那章会展开,但数字我先抛出来 —— 在我们内部的 600 条工具调用样本上,Claude 3.5 Sonnet 的"参数完全合法率"是 0.94, GPT-4o 是 0.89;但在"调用了正确的 tool"这件事上,Claude 是 0.81, GPT-4o 是 0.78。两边都没到 0.95 以上,这就是为什么后面我们一定要加一层 retry + schema validation。

2025 年之后,我自己的项目基本只接 Anthropic 和 OpenAI,Google 那边的 function calling 一直没追,但 Gemini 2.0 那阵子业内反馈还行,就是生态弱。如果你要快速开始,直接上 **LiteLLM 或者 Instructor** 抽象一下,别跟自己较劲写 client。我用 Instructor 比较多,因为它把 Pydantic 模型直接当 tool 声明用,代码读起来舒服太多:

```python
from pydantic import BaseModel, Field
from instructor import from_anthropic

class SearchOrders(BaseModel):
    user_id: str = Field(..., description="用户 ID")
    date_from: str | None = Field(None, description="起始日期 YYYY-MM-DD")
    status: str | None = Field(None, description="订单状态")

client = from_anthropic(anthropic.Anthropic())
order_query = client.messages.create(
    model="claude-sonnet-4-5",
    messages=[{"role": "user", "content": "查一下用户 u_123 这周已发货的订单"}],
    response_model=SearchOrders,
)
```

Instructor 内部把 Pydantic model 转成 Anthropic 的 tool schema,parse 回来再 validate,顺手做了重试。**这一层抽象从我们的代码里消除了大概 40% 的样板代码**,而且把"模型吐错 JSON"这种 bug 几乎完全挡在了外面。代价是你被绑在 Pydantic + 这两个 provider 上,换别的就得自己写 adapter。

## MCP:协议统一的尝试,以及它没解决的问题

**MCP (Model Context Protocol) 是 2024 年 11 月 Anthropic 推出来的,2025 年算是真正铺开**。它的核心想法特别工程师思维:把 tool 暴露这件事标准化成 client-server 模型,server 端用 stdio 或者 HTTP 跟 client 通信,client 端 (一般是 Claude Desktop 或者你写的 Agent 框架) 通过 JSON-RPC 调。一个 MCP server 长这样(简化版):

```python
from mcp.server import Server
from mcp.types import Tool, TextContent

app = Server("my-tools")

@app.list_tools()
async def list_tools():
    return [Tool(
        name="search_orders",
        description="查询用户订单",
        inputSchema={...}  # JSON Schema
    )]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "search_orders":
        result = db.query(...)
        return [TextContent(type="text", text=json.dumps(result))]
```

MCP 解决的问题很现实:**以前每个 Agent 框架都有自己的 tool 接入方式**,LangChain、AutoGen、CrewAI 各搞一套,你写一个工具想复用,得给三个框架都写 adapter。MCP 想做"工具的 USB-C 接口" —— 一个 server 写好,所有兼容 MCP 的 client 都能用。

2025 年我们组在内部推过一波 MCP,接了大概 30 多个 internal tools (查数据库、改工单、跑 ETL、查 Grafana)。体感是:**MCP 在"工具的发现和注册"这件事上确实赢了** —— server 起来之后,client 自动知道有哪些 tool 能用,不用手动注册 schema。但 MCP 没有解决,而且大概率不会解决的事情是:

**工具语义对齐**。就是说,你让模型去"修这个 bug",MCP 能把 `create_jira_ticket` 这个 tool 喂给它,但模型怎么知道"修 bug"对应"建 ticket + 指给 owner + 设 priority = high"?这个不在协议层,这是 prompt engineering / 工具描述 / few-shot 的事。我在我们的 600 条样本里专门看过,**工具描述写得好不好,对调用准确率的影响是 0.11-0.15 个点**。这个数字比换模型还猛。

另一个 MCP 没解决的事情是**tool 的版本管理和权限**。你把一个 tool 部署上去,怎么升级 schema 不破坏老的 client?怎么限定某些 tool 只能被某些 user 调?MCP 自己不管,你得在 server 实现里加 auth 和 version negotiation。我们当时就是自己叠了一层。

**所以我的建议是:接 MCP,但别把所有赌注都押在它上面**。用 MCP 做"工具分发"很合适,但工具的设计、错误处理、重试策略,得自己把控。MCP 生态 2025 年下半年明显起来了,Cursor、Cline、各家 IDE agent 基本都支持,如果你做的是开发者工具,接 MCP 几乎是必选。

## 工具设计原则:从 200 个 tool 的坑里学到的

我 2025 年初做过一个项目,把一个 SaaS 产品所有能干的活儿(大概 200+ 个 API endpoint)接进 Agent,做成"自然语言版的操作面板"。**第一次做的时候我们把所有 endpoint 平铺扔给模型,失败得一塌糊涂**。具体怎么失败的呢,token 爆炸 —— 200 个 tool 的 JSON schema 加起来大概 12 万 token,光 system prompt 就吃掉了 18k,留给真正对话的 token 不到一半。而且模型在这么多 tool 里挑,选择准确率直接掉到 0.6 以下。

后来我们做了几轮迭代,有几个经验我觉得对所有做 Agent 的人都有用。

**第一,tool 数量控制在 20 个以内,最好是 10 个左右**。这个不是硬规矩,Claude 3.5/3.7 能 handle 30-40 个 tool,4 系列应该能更多。但我们的经验是,tool 越多,选择越糊,而且 context window 浪费在 schema 上。**真正能跑的做法是分层:高频 5-10 个 tool 常驻,长尾的 tool 在需要时 dynamic load**。比如用户问"查订单",你不需要把"建工单"也塞进去。

**第二,tool description 是产品,不是文档**。我前面提到这个数字 —— 描述对准确率影响 0.11-0.15 个点。具体什么意思呢?我直接给个对比:

差的描述:
```json
"name": "get_data",
"description": "Gets data"
```

好的描述:
```json
"name": "get_user_orders",
"description": "查询指定用户在指定时间范围内的订单列表。**重要:如果用户没指定时间,默认查最近 7 天**。如果用户没指定状态,返回所有状态。返回的 order_id 可以用于后续的 get_order_detail 调用。"
```

加粗的"重要"、明确默认值、指出跟其他 tool 的关系 —— 这些东西对模型的决策帮助巨大。**我们组的习惯是,tool description 要被当作"给模型的 prompt"来写,而不是 API 文档**。意思就是写完自己读一遍,把自己当模型,看能不能根据这段描述做出正确决策。

**第三,error 是 tool 设计的一部分,不是 afterthought**。这点踩过坑你才会痛。我们最早的工具,失败了就返回一个 `{"error": "DB timeout"}`,模型拿到这个也不知道该怎么办 —— 是重试?换 tool?问用户?后来我们强制要求每个 tool 的错误返回都带一个 `retryable: bool` 和 `user_actionable: bool` 字段,模型看到 `retryable: true` 就自己重试,看到 `user_actionable: true` 就去问用户。这样**端到端的成功率从 0.71 提升到了 0.83**。

```python
class ToolError(BaseModel):
    code: str  # "DB_TIMEOUT" / "INVALID_INPUT" / "PERMISSION_DENIED"
    message: str  # 给模型看的解释
    retryable: bool
    user_actionable: bool
    suggested_retry_after_ms: int | None = None
```

**第四,tool 的 idempotency 必须想清楚**。这个听起来像后端常识,但在 Agent 场景特别重要 —— 因为模型可能因为 context window 满了或者其他原因,同一个 tool call 发两次。如果你的 `create_user` 不是 idempotent,那第二次调用可能直接报"user already exists",模型又不知道该怎么办。**我们做所有写操作的 tool 都强制要求接受一个 `idempotency_key` 参数**,模型自己生成一个 UUID 放在那里,服务端去重。这事看起来小,但线上救过我们命。

## 浏览器 Agent:一个真实的工具调用案例

我 2025 年做过的项目里,**最"工具调用密集"的是浏览器 Agent**。我给你讲讲我们怎么搭的,你拿去改改就能用到自己的项目里。

场景是这样的:我们给运营团队做一个 agent,能根据自然语言指令去操作内部 admin 后台(选品、改价格、查报表)。admin 后台是个老破 SPA,没有 API,只有 UI。所以 agent 必须能驱动浏览器。

工具集我们是这样设计的:

```python
browser_tools = [
    Tool(name="browser_navigate", ..., description="导航到指定 URL。**调这个 tool 之前先看当前 URL,别无脑跳**"),
    Tool(name="browser_click", ..., description="点击 selector 指定的元素。selector 优先用 data-testid,没有再退到 CSS"),
    Tool(name="browser_type", ..., description="在 input 里输入文本。**输入前先 click 聚焦**"),
    Tool(name="browser_screenshot", ..., description="截屏,返回 base64 编码的 PNG。**任何不确定的页面状态都先截图看**"),
    Tool(name="browser_read_dom", ..., description="读取当前页面的可访问性树,返回简化版 DOM"),
    Tool(name="browser_wait_for", ..., description="等待某个 selector 出现,或者等待固定毫秒数"),
]
```

关键的几个 trick 我说一下。

**第一个,用 Playwright 而不是 Selenium 或者 Puppeteer 的 Python binding**。Playwright 的异步 API 干净,等待机制好,而且它有个特别牛的功能是 `page.accessibility.snapshot()`,返回的是 a11y tree —— 这是带语义的 DOM,比 raw HTML 好用十倍。模型拿到 a11y tree 之后,能直接理解"这是一个 button,名字是'提交订单'"。

**第二个,永远先截图,再决定下一步**。这是血的教训。我们最早一版让模型纯靠 DOM 决策,结果遇到 modal 弹窗、loading 状态、toast 通知这种东西,模型完全瞎掉 —— DOM 里这些元素要么不存在,要么是动态的,模型推理时拿的是上一步的快照。**加了 screenshot 之后,任务完成率从 0.62 提到 0.81**。截图用 Claude 的 vision 来读,效果很好,token 也还能接受(我们做了缩放,1280x720 那个量级,大概 1000-1500 token)。

**第三个,长任务必须做 step checkpoint**。浏览器操作经常是 20-30 步的长链,中间任何一步失败,从头来体验很差。我们做了一个简单的机制:每完成一个"逻辑步骤"(比如"登录完成"、"进入商品列表"),就把当前 page state 序列化一下存起来。失败的时候从最近的 checkpoint 恢复,而不是从 0 开始。这个不是工具调用本身的事,是 agent loop 的设计,但跟 tool 关系很大,所以放在一起讲。

**第四,工具的 granularity 是个哲学问题**。是给模型 `browser_click` 这种"原子操作",还是给 `browser_login` 这种"高层动作"?我们试过两种,最后**用了混合方案**。原子操作放底层(click/type/navigate),高层动作是"宏",由几个原子操作组合而成,模型也可以选择直接调原子操作。**这个给了模型灵活性,又给了一致性**。但宏要小心 —— 写得太死,模型遇到宏没覆盖的情况就完蛋;写得太多,context 里全是宏定义,token 又爆。

## 工具调用的进化方向,跟其他系列的衔接

讲讲我对未来 12-18 个月工具调用这件事的判断。

**短期 (2025-2026),各家会把 tool 调用的 latency 拉下来**。现在 tool call 一次 round trip 至少 1-3 秒(模型推理 + 网络),如果你做的是实时 agent(比如语音助手),这个 latency 真的扛不住。Anthropic 推 prompt caching、OpenAI 推 predicted outputs,部分是为了降 tool call latency。我自己的体感是,**从 2024 年中到 2025 年底,tool call 的 p50 latency 从 2.1s 降到了 0.9s 左右**(在我们内部的 benchmark 上),这主要靠的是模型速度的提升和 streaming tool call 的支持。

**中期,tool 本身会变"聪明"**。什么意思呢?现在的 tool 是 dumb function,传什么参数就做什么。**2025 年开始有人在做"smart tool"** —— tool 自己也是一个 LLM call,接受自然语言输入,自己决定怎么调 API。比如 `search_orders` 这个 tool,内部不是直接打 DB,而是先调一个 LLM 解析"最近一周已发货的订单"这个 query,转成 SQL,再查。这种"嵌套 LLM"在 tool 内部很常见了,但还没标准化。

**长期看,我赌的是 protocol 层会进一步统一**。MCP 是个开头,但还不够。真正的"工具生态"可能需要类似 npm 的东西 —— 中央 registry、版本管理、签名验证、付费机制。Anthropic 在推 MCP registry,社区也有 r/mcp 这种,2025 年底能看到一些雏形。但说实话,**离真正的"tool 商店"还远**,因为现在 tool 调用本身的成功率没到能放心让模型自己挑 tool 用的程度。

最后讲讲跟其他系列的衔接。**这一章跟 multi-agent in practice 的关系**:多 agent 系统里,tool 调用经常是"分散"的 —— 一个 agent 管一组 tool,另一个管另一组,中间通过 message 通信。如果你的 tool 数量超过 50,认真考虑按 domain 拆 agent,而不是塞给一个。

**跟 AI Evals 的关系**:tool 调用的评测是个独立子领域 —— tool selection accuracy、argument validity、end-to-end task success rate,三个不同的指标。我会在这系列后面的 evals 章节展开,包括我们那个 600 条样本的 benchmark 怎么搭的。

**跟 context-engineering 的关系**:tool 吃掉的 context 比你想的多。20 个 tool 的 schema 加起来 3-4k token,一个 50 轮对话的 tool call history 又是 2-3k,**一个 agent session 跑下来,40% 的 token 花在 tool 上**。怎么压、怎么 cache、怎么用 progressive disclosure,是 context engineering 的核心问题之一。下一章 [Memory](./05-memory.md) 我们就聊 Agent 怎么"记得" —— 包括 tool call history 怎么存,跨 session 怎么复用。

## 给工程师的两条建议

**第一,先接协议层抽象(用 LiteLLM 或 Instructor),别写裸 client**。除非你做的是 SDK 或者框架本身,否则在 client 代码上花的每一分钟都是浪费。我们组 2024 年下半年把所有裸 OpenAI/Anthropic client 都换成了 Instructor,**开发速度大概快了 1.5 倍**,bug 还少了。

**第二,把 tool 当产品做,别当 API 做**。Tool description 要反复打磨,error 要可操作,idempotency 要设计,observability 要全。我建议每个 tool 都至少有:**调用次数、成功率、p50/p95 latency、参数 validation 失败率**这四个指标,挂到你的监控里。Tool 是 Agent 的"肌肉",肌肉不好使,脑子再聪明也白搭。

工具调用这件事,2024 年还在"能不能做",2025 年已经在"怎么做得稳、做得快、做得省"。我自己的体感是,**接下来一年最值得投入精力的方向是 tool 的 reliability engineering** —— retry 策略、partial failure recovery、跨 tool 的事务一致性。这些东西教科书不教,只能在生产里摸出来。

下一章我们聊 memory —— agent 怎么跨 session、跨 tool call 记住东西。这块跟 tool 调用关系特别紧密,因为 tool call history 本身就是 memory 的一部分。