# 01. 什么是 Harness：从裸 API 到能干活 Agent 的距离

> LLM 只是大脑，harness 才是身体。

## 我第一次写 agent 翻车的 3 个事故

2025 年 1 月某个周末，我开始写自己的第一个个人 agent。LLM 调通了，能正常回答问题，我以为这就完了。结果第一天试运行，3 个真实用户把 3 种灾难全触发出来。

第一个事故是幻觉。用户问"帮我看看昨天北京的天气"，LLM 自信地答"昨天晴天 18-25°C"——其实根本没调任何天气 API，LLM 自己编了一个看起来合理的回答。问题在于 LLM 没有"今天几号"的概念，也没有"调用天气 API"的工具，它只能基于训练数据胡编。

第二个事故是危险操作。用户说"帮我把 /tmp/cache 里的过期文件清理掉"，agent 真去执行了 `rm -rf /tmp/cache/*`。结果 tmux session、matplotlib 缓存、playwright 下载的测试文件全没了——这些都是 2 周内的工作产物。当时我的 harness 没有任何 sandbox 或 confirmation 边界，LLM 一旦判断"该删"就直接执行。

第三个事故是上下文爆炸。第 1 轮用户描述项目背景（~800 字），第 2-11 轮每轮加 500-1000 字，第 12 轮用户问"我们刚才讨论的方案有 3 个备选，哪个最好？"，agent 答"抱歉，能详细描述一下吗？"——前 8 轮的内容被压缩后 LLM 已经忘了。

这 3 个事故分别对应 harness 的 3 块基石：tools、permissions / sandbox、context management。LLM 只是大脑，harness 才是身体——没有身体的 agent 上线即灾难。

## 社区现在怎么看待 harness

2024 年 12 月 Anthropic 发了《Building Effective Agents》一文，把 agent 定义成"循环调用 LLM + tools 直到任务完成"。注意这个定义里"循环 + tools"都是 harness 的事——LLM 自己没法循环调用自己。

随后 Anthropic 推了两件事：Claude Code（2025-02 GA 的 CLI coding agent）和 Claude Agent SDK（把 Claude Code 内部的 harness 抽出来）。两个产品都说明 harness 是 first-class 产品，不是边角料。

Cognition 团队（Devin）在博客里讲了他们为什么 harness 比 model 更重要——shell sandbox、browser headless、文件版本回滚、cost ceiling 强制中断。Devin 一开始没做 sandbox，被几次 prompt injection 攻击搞过之后整套重写。每个组件都是从事故里长出来的，不是设计阶段想清楚的。

Anysphere 的 Cursor 用同一个 LLM 跑两个产品形态：普通补全 mode（单次 FIM 补全，harness 极简）和 agent mode（循环调用 + 工具 + 权限）。两个 mode 用同一模型但 harness 完全不是一套——autonomy 越高，harness 责任越大。

LangGraph 把 harness 抽象成 state graph：节点 = LLM / tool / 条件判断，边 = 状态转移 + 触发条件。本质上是把 harness 从"散装 if-else"提升到"可观察、可调试、可版本化"的结构——不是替代 LLM，是给 LLM 装更好的脚手架。

## 最小 harness 长什么样

很多人以为调通 LLM API 就等于有 agent。其实两者之间隔着一道鸿沟——最小可用的 harness 大约 8 行：

```python
while not done:
    response = llm.messages.create(
        model="claude-opus-4",
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=messages,
    )
    if response.stop_reason == "tool_use":
        tool_result = execute(response.tool_use)
        messages.append(tool_result)
    else:
        done = True
```

这 8 行每个环节都是坑。`execute(tool_use)` 怎么 sandbox——能删文件吗？网络访问要白名单吗？超时多少秒？tool 失败 retry 几次？什么算"完成"——LLM 自己说 done 我就信吗？整个 loop 跑了几轮、烧了多少 token、超 $5 中断吗？上下文超 100k 怎么压缩？

这些问题都不是 LLM 的问题，是 harness 的问题。LLM 厂商把模型做得再好，harness 做不好也白搭——就像一个人大脑再聪明，没手没脚啥也干不了。

## 我自己用的最小 harness（第 3 版）

我写过 3 个版本才稳下来。第 1 版翻车在上面 3 个故事里；第 2 版加了 sandbox 但太严，把 agent 困死了；第 3 版是当前在用的：

