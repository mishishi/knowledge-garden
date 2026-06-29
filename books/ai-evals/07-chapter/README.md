# 07. 自动化评测工程

> 流水线脚本不是 "写一次就完", 它是评测系统的肌肉。

凌晨两点四十分, 我盯着屏幕上一条已经跑了一小时还没结束的评测任务, 心里只有一个念头: "这套脚本到底什么时候才能真正稳定?" 那是我第一次把评测从 notebook 搬到 cron 上的夜晚。日志里全是 `KeyError: 'answer'`、`TimeoutError`、还有一条特别有意思的—— `FileNotFoundError: 'golden_set.json'`, 因为有个人把它改名成了 `golden_set_v2_FINAL.json`。

这一章想讲的就是: 怎么把评测脚本做成一个能放在 CI 里、能被别人接手、能在凌晨三点报警而不是崩在生产环境的工程模块。我踩过的坑, 大概能帮后来的同学省下几十个小时。

## 为什么评测一定要上流水线

先把一句我一直跟团队强调的话放在这: 评测脚本和数据一样, 都是产出的资产, 不是一次性玩具。

我见过最常见的反模式是, 同学在本地 jupyter 里跑出一份看起来不错的报告, 然后 commit, 然后下一个人拉下来发现路径不对、API key 过期、模型版本升了、prompt 改了一个字, 跑出来结果天差地别。这种 "评测" 本质上不可复现, 跟没跑差不多。

上流水线的核心目的有三个:

1. **可复现**: 同样的 commit + commit hash + 数据集 → 同样的结果。
2. **可对比**: 每周三凌晨自动跑, 把分数落进表里, 趋势能画出来。
3. **可拦截**: 一次回归掉了 5 分, 直接红 PR, 不让人合并。

我自己的项目里, 上完流水线之后失败率从 12% 降到了 1.8%。不是因为脚本写得多好, 而是因为原来那些 "本地跑得好好的" 隐藏问题, 在定时执行下全暴露了, 被一个一个修掉。

## 一个能跑的最小骨架

先看一段我目前在用的最小骨架, 删掉了项目相关的部分, 但骨架完整:

```python
# eval_pipeline.py
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime

def load_golden(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # 用内容哈希当版本号, 避免文件名乱改
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return data, digest

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    cases, version = load_golden(args.golden)
    started_at = datetime.utcnow().isoformat()

    results = []
    for case in cases:
        try:
            answer = run_one_case(case, model=args.model)
            results.append({"id": case["id"], "answer": answer, "ok": True})
        except Exception as e:
            # 失败也要落盘, 不能让一条坏 case 拖垮整次跑批
            results.append({"id": case["id"], "error": str(e), "ok": False})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump({
            "golden_version": version,
            "model": args.model,
            "started_at": started_at,
            "results": results,
        }, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
```

这段代码里有几个我特别在意的小决定:

- **数据集用哈希而不是文件名当版本号**。`golden_set.json`、`golden_set_v2.json`、`golden_set_FINAL_use_this.json` 在我职业生涯里见过的项目里出现过无数次, 哈希能强制人面对 "这其实是另一份数据" 的现实。
- **每条 case 独立 try / except**。一条样本抛异常不能让整次评测崩盘, 也不能让一条数据被静默吞掉——必须写进 results, 后续报表才能算 "失败率"。
- **started_at 写进结果文件**。对比两次跑的差异时, 时间戳比 commit message 重要得多, 因为 prompt 模板的修改常常不在 git 里。

## 把骨架接进 CI

骨架只能跑, 流水线还得能 "在正确的时间被正确的人触发"。下面这段是我在 GitHub Actions 上用的最小化配置, 项目里很多同学看完都说 "原来这么简单":

```yaml
# .github/workflows/eval.yml
name: nightly-eval
on:
  schedule:
    - cron: "0 17 * * 1-5"   # 工作日 UTC 17:00 = 北京时间 01:00
  workflow_dispatch:
    inputs:
      model:
        description: "model tag to evaluate"
        required: true

jobs:
  run-eval:
    runs-on: ubuntu-latest
    timeout-minutes: 90
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - name: run eval
        env:
          OPENAI_API_KEY: ${{ secrets.OAI_KEY }}
        run: |
          python eval_pipeline.py \
            --golden data/golden.json \
            --model ${{ inputs.model || 'gpt-4o-mini-2024-07-18' }} \
            --out reports/$(date +%F).json
      - uses: actions/upload-artifact@v4
        with:
          name: eval-report
          path: reports/$(date +%F).json
```

这里藏着我后来反复给团队强调的三件事:

第一, **timeout-minutes 一定要写**。不写默认 360 分钟, 我那次 "凌晨两点四十分" 就是因为某次评测里的 LLM 调用 hang 住, CI 跑了六小时才超时失败。设到 90 分钟之后, 单次异常最多浪费一个工位的工作日上午, 不会浪费整晚。

第二, **API key 走 secrets, 别走环境变量文件**。我见过有人把 `.env` commit 上去, 三天后账单多了两千美金, 至今想起都心痛。secrets 是按 PR 隔离的, 即使误 commit 也不会泄漏到 fork。

第三, **报告落盘 + 上传 artifact**。为什么不直接打 log? 因为 log 在 CI 里只保留 90 天, 而且很难 diff。落到 JSON 文件, 第二天另一个脚本就能 diff 两个文件的 scores 字段, 自动发 PR 评论。

## 我踩过的三个真坑

第一坑: **"本地跑得好好的, CI 上挂了"**。最常见的原因是路径。notebook 里用相对路径一切正常, CI 的 working directory 是 `/home/runner/work/xxx/xxx`, 相对路径直接对不上。我后来在脚本入口强制 `chdir 到 __file__ 的父目录`, 然后所有路径都用 `Path(__file__).parent` 拼。这一个改动, 让 "CI 失败但本地通过" 的 issue 减少了 80%。

第二坑: **并发把 rate limit 打爆**。最早我图快, 写了 50 个线程并发调 OpenAI, 结果第一次跑就被 429 打回来, 还连带影响了团队其他人的开发。换成 token bucket 限速之后, 1000 条样本稳定跑 47 分钟, 不再触发任何限流。我把限速逻辑抽成了一个 `RateLimiter` 类, 后来在三个项目里复用。

第三坑: **结果文件被覆盖**。我曾经一天早上发现 reports/2024-10-15.json 被覆盖了——因为 CI 重跑了一次 workflow, 但 report 文件名只带日期。改用 `reports/{date}-{run_id}.json` 之后, 同一日期的多次跑批都能保留。我还在脚本开头加了 `if out.exists(): raise SystemExit("refuse to overwrite")`, 双保险。

## 数据集、prompt、模型 三件套的版本对齐

这是我后来补的一个工程原则: **评测里所有外部依赖都必须有版本号**。具体一点:

- **数据集**: 上面那段骨架的 sha256 前 12 位就是版本号。
- **prompt**: 我把 prompt 模板也放进 git, 然后用 `git rev-parse HEAD:prompts/main.txt` 当版本号。
- **模型**: 不用 `gpt-4o-mini`, 用 `gpt-4o-mini-2024-07-18`, 这样模型灰度升级时能定位到具体哪天开始飘。

报告文件里这三个字段同时落盘, 后面做趋势分析、做 A/B、做归因, 缺一不可。我有一次排查 "为什么本周分数掉了 3 分", 最后定位到是 prompt 模板里的一个换行符被 prettier 改成了空格, 花了半天。没有版本号的话, 这种问题根本没法复现。

## 怎么判断你的流水线 "合格了"

最后, 给你四个判断标准, 我每次 review 团队的评测脚本都会按这个打钩:

1. **冷启动能不能 5 分钟内跑起来**。新来的同学 clone 仓库之后, 五分钟内能不能跑出第一条结果? 如果需要 "问张三要一个 key"、"装某个奇怪的驱动"、"把某个文件改名", 那就是不合格。
2. **失败能不能定位到具体 case**。500 条里失败 5 条, 报表里能不能直接看到是哪些 id、什么原因? 而不是 "评测挂了, 看看 log"。
3. **能不能横向对比**。同一份数据集, 不同模型 / 不同 prompt / 不同时间, 跑出来的结果能不能直接 diff? 能不能画时间序列?
4. **能不能反查到输入**。某个 case 失败了, 能不能从报告里反查到当时的输入 prompt、模型返回值、当时的 prompt 模板版本号?

四条全过, 我才会放心把这个评测叫做 "工程化"。少一条, 就还是处在 "能用" 的阶段, 不能叫 "工程"。

---

写到这里, 我其实最想说的是: 评测工程的难点从来不是脚本本身, 而是 **强迫团队接受 "评测结果是严肃产出" 这件事**。脚本三小时就能写完, 让所有人愿意跑、愿意看、愿意因为评测红了而回滚代码, 这才是慢功夫。下一章我会进入更具体的领域: LLM-as-a-judge 的那些坑——为什么它好用, 为什么它也会骗你, 怎么设置才不容易被骗。

[下一章](./08-chapter.md)