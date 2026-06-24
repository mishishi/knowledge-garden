# 第 3 章代码

## 文件结构

```
code/
├── 01_role.py        # Role 抽象：3 种拆分方式对比
├── 02_goal.py        # Goal 颗粒度对比
├── 03_tool.py        # Tool 自定义工具 3 种写法
├── 04_memory.py      # Memory 短期/长期/共享对比
└── 05_handoff.py     # Handoff 顺序/条件/并行 3 种模式
```

## 运行

每个文件支持模式参数（除 03_tool.py 外）：

```bash
# Role
python 01_role.py good       # 推荐：细粒度拆分
python 01_role.py bad        # 反例：粗粒度
python 01_role.py over       # 反例：过度拆分

# Goal
python 02_goal.py good       # 推荐：细粒度 + 可验证
python 02_goal.py bad        # 反例：太宽
python 02_goal.py contradict # 反例：矛盾

# Tool
python 03_tool.py "东京今天天气怎么样？"
# 演示 3 种工具写法：装饰器、BaseTool、错误返回

# Memory
python 04_memory.py short    # 短期记忆
python 04_memory.py long     # 长期记忆
python 04_memory.py shared   # 共享记忆

# Handoff
python 05_handoff.py pipeline     # 顺序
python 05_handoff.py conditional # 条件
python 05_handoff.py parallel    # 并行
```

## 依赖

- `openai>=1.50.0`
- `crewai>=0.80.0`
- `pydantic>=2.0`（CrewAI 自带，但 03_tool.py 显式用到）

完整 requirements 在 [01-your-first-agent/code/requirements.txt](../01-your-first-agent/code/requirements.txt)。