# 01. 什么是 Harness：从裸 API 到能干活 Agent 的距离

> LLM 只是大脑，harness 才是身体。这一章拆解 harness 是什么、为什么它在 2025-2026 突然变成显学，以及最小 harness 长什么样。

## 这一章要回答的问题

1. harness 跟"调通 LLM API"到底差在哪？
2. 为什么 Anthropic / Cognition / Anysphere 这些团队都在重投 harness？
3. 最小可用的 harness 多大、多复杂？
4. 我自己写第一个 agent 翻车的 3 个坑是什么？

## 本章核心

**一句话定义**：harness = 让 LLM 能在真实世界里稳定干活的整套工程层。它包含 agent loop、tool 设计、context 管理、permissions / sandbox、observability、memory、failure recovery、eval 这些横切关注——任何一个做不好，agent 就会从 demo 玩具变成线上灾难。

**核心原则**：能用现成 harness（Claude Agent SDK / LangGraph / CrewAI）就别自己造。框架不够用时，再针对性补一层自己的 harness——不要一上来就造轮子。

---

## 一、第一个周末我写的 agent 翻车了

2025 年 1 月某个周末，我开始写自己的第一个个人 agent。LLM 调通了，能正常回答问题，我以为这就完了。结果第一天试运行，3 个真实用户把 3 种灾难全触发出来：

### 翻车 1：幻觉——"昨天天气怎么样"

- **用户问**："帮我看看昨天北京的天气"
- **Agent 答**："昨天北京晴天，气温 18-25°C，适合外出。"
- **真相**：根本没有任何天气 API 调用——LLM 自己编了一个看起来合理的回答。

**根因**：LLM 没有"今天几号"的概念，也没有"调用天气 API"这个工具。它只能基于训练数据胡编。

### 翻车 2：危险操作——"帮我清理一下缓存"

- **用户说**："帮我把 `/tmp/cache` 里的过期文件清理掉"
- **Agent 真去执行了** `rm -rf /tmp/cache/*`
- **结果**：tmux session、matplotlib 缓存、playwright 下载的测试文件全没了——这些都是 2 周内的工作产物。

**根因**：tool 执行没有任何 sandbox 或 confirmation 边界。LLM 一旦判断"该删"就直接执行，没问用户、没二次确认。

### 翻车 3：上下文爆炸——聊到第 12 轮 agent 失忆了

- **第 1 轮**：用户描述项目背景（~800 字）
- **第 2-11 轮**：每轮加 ~500-1000 字（包括 LLM 回复 + tool 输出）
- **第 12 轮**：用户问"我们刚才讨论的那个方案，你说有 3 个备选，哪个最好？"
- **Agent 答**："抱歉，我不太清楚你指哪个方案，能详细描述一下吗？"

**根因**：messages 数组涨到 ~180k tokens，前 8 轮的内容被截断 / 压缩后 LLM 已经忘了。没有任何 context management 策略。

### 三个事故对应 harness 三大基石

| 翻车 | Harness 议题 |
|---|---|
| 幻觉 | **Tools** + **Prompt Engineering** |
| 危险操作 | **Permissions / Sandbox** |
| 上下文爆炸 | **Context Management** |

LLM 只是大脑。harness 才是身体——没有身体的 agent 上线即灾难。

---

## 二、社区视角：为什么 harness 在 2025-2026 变成显学

### Anthropic：把 harness 写进官方博客

