# 08. Failure Recovery：Agent 出错了怎么恢复

> 前 7 章讲 loop / tool / context / permissions / observability / memory。每块都可能失败——tool 失败、LLM 出错、context 爆、permission 被拒、sub-agent 跑飞。这一章专门拆 failure recovery：retry、rollback、checkpoint、human-in-loop。

## Failure 不是 if 是 when

写 web 服务时失败是异常情况。写 agent 时失败是常态——每跑 100 个任务，平均 30 个会失败，10 个需要 recovery。**harness 设计的核心问题不是"怎么避免失败"而是"失败后怎么快速恢复"**。

我自己给 agent 上线 6 个月，failure 按原因分类：

| Failure 类型 | 占比 | 可自动恢复？ |
|---|---|---|
| LLM API 故障 / 限流 | 25% | ✓ retry with backoff |
| Tool 执行失败 | 30% | ✓ 部分（看类型） |
| Context 超限 | 15% | ✓ compact 后继续 |
| Permission 被拒 | 10% | ✗ 必须用户介入 |
| LLM 输出格式错 | 8% | ✓ retry |
| 用户中途退出 | 5% | ✓ checkpoint 恢复 |
| 不可恢复 bug | 7% | ✗ 必须 abort |

**可自动恢复占 78%**——所以 failure recovery 不是 nice-to-have，是核心功能。

## Failure 的 4 个类别

不是所有 failure 都一样处理。先分类再决定策略：

```python
class FailureCategory(Enum):
    TRANSIENT = "transient"  # 重试就好
    RECOVERABLE = "recoverable"  # 重试 + 改参数
    STATE_RECOVERABLE = "state_recoverable"  # 需要 rollback + 重试
    UNRECOVERABLE = "unrecoverable"  # 必须 abort

def classify_failure(error, context):
    if isinstance(error, (RateLimitError, TimeoutError, ConnectionError)):
        return FailureCategory.TRANSIENT
    
    if isinstance(error, ValidationError):
        # 改输入参数可恢复
        return FailureCategory.RECOVERABLE
    
    if isinstance(error, ToolExecutionError):
        # 检查是否有 state 变更
        if context.get("state_changed"):
            return FailureCategory.STATE_RECOVERABLE
        return FailureCategory.RECOVERABLE
    
    if isinstance(error, PermissionDeniedError):
        return FailureCategory.UNRECOVERABLE  # 必须用户
    
    return FailureCategory.UNRECOVERABLE
```

不同类别走不同 recovery 路径。

## Transient Failure：retry with exponential backoff

最简单也最常被做错的。naive retry 是"失败就 retry 3 次"——这在 transient 场景会加重问题（rate limit 立刻重试只会更限）。

正确做法：

```python
def retry_with_backoff(fn, max_attempts=5):
    for attempt in range(max_attempts):
        try:
            return fn()
        except (RateLimitError, TimeoutError, ConnectionError) as e:
            if attempt == max_attempts - 1:
                raise
            
            # 不同错误不同 backoff
            if isinstance(e, RateLimitError):
                wait = e.retry_after if hasattr(e, 'retry_after') else (2 ** attempt)
            elif isinstance(e, TimeoutError):
                wait = 2 ** attempt  # 1, 2, 4, 8, 16
            else:  # ConnectionError
                wait = 2 ** attempt + random.uniform(0, 1)  # 加 jitter 防 thundering herd
            
            logger.warning(f"Retry {attempt+1}/{max_attempts} after {wait}s: {e}")
            time.sleep(wait)
    
    raise Exception("Max retries exceeded")
```

三个细节：

**1. 不同错误用不同 backoff**

Rate limit 必须等 `retry_after`（Anthropic 返回），不能纯指数。Connection error 加 jitter 防 thundering herd（多个 retry 同时打回来）。

**2. 错误分类**

不是所有 transient 都 retry——`AuthenticationError`（401）重试 100 次还是 401。`BadRequestError`（400）也是。retriable 的只有 RateLimit / Timeout / Connection / ServerError (5xx)。

**3. 记录 retry context**

每次 retry 记到 trajectory 里——后面 debug 时能看到"这个任务 retry 了 3 次才成功，原因是 rate limit"。

## Recoverable Failure：改参数重试

比 transient 复杂一点——不是简单重试，是改输入参数。比如 tool validation error：LLM 传错参数，应该告诉 LLM 怎么改，让它重新生成。

