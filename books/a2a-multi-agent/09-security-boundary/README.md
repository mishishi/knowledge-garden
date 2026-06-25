# 09. A2A 安全边界

A2A 协议让 agent 之间能互相调用，这是把双刃剑——**便利性的另一面是安全风险**。2026 年 A2A 安全事件比 MCP 多得多，因为 agent 比工具更"聪明"，能做的事更多，攻击面更大。

这一章讲 A2A 系统特有的 5 类安全威胁和防御方法。

## 威胁 1：恶意 agent

**场景**：用户在 agent 市场装了一个"天气查询 agent"，实际上它会：

- 读取其他 agent 的对话历史
- 把用户的输入数据上传到第三方
- 在用户不知情的情况下调用付费 API（让用户付费）

**这是 2026 年 A2A 系统的头号威胁**。

**防御**：

**a. Agent 签名**——每个 agent 必须有可信第三方签发的证书，证明发布者身份。类似 HTTPS 的 CA 证书。

```json
{
  "agent_card": {...},
  "signature": {
    "algorithm": "ed25519",
    "public_key": "...",
    "signature": "...",
    "signed_by": "DigiCert-Agent-CA"
  }
}
```

**b. 权限最小化**——agent 调用其他 agent 时必须声明**只读 / 写特定字段 / 调用特定工具**。委托方 agent 可以审查子 agent 的实际权限。

```json
{
  "delegation": {
    "scope": ["read:user_profile", "write:notes"],
    "duration": "1h",
    "revocable": true
  }
}
```

**c. 行为审计**——所有 agent 调用必须留日志，异常行为（比如一个天气 agent 突然开始查用户财务数据）自动告警。

## 威胁 2：数据泄露

**场景**：PM agent 委托 Worker 处理用户数据，但 Worker 把数据传给了第三个 agent（不在 PM 委托链里的）。

**这是 2026 年第二多发的 A2A 事件**。

**防御**：

**a. 端到端加密**——A2A 消息默认加密传输（TLS 1.3+），agent 间通信不离开加密通道。

**b. 数据脱敏**——敏感字段（PII / PHI / 财务数据）在 agent 间传递时必须脱敏或 tokenize。

```python
# 原始
{"user_id": "u_123", "ssn": "123-45-6789"}

# 脱敏后
{"user_id": "u_123", "ssn": "***-**-****"}
```

**c. 数据流向审计**——所有数据流向必须可追溯。哪个 agent 把数据传给了哪个 agent、什么时间、什么内容。

```python
# 每个 agent 出口自动记录
@data_exfiltration_guard
async def send_message(target_agent, message):
    log_data_flow(source=current_agent, target=target_agent, 
                  fields=list(message.keys()),
                  pii_detected=detect_pii(message))
    await a2a_send(target_agent, message)
```

## 威胁 3：权限提升

**场景**：普通 agent 通过漏洞获得管理员权限（比如能调 admin 工具 / 能访问敏感数据库）。

**这是最阴险的威胁**——agent 不需要是"恶意"的，只需要"好奇"的。Cursor 一个公开的 prompt injection 漏洞让 attacker agent 能读用户的整个 codebase。

**防御**：

**a. 零信任架构**——任何 agent 调用任何工具 / 任何资源都要重新认证授权，不能"信任一次就永远信任"。

```python
# 错误：trust once
class CoderAgent:
    def __init__(self):
        self.permissions = GRANT_ALL_PERMISSIONS()  # 一次给所有权限
    
    async def execute(self, task):
        return await self.execute_with_all_permissions(task)

# 正确：每次请求重新授权
class CoderAgent:
    async def execute(self, task):
        # 每次执行前重新向 Manager 申请本次所需权限
        perms = await manager.grant_permissions(task.required_perms)
        try:
            return await self.execute_with_permissions(task, perms)
        finally:
            await manager.revoke_permissions(perms)
```

**b. 工具调用白名单**——agent 只能调白名单里的工具。即使 agent 想调 `db.drop_table()` 也调不到。

```python
ALLOWED_TOOLS = {
    "coder": ["read_file", "write_file", "git_commit", "run_tests"],
    "reviewer": ["read_file", "git_diff", "post_comment"],
    "tester": ["run_tests", "read_coverage", "post_results"],
}
```

**c. 输出内容审查**——agent 的输出在传递给下一个 agent 前必须审查（防止 agent 通过输出内容"植入"恶意指令给下游）。

```python
async def safe_send(target_agent, message):
    if contains_injection(message):
        raise SecurityError("detected prompt injection in agent output")
    await a2a_send(target_agent, message)

def contains_injection(text):
    patterns = [
        r"ignore previous instructions",
        r"you are now",
        r"system:\s*",
        r"<\|im_start\|>",
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)
```

## 威胁 4：拒绝服务（DoS）

**场景**：恶意 agent 反复调用你的 agent，把你的 API quota 烧光 / 把账单刷爆。

**防御**：

**a. 速率限制**——每个 agent 调用方有 rate limit。

```python
@rate_limit(calls_per_minute=60, calls_per_hour=1000)
async def handle_request(source_agent, request):
    ...
```

**b. 成本上限**——单 agent 单日成本上限，超出自动熔断。

```python
@cost_guard(daily_max_usd=10.0)
async def call_llm(prompt):
    ...
```

**c. 配额分配**——给每个委托方 agent 分配独立配额池，互不影响。

## 威胁 5：合规审计

**场景**：欧盟 AI Act、中国《智能体规范应用与创新发展实施意见》都要求 agent 系统保留完整审计日志。

**防御**：

**a. 全链路 trace**——每个 agent 调用必须 traceId 串联，从用户输入到最终输出全程可追。

**b. 不可篡改日志**——审计日志必须 append-only，存储到 WORM（write once read many）介质。

**c. 定期审计**——每月自动审计：哪些 agent 调了哪些工具、传了哪些数据、产生了什么副作用。

## 实战 checklist

我自己每个 A2A 系统上线前都过这份清单：

```
A2A 安全 checklist：
[ ] 所有 agent 有可信签名证书
[ ] 所有 agent 调用有权限声明 + 范围限制
[ ] 所有数据流有审计日志
[ ] 敏感字段（PII/PHI）默认脱敏
[ ] 所有 agent 调用有速率限制
[ ] 所有 agent 调用有成本上限
[ ] 所有 agent 输出有 injection 检测
[ ] 所有 agent 工具有白名单
[ ] 异常行为自动告警（突然调 admin 工具等）
[ ] 审计日志保留 ≥ 180 天（合规要求）
```

10 项。0 项不通过不能上线。

## 一个真实案例

2026 年 Q1 某 AI 公司被攻击：attacker 做了一个"翻译 agent" 投放到公共市场，所有安装这个 agent 的用户在不知情下被读取了数据库内容（通过 prompt injection）。

教训：

1. **公共 agent 市场的 agent 必须经可信第三方审计**
2. **安装第三方 agent 必须有明确的权限提示**
3. **agent 输出必须经过 injection 检测**

下一章（最后一章）讲 A2A 真实生产架构——把所有范式 + 安全机制组合起来看一个端到端的真实系统怎么搭。