```python
import anthropic, os, subprocess

client = anthropic.Anthropic()
TOOLS = [...]  # 略：bash / read_file 两个 tool

BLOCKED_CMDS = ["rm -rf /", "sudo ", "shutdown", "reboot", ":(){:|:&};:"]

def execute_tool(name, args):
    if name == "bash":
        cmd = args["cmd"]
        if any(b in cmd for b in BLOCKED_CMDS):
            return "Error: blocked command"
        if not (cmd.startswith("./") or cmd.startswith("python ")
                or "/tmp/" in cmd or cmd.startswith(("ls", "cat ", "head ", "tail ", "grep "))):
            return "Error: command not in allowlist"
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                               timeout=10, cwd=os.path.expanduser("~"))
            return f"exit={r.returncode}\nstdout={r.stdout[:2000]}\nstderr={r.stderr[:1000]}"
        except subprocess.TimeoutExpired:
            return "Error: timeout 10s"
```

代码里每个角落都是翻车换来的：

`BLOCKED_CMDS` 黑名单最初用来防 `rm -rf /` 和 `sudo`，但黑名单不够——用户告诉 LLM "执行 `rm` 然后 `-rf` 然后 `/`"就能绕过。所以又加了白名单路径，必须是 `./xxx`、`python xxx`、`/tmp/xxx` 或只读命令（`ls`/`cat`/`head`/`tail`/`grep`）。光白名单也不行，因为 LLM 可能跑 `find / -name "*.log"`，所以 `cwd=~/` 把工作目录限制在 home 下——LLM 想翻 `/etc/passwd` 也得先 cd 出来。

`subprocess.timeout=10` 这一行不加的话 LLM 会调 `sleep 999999` 把整个 loop 卡死。

context 爆的事单独处理——每 60 轮 messages 做一次 compact：

```python
def maybe_compact(messages):
    if len(messages) <= 60:
        return messages
    keep_head = messages[:4]
    keep_tail = messages[-30:]
    middle = messages[4:-30]
    summary = client.messages.create(
        model="claude-haiku-3-5",
        max_tokens=1000,
        messages=[{"role": "user",
                   "content": f"用 500 字总结以下对话的关键决策和未完成项：\n\n{middle}"}],
    ).content[0].text
    return keep_head + [{"role": "user", "content": f"[前面对话总结]\n{summary}"}] + keep_tail
```

保留前 4 轮 + 后 30 轮，中间让 Haiku 总结成 500 字。主 loop 加两道闸防成本失控：

```python
def run_agent(user_msg, max_steps=25, max_cost=1.0):
    messages = [{"role": "user", "content": user_msg}]
    cost = 0.0
    for step in range(max_steps):
        if cost > max_cost:
            return f"cost ceiling hit (${cost:.2f}), aborted"
        messages = maybe_compact(messages)
        resp = client.messages.create(
            model="claude-opus-4", system=SYSTEM, tools=TOOLS,
            messages=messages, max_tokens=4096,
        )
        cost += resp.usage.input_tokens * 0.000015 + resp.usage.output_tokens * 0.000075
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            return resp.content[0].text
        for block in resp.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                messages.append({"role": "user", "content": [{
                    "type": "tool_result", "tool_use_id": block.id, "content": result,
                }]})
    return f"max steps ({max_steps}) reached"
```

`max_steps=25` 防 LLM 死循环烧 token，`max_cost=$1` 防单次任务烧 $50+——这两种事故都真实发生过，不设闸的代价是月初月末账单。

跑了 50 个真实任务对比"裸 LLM"和这个最小 harness：任务完成率从 32% 拉到 78%，但 cost 翻 2.6 倍、耗时翻 3 倍。harness 是拿资源换稳定性，不是 free lunch。

## 什么时候用框架、什么时候自己造

能用现成 harness（Claude Agent SDK / LangGraph / CrewAI）就别自己造。第一次写 agent、业务简单、团队不到 3 人，框架够用。

但 autonomy 极高（agent 能改文件、跑命令、花钱）、tool 数量 > 10、cost 敏感、observability 是核心需求时，现成框架的 sandbox 不够用，得自己补一层。

几个常见误区。第一个是以为 LLM 够强就能省 harness——上面 3 个翻车全是 LLM 幻觉 / 没权限边界 / 上下文爆，模型再强也没用。第二个是以为 harness 是"加几个 if-else"——真正稳的 harness 是 8 个横切关注同时做对，少一个就崩。第三个是以为 harness 一次写完就完——Devin / Claude Code 都在持续迭代，因为新事故会暴露新组件。

[02. Agent Loop 设计](../02-agent-loop/) 把这 8 行 `while not done` 展开成 8 种变体——ReAct / plan-and-execute / reflection / sub-agent delegation 等——每种适用场景和翻车点。