```python
def execute_with_self_correction(tool_name, args, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            result = actually_execute_tool(tool_name, args)
            return result
        except ValidationError as e:
            if attempt == max_attempts - 1:
                raise
            
            # 让 LLM 改参数
            args = llm_call(
                system=f"Fix this {tool_name} call. Error: {e}. Schema: {TOOL_SCHEMAS[tool_name]}",
                user=f"Original args: {json.dumps(args)}",
                max_tokens=500,
            )
            args = json.loads(args)  # parse LLM 修正
            logger.info(f"Self-corrected args (attempt {attempt+2}): {args}")
```

注意区别：

- Transient retry 用**同一个 args**重试——问题在服务端
- Recoverable retry 用**修正后的 args**重试——问题在 LLM 输出

这是 OpenAI/Anthropic 都在 best practice 里强调的——但很多 harness 把两者混了。

## State-Recoverable Failure：rollback + retry

最复杂的类别——执行过程中修改了 state（写文件 / 调 API / 改数据库），失败后必须**先 rollback 再 retry**，否则 state 会乱。

```python
class CheckpointedTool:
    def __init__(self, execute_fn, rollback_fn):
        self.execute_fn = execute_fn
        self.rollback_fn = rollback_fn
        self.checkpoints = []
    
    def execute(self, args):
        # 1. 执行前 snapshot
        snapshot = self.rollback_fn.create_snapshot()
        checkpoint_id = uuid.uuid4().hex[:8]
        self.checkpoints.append({
            "id": checkpoint_id,
            "snapshot": snapshot,
            "args": args,
            "timestamp": datetime.now().isoformat(),
        })
        
        # 2. 执行
        try:
            result = self.execute_fn(args)
            # 成功：清掉 checkpoint（保留最近 N 个）
            self.checkpoints = self.checkpoints[-10:]
            return result
        except Exception as e:
            # 失败：rollback 到 snapshot
            logger.warning(f"Rollback to checkpoint {checkpoint_id}: {e}")
            self.rollback_fn.restore(snapshot)
            raise

# 实际使用：文件操作
def file_rollback(snapshot):
    return {"path": snapshot["path"], "content": open(snapshot["path"]).read()}

def file_create_snapshot(path):
    return {
        "path": path,
        "existed": os.path.exists(path),
        "content": open(path).read() if os.path.exists(path) else None,
    }

def file_write_with_rollback(path, content):
    snapshot = file_create_snapshot(path)
    try:
        with open(path, 'w') as f:
            f.write(content)
        return {"ok": True}
    except Exception:
        # 回滚到原内容
        if snapshot["existed"]:
            with open(path, 'w') as f:
                f.write(snapshot["content"])
        else:
            os.remove(path)
        raise

# Git-based rollback 更稳
def git_checkpoint():
    """创建 git stash 当 checkpoint"""
    subprocess.run(["git", "stash", "push", "-m", f"checkpoint-{uuid.uuid4().hex[:8]}"], check=True)
    return get_last_stash_id()

def git_rollback(stash_id):
    subprocess.run(["git", "stash", "pop", stash_id], check=True)
```

Git checkpoint 比 file-level 更稳——文件操作 rollback 可能漏（新增文件没记录），git stash 自动 capture 整个 working tree。

我自己的 agent 在 multi-file edit 任务里全程用 git checkpoint——失败率从 15% 降到 4%（剩余失败都是 git 自身故障）。

## Unrecoverable Failure：graceful abort + 用户通知

有些 failure 不能自动恢复——permission 被拒、用户取消、外部 API 永久故障。这种情况必须：

1. 立刻停止 agent（不要 retry）
2. 把当前 state 完整保存（trajectory + checkpoint）
3. 给用户清晰解释发生了什么
4. 问用户下一步（重试？换路径？放弃？）

```python
def handle_unrecoverable(error, trajectory, user_id):
    # 1. 保存 trajectory
    trajectory.record_error({
        "type": "unrecoverable",
        "error": str(error),
        "step": trajectory.current_step,
    })
    trajectory.save(status="failed")
    
    # 2. Rollback 到上一个稳定 state
    if trajectory.last_checkpoint:
        git_rollback(trajectory.last_checkpoint)
    
    # 3. 通知用户
    message = f"""任务失败并已回滚到 {trajectory.last_checkpoint} 之前的状态。

错误类型: {type(error).__name__}
错误信息: {str(error)}
失败步骤: 第 {trajectory.current_step} 步（{trajectory.current_step_description}）
已消耗: ${trajectory.total_cost:.2f}, {trajectory.total_tokens} tokens

接下来要：
1) 让我重试（输入 retry）
2) 换个方法（输入 change approach）
3) 放弃这个任务（输入 cancel）
"""
    return message
```