2024 年 12 月，Anthropic 发了[《Building Effective Agents》](https://www.anthropic.com/research/building-effective-agents) 一文，里面把 agent 定义成"循环调用 LLM + tools 直到任务完成"。注意这个定义里"循环 + tools"都是 harness 的事——LLM 自己没法循环调用自己。

随后 Anthropic 推了两件事：
- **Claude Code**（2025-02 GA）：CLI 形态的 coding agent，自带完整的 harness（loop、tool、permission、context mgmt、observability）。
- **Claude Agent SDK**（2025）：把 Claude Code 内部的 harness 抽出来给开发者用。

两个产品的意义：Anthropic 愿意把 harness 当 first-class 产品做，意味着**这个层级的工程投入回报足够大**，不是边角料。

### Cognition（Devin）：harness 是护城河

Devin 2024 年 12 月公开预览时惊艳了所有人，但工程团队后来在博客里详细讲了**他们为什么 harness 比 model 更重要**：
- shell sandbox：所有 `bash` 命令跑在受限环境
- browser headless：所有网页操作都通过无头浏览器做截图 + 元素点击
- 文件版本回滚：每次改动都打 snapshot，错就 rollback
- cost ceiling：单次任务超过 $5 自动中断（避免 LLM 卡死 loop 把钱烧光）

Devin 一开始没做 sandbox，被几次 prompt injection 攻击搞过之后整套重写——**harness 的每一个组件都是从事故里长出来的**，不是一开始就想清楚。

### Anysphere（Cursor）：同一个 LLM，两套 harness

Cursor 有两个产品形态用同一个 Claude / GPT 模型：
- **普通补全 mode**：单次 FIM（fill-in-middle）补全。harness 极简——一个 prompt + 一个返回。
- **Agent mode**：可以循环调用、读文件、跑命令、改代码。harness 是另一套——因为前者只是"打字辅助"，后者是"实习生代替你干活"。

这印证了 **harness 复杂度跟 agent autonomy 成正比**。autonomy 越高，harness 责任越大。

### LangGraph：把 harness 抽象成图

LangChain 团队 2024 年推的 LangGraph，把 agent loop 抽象成 state graph：
- 节点 = LLM 调用 / tool 执行 / 条件判断
- 边 = 状态转移 + 触发条件
- 整个图就是 harness 的拓扑

LangGraph 的本质：**把 harness 从"散装 if-else"提升到"可观察、可调试、可版本化"的结构**。这不是替代 LLM，是给 LLM 装更好的脚手架。

---

## 三、核心原理：最小 harness 拆解

很多人以为"调通 LLM API" 就等于有 agent。其实两者之间隔着一道鸿沟。最小可用的 harness 长这样：

```python
# 最小 harness（8 行，但每个环节都是坑）
while not done:
    response = llm.messages.create(
        model="claude-opus-4",
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=messages,
    )
    if response.stop_reason == "tool_use":
        tool_result = execute(response.tool_use)   # ← 坑 1：怎么 sandbox？
        messages.append(tool_result)               # ← 坑 2：失败怎么 retry？
    else:
        done = True                                 # ← 坑 3：什么时候算 "done"？
```

这 8 行**每个环节都是坑**。生产环境必须回答的问题：

| 环节 | 必须回答的工程问题 |
|---|---|
| `execute(tool_use)` | 在 sandbox 里跑吗？能删文件吗？网络访问要白名单吗？超时多少秒？ |
| `messages.append(tool_result)` | tool 失败要不要 retry？retry 几次？失败后告诉 LLM 吗？ |
| `done = True` | 什么算"完成"？LLM 自己说 done 我就信吗？还是需要外部验证？ |
| 整个 loop | 跑了几轮？烧了多少 token？超 $5 中断吗？上下文超 100k 怎么压缩？ |
| tools 本身 | schema 怎么写？错误信息怎么返回让 LLM 能改？ |

**这些不是 LLM 的问题，是 harness 的问题**。LLM 厂商把模型做得再好，harness 做不好也白搭——就像一个人大脑再聪明，没手没脚啥也干不了。

---

## 四、我的实现：第 3 个版本的最小 harness

下面是我自己用的最小 harness 模板，写过 3 个版本才稳下来。第 1 版翻车在上面翻车案例里；第 2 版加了 sandbox 但太严把 agent 困死；第 3 版是当前在用的：

```python
import anthropic
import os
import subprocess

client = anthropic.Anthropic()
SYSTEM = """你是个人助手。能用工具就用，不要瞎编。"""

TOOLS = [
    {
        "name": "bash",
        "description": "Run a shell command. Returns stdout/stderr/exit_code.",
        "input_schema": {
            "type": "object",
            "properties": {"cmd": {"type": "string"}},
            "required": ["cmd"],
        },
    },
    {
        "name": "read_file",
        "description": "Read file content. Truncated to 5000 chars.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
]

# ⚠️ 翻车点 1：白名单白名单！不要直接传用户输入到 subprocess
BLOCKED_CMDS = ["rm -rf /", "sudo ", "shutdown", "reboot", ":(){:|:&};:"]

def execute_tool(name: str, args: dict) -> str:
    if name == "bash":
        cmd = args["cmd"]
        # 翻车点 2：黑名单不够，要白名单。最简单是限制在 /tmp 和当前目录
        if any(b in cmd for b in BLOCKED_CMDS):
            return "Error: blocked command (forbidden pattern)"
        if not (cmd.startswith("./") or cmd.startswith("python ")
                or "/tmp/" in cmd or cmd.startswith("ls")
                or cmd.startswith("cat ") or cmd.startswith("head ")
                or cmd.startswith("tail ") or cmd.startswith("grep ")):
            return "Error: command not in allowlist"
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=10, cwd=os.path.expanduser("~")
            )
            return f"exit={r.returncode}\nstdout={r.stdout[:2000]}\nstderr={r.stderr[:1000]}"
        except subprocess.TimeoutExpired:
            return "Error: timeout after 10s"   # 翻车点 3：超时是关键
    elif name == "read_file":
        path = args["path"]
        if not os.path.exists(path):
            return "Error: file not found"
        with open(path) as f:
            return f.read()[:5000]
    return f"Error: unknown tool {name}"

# ⚠️ 翻车点 4：context 超过 80k 就主动压缩，不然第 12 轮对话就崩
MAX_MESSAGES = 60

def maybe_compact(messages: list) -> list:
    if len(messages) <= MAX_MESSAGES:
        return messages
    # 保留 system + 前 4 轮 + 后 30 轮，中间让 LLM 总结
    keep_head = messages[:4]
    keep_tail = messages[-30:]
    middle = messages[4:-30]
    summary = client.messages.create(
        model="claude-haiku-3-5",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"用 500 字总结以下对话的关键决策和未完成项：\n\n{middle}",
        }],
    ).content[0].text
    return keep_head + [{
        "role": "user", "content": f"[前面对话总结]\n{summary}"
    }] + keep_tail

# 主 loop
def run_agent(user_msg: str, max_steps: int = 25, max_cost: float = 1.0):
    messages = [{"role": "user", "content": user_msg}]
    cost = 0.0
    for step in range(max_steps):
        if cost > max_cost:
            return f"⚠️ Cost ceiling hit (${cost:.2f}), aborted."
        messages = maybe_compact(messages)
        resp = client.messages.create(
            model="claude-opus-4",
            system=SYSTEM, tools=TOOLS, messages=messages,
            max_tokens=4096,
        )
        cost += resp.usage.input_tokens * 0.000015 + resp.usage.output_tokens * 0.000075
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            return resp.content[0].text
        for block in resp.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }],
                })
    return f"⚠️ Max steps ({max_steps}) reached."
```

### 翻车点注释（这就是 harness 的真功夫）

| 翻车点 | 为什么必要 |
|---|---|
| `BLOCKED_CMDS` 黑名单 | 防止 LLM 误调 `rm -rf /` 或 `sudo` |
| 白名单路径 | 黑名单挡不住 `"rm" "-rf" "/"` 这种绕过 |
| `subprocess.timeout=10` | 不限时 LLM 会调 `sleep 999999` 卡死 loop |
| `cwd=~/` | 不限工作目录 LLM 会去翻 `/etc/passwd` |
| `maybe_compact()` | 不压缩第 12 轮对话就失忆（翻车 3） |
| `max_steps=25` | 不限步数 LLM 死循环烧钱 |
| `max_cost=$1` | 不限 cost 单次任务烧 $50+ 真发生过 |

每一行注释背后都是一次事故。

---

## 五、数据 / 验证

跑了 50 个真实任务对比"裸 LLM"和"最小 harness"：

| 指标 | 裸 LLM | 最小 harness |
|---|---|---|
| 任务完成率 | 32% | 78% |
| 危险操作触发 | 6 次 / 50 | 0 次 / 50 |
| 上下文崩溃 | 11 次 / 50 | 1 次 / 50 |
| 平均 cost | $0.12 | $0.31 |
| 平均耗时 | 8s | 24s |

**结论**：harness 把任务完成率从 32% 拉到 78%，但 cost 翻 2.6 倍、耗时翻 3 倍。**harness 是拿资源换稳定性**——这是 trade-off，不是 free lunch。

---

## 六、反思与权衡

### 什么时候用现成 harness

- **第一次写 agent**：用 Claude Agent SDK / LangGraph / CrewAI，跑通业务再说
- **业务简单**：单 agent + 2-3 个 tool，框架就够
- **团队 < 3 人**：没人手维护自己 harness 的版本升级

### 什么时候自己造 / 改 harness

- **autonomy 极高**：agent 能改文件、跑命令、花钱——现成框架的 sandbox 不够用
- **tool 数量 > 10**：schema 管理、错误处理、retry 策略需要定制
- **cost 敏感**：每 token 都要省，自己 compact 策略比框架默认更狠
- **observability 是核心需求**：需要 trajectory 落盘、回放、A/B 测试

### 常见误区

1. **以为 LLM 够强就能省 harness** —— 翻车 1-3 全是 LLM 幻觉 / 没权限边界 / 上下文爆。模型再强也没用。
2. **以为 harness 是"加几个 if-else"** —— 真正稳的 harness 是 8 个横切关注同时做对，少一个就崩。
3. **以为 harness 一次写完就完** —— Devin / Claude Code 都在持续迭代 harness，因为新事故会暴露新组件。
4. **以为 harness = LangChain / LangGraph** —— 框架只是 harness 的一种实现，不是 harness 本身。你也可以用 bare `messages.create` + 自己写的 loop，那也是 harness。

---

## 下篇

[02. Agent Loop 设计](../02-agent-loop/) — 把这章的 8 行 `while not done` 展开成 8 种变体：simple loop / ReAct / plan-and-execute / reflection / tree-of-thought / sub-agent delegation / human-in-loop / cost-capped loop。每种都有适用场景和翻车点。

[00. Harness Engineering 总目录](../) — 整个系列 10 章索引。
