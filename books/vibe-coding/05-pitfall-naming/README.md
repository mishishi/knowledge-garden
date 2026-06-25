# 05. 真坑 2：字段命名 / 规范割裂

2026 年 3 月，我带后端小组用 Claude Code 开发物流追踪系统（代号 LOGISTICS_V2），20+ 个 Flask REST 接口全 vibe coding。**第 12 天前端同事冲进会议室："接口字段全部 undefined。"**

排查三天才发现：AI 生成的 20 个接口里，**有 11 个返回下划线字段，9 个返回驼峰字段**。原因是项目数据库字段是下划线命名（user_id, logistics_code），AI 在有些接口里加了 `snake_to_camel` 转换、有些没加，前端解析时一半成功一半失败。

Claude Code 纯终端模式**没有"全局代码规范预览"**，每个接口单独生成时 AI 不会记得别的接口怎么写的。批量生成越多，规范割裂越严重。

## 为什么 vibe coding 特别容易踩

跟 N+1 不同，字段命名的问题**测试环境看不出来**——每个接口单独测都能拿到数据，只是字段格式不同。前端单独调一个接口也能拿到值。只有多接口联调时才暴露。

AI 不是故意的，它**真不记得 5 分钟前写的另一个文件**。Claude Opus 4.7 的 context window 200K token，但你一个项目几十个文件，单个文件 5K 行，AI 在 vibe 时只能扫它自己刚写的那个，根本没法做"全局规范对齐"。

## 三个解法叠着用

**第一，口述需求模板里写死规范**：

```
命名约束：
- DB 字段下划线（snake_case）
- API 返回驼峰（camelCase）
- 所有 DB 返回必须经过 utils.format_util.snake_to_camel 统一转换
- 转换函数路径：utils/format_util.py（项目已有，禁止重新实现）
```

**第二，口述"先建工具再写业务"**：

> "在写接口前先确认项目已有 utils/format_util.py（snake_to_camel / camel_to_snake），所有接口必须调用。如果没有先建。"

AI 会先 `cat utils/format_util.py` 看一眼，确认工具存在，然后所有接口统一调用。**这一条能解决 90% 的字段割裂**。

**第三，commit 前跑一遍全局校验脚本**：

我自己写了个 Python 脚本扫所有路由文件：

```python
import ast, pathlib
issues = []
for f in pathlib.Path("routes").rglob("*.py"):
    tree = ast.parse(f.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Return):
            # 检查返回值有没有经过 snake_to_camel
            if not _passes_through_converter(node.value):
                issues.append(f"{f}:{node.lineno} return without snake_to_camel")
print(f"{len(issues)} issues found")
for i in issues[:10]:
    print(i)
```

每次 commit 前跑一遍。**0 个 issue 才能 commit**。

## TRAE 怎么破这个局

TRAE 的 IDE 模式（不是 Work 模式）有**项目级代码索引**——字节内部百万行级代码验证过的能力。AI 在生成新接口前会扫一遍项目已有接口的命名风格，自动对齐。

这是 TRAE 比 Claude Code 在 vibe coding 场景下**最关键的胜场**。Claude Code 纯终端无索引，N 个文件生成 N 种风格；TRAE IDE 有索引，N 个文件生成 1 种风格。

我用 Claude Code 写 LOGISTICS_V2 时是 20 接口 11 下划线 9 驼峰。换 TRAE 重写同样需求，20 接口全驼峰，零割裂。

## 校验工具清单

我自己 vibe coding 每个项目都贴这份：

```
规范校验清单：
- API 返回字段必须统一（驼峰/下划线二选一，全项目一致）
- 所有 DB 层返回必须经过统一转换函数（禁止散落各文件）
- 错误返回必须走全局 ExceptionFilter（禁止 try/except 后 return 自定义格式）
- 日志格式统一（time | level | traceId | msg）
- 数据库事务边界统一（service 层管事务，controller 不管）
```

5 行。贴到 AI 对话开头。

下一章讲第三个真坑——安全 / 鉴权 / 密钥硬编码，这个能直接造成线上事故。