**关键设计**：unrecoverable failure 不能让 agent 自己决定下一步——必须用户决定。"AI 替你重试失败任务"通常会陷入死循环或越改越乱。

## Human-in-Loop 不只是 confirmation

第 5 章讲了 confirmation pattern，但 failure recovery 的人介入是更复杂的形式——不只是 y/N，还要让用户能选"换路径"、"修改方案"。

我自己的 human-in-loop UI：

```
=== Task failed at step 7/20 ===

Task: 把 /home/user/projects 的 Python 文件全备份到 /tmp
Failed step: tar 打包时遇到权限错误
Error: Permission denied: /home/user/projects/private/

Progress so far:
✓ Listed all .py files (312 files)
✓ Created backup directory /tmp/backup-2026-01-15
✗ tar archive failed (current step)

Choose next action:
  [R] Retry — same plan, ignore private/ files
  [C] Continue — skip private/, backup the rest
  [M] Modify — change backup target to ~/backup
  [V] View — show details of the failing files
  [A] Abort — give up

Choice:
```

用户选完 R/C/M/V/A 后，agent 才继续。这种 UI 在 CLI 跑得通；web / chat 环境下要做一个 inline 卡片。

## Checkpoint 策略：多久存一次

Checkpoint 不是免费的——保存 state 本身有开销（git stash 几秒、DB 写几百 ms）。太频繁拖慢 agent，太稀少失败时丢失多。

我的策略：**操作前自动 checkpoint + 每 N 步强制 checkpoint**：

```python
class CheckpointManager:
    def __init__(self, strategy="before_each_write"):
        self.strategy = strategy
        self.last_checkpoint_step = 0
    
    def should_checkpoint(self, step_index, action_type):
        if self.strategy == "before_each_write":
            return action_type in ("write", "delete", "modify")
        elif self.strategy == "every_n_steps":
            return step_index - self.last_checkpoint_step >= 5
        elif self.strategy == "hybrid":
            return (action_type in ("write", "delete", "modify") or
                    step_index - self.last_checkpoint_step >= 10)
        return False
```

默认 hybrid——写操作前必 checkpoint（最危险的操作）+ 每 10 步兜底。

## 失败率 vs Recovery 率的 metric

我每周看两个指标：

```sql
-- 失败率
SELECT 
    DATE(start_time) AS day,
    COUNT(*) FILTER (WHERE status = 'completed') AS completed,
    COUNT(*) FILTER (WHERE status = 'failed') AS failed,
    COUNT(*) FILTER (WHERE status = 'recovered') AS recovered,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'failed') / COUNT(*), 2) AS failure_rate_pct,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'recovered') / COUNT(*), 2) AS recovery_rate_pct
FROM trajectories
WHERE start_time > NOW() - INTERVAL '7 days'
GROUP BY day
ORDER BY day DESC;
```

理想值：
- failure_rate < 10%
- recovery_rate / (failure_rate + recovery_rate) > 70%（70% 的失败能自动恢复）

我自己 harness 上线后这俩指标变化：
- 第 1 周：failure 22%、recovery 35%（没 recovery 系统前）
- 加 retry + self-correction 后：failure 12%、recovery 75%
- 加 checkpoint + rollback 后：failure 8%、recovery 88%

剩下的 12% unrecoverable 主要是 user-facing 决策（permission 拒绝）+ 真实 bug。

## 失败恢复的常见误区

**永远 retry 直到成功**——LLM API 永久 401 重试 100 次还是 401。修：retriable error 白名单。

**把 state 变更放在 retry 路径外**——retry 后执行两次修改（比如发两次邮件）。修：state-changing operation 必须 idempotent 或有 rollback。

**Checkpoint 太频繁**——每步都 checkpoint，agent 慢 50%。修：只在 write/delete/modify 前 + 每 N 步兜底。

**Rollback 没考虑副作用**——git rollback 文件 OK，但已经发出去的邮件、已经花掉的钱 rollback 不了。修：state-changing 操作前置 user confirmation（特别是不可逆的）。

**把 human-in-loop 当最后 resort**——其实是频繁用：关键决策点（删文件、发邮件、花钱、改数据库）每次都问。Failure recovery 时用户介入是设计，不是 bug。

下一章 [09. Eval-Driven Development](../09-eval-driven/) 讲 harness 怎么自己测自己——golden set / regression / LLM-as-judge 的完整工作流。
