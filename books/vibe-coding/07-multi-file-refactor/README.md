# 07. 多文件联动 / 全局重构

vibe coding 处理单文件 bug 没问题，但碰到**跨文件修改**就开始掉链子。AI 默认只看到自己刚写的代码，看不到整个项目的依赖图。

2026 年 3 月 LOGISTICS_V2 项目收尾时，老板让我把整个项目从 Flask + SQLAlchemy 1.4 升级到 2.0。SQLAlchemy 2.0 把 `Query` 类砍了，所有 `Model.query.filter_by()` 改成 `select(Model).where()`。我让 Claude Code vibe 改这个升级。

**结果**：改了 4 个文件，新功能跑通了，但其他 16 个文件没改——AI 在 vibe 模式下不会主动扫整个项目找"还需要改的地方"。上线的时候 16 个老接口全部 500 报错。

这次踩坑让我意识到：**vibe coding 处理跨文件修改有 4 个套路**，挨个用一遍才稳。

## 套路 1：先让 AI 自己扫一遍

口述需求模板里写：

> "扫描 src/ 目录下所有 .py 文件，列出所有使用 SQLAlchemy 1.x 旧 API（query / Query / session.query）的位置（文件:行号）。不要修改任何代码，只列清单。"

AI 会先 `grep -rn "session.query\|\.query\(" src/` 然后给你列一份清单。**拿到清单再决定改的顺序**。

这个套路适用任何"全局替换"场景：变量改名、API 升级、依赖替换、lint 规则统一。

## 套路 2：让 AI 画依赖图

口述需求：

> "用 `find src -name '*.py' | xargs grep -l 'session.query'` 找出所有相关文件，然后画一个依赖图：哪个文件 import 哪个，被改的公共函数有哪些调用方。先输出图（mermaid 或纯文本都行），再开始改。"

依赖图出来后，**先改底层（被依赖最多的），再改上层**。这样不会出现"改到一半引用断了"的中间态。

LOGISTICS_V2 那次如果先画依赖图，我会发现 11 个文件 import `BaseModel`，2 个文件定义了 `BaseModel`，AI 在 vibe 时改了其中 1 个定义文件的 API 但没改另一个，导致运行时找不到方法。

## 套路 3：分批改 + 每批跑测试

不要让 AI "一次性把整个项目升完"，让它分批：

> "第一批：只改 src/db/ 目录下的 5 个文件，改完跑 pytest tests/db/ 看是否通过。通过后再继续。第二批：改 src/services/ 下 12 个文件，跑 pytest tests/services/。以此类推。"

每批独立 commit、独立测试、独立回退。AI 改坏了不至于整个项目挂掉。

我现在的规矩：**单次 vibe 改动不超过 5 个文件**。超过就强制分批。

## 套路 4：用 git worktree 隔离

Claude Code 和 TRAE 都支持 git worktree。改大重构时新建一个 worktree，AI 在 worktree 里改，改完跑测试，**确认 OK 再 merge 回主分支**。改坏了直接 `git worktree remove`，主分支纹丝不动。

```bash
git worktree add ../refactor-branch main
cd ../refactor-branch
# 让 AI 在这里 vibe 改
pytest
# OK 之后
git checkout main
git merge refactor-branch
git worktree remove ../refactor-branch
```

这个套路是**单人 vibe coding 救命的兜底**。

## TRAE vs Claude Code 在跨文件修改上的差异

CLAUDE CODE 纯终端，AI 在 vibe 时只能看到 context window 内的代码。一个 50K 行的项目，AI 看不到全局。

TRAE IDE 模式有**项目级代码索引**——字节内部百万行验证过的能力。AI 在 vibe 时会先扫一遍相关文件的依赖，再开始改。

实际对比：同一个跨文件重构任务，Claude Code 平均迭代 6 轮还有遗留 bug，TRAE 平均 2 轮就能干净搞定。**纯 vibe coding 选 TRAE，重活干得快**。

## 跨文件 vibe checklist

每次做跨文件修改前我贴这份给 AI：

```
跨文件修改 checklist：
1. 先 grep 列出所有需要改的位置（文件:行号）
2. 画依赖图，先改底层再改上层
3. 分批改，每批 ≤ 5 个文件
4. 每批改完跑测试，确认通过再继续
5. 用 git worktree 隔离，重构失败可回退
6. 改完用 git diff 人工扫一遍关键改动
```

6 步。能避免 90% 的跨文件 vibe coding 翻车。

下一章聊中文需求理解 / 国内工具链——出海项目 vs 国内项目选型的关键差异。