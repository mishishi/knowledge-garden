# 实战 CodeReviewer Multi-Agent

## 项目结构

```
09-code-review-project/
├── README.md                    # 项目说明
├── main.py                      # 入口
├── crew.py                      # CrewAI 组装
├── agents/
│   ├── code_reader.py           # 读取员
│   ├── reviewer_architecture.py # 架构评审
│   ├── reviewer_performance.py  # 性能评审
│   ├── reviewer_security.py     # 安全评审
│   ├── reviewer_test.py         # 测试评审
│   └── lead_reviewer.py         # 主评审
├── tools/
│   ├── git_diff.py              # Git diff 工具
│   └── file_reader.py           # 文件读取工具
├── data/
│   └── sample_diff.txt          # 示例 diff
├── output/
│   └── review_report.md         # 生成的报告
├── requirements.txt
└── .gitignore
```

## 运行

```bash
cd 09-code-review-project
pip install -r requirements.txt
export OPENAI_API_KEY=sk-xxx

# 跑示例
python main.py

# 跑自己的 diff
python main.py --diff data/my_diff.txt

# 直接读 git diff
python main.py --diff "git diff HEAD~1"
```

## 工作流程

```
1. CodeReader 读取 diff，提取结构化信息
        ↓
2. 4 个 Reviewer 并行评审（架构 / 性能 / 安全 / 测试）
        ↓
3. LeadReviewer 汇总 4 份评审，输出最终报告
```

## 扩展方向

- 接 GitHub API，自动从 PR URL 拉 diff
- 接 GitHub Webhook，自动响应 PR 创建
- 接 Slack / 飞书通知
- 高风险评审结果需要人类确认（不能自动 approve）
- 评审结果存数据库，做趋势分析