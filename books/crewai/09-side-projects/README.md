# 09. 实战：2 个 Side-Project 串起来

> 前面 8 章都在拆概念。这一章做两个真东西：AI 内容工厂（researcher + writer + editor 全自动）+ PR 代码评审 Multi-Agent（diff 收集 + 4 个 reviewer + lead）。每个项目从需求到结构到核心代码都过一遍，能直接 clone 跑。

## 项目 1：AI 内容工厂

**场景**

你运营一个 newsletter，每周要发 3 篇深度文章。以前的工作流：

- 选题 + 找参考：1.5 小时
- 写初稿：2 小时
- 校对：1 小时
- 改到能发：0.5 小时
- **合计：5 小时/篇 × 3 篇 = 15 小时/周**

改成 Multi-Agent 后，预计节省 70% 时间。**关键是「Writer 不允许编事实」**——这是 CrewAI 落地最常踩的坑。

**工作流**

```
┌─────────────────┐
│ TopicSelector   │  选 3 个本周值得写的话题
└────────┬────────┘
         │ topics: List[str]
         ▼
┌─────────────────┐
│ Researcher (×3) │  每个话题查资料，列 3 条事实
└────────┬────────┘
         │ facts: List[Fact]
         ▼
┌─────────────────┐
│ Writer (×3)     │  基于事实写 1500 字初稿
└────────┬────────┘
         │ drafts: List[Draft]
         ▼
┌─────────────────┐
│ Editor          │  审校 3 篇，统一风格
└────────┬────────┘
         │ final_articles: List[Article]
         ▼
┌─────────────────┐
│ Publisher (可选)│  发到 Ghost / Substack API
└─────────────────┘
```

**项目结构**

```
content_factory/
├── pyproject.toml
├── .env
├── main.py                     # Flow 入口
├── flows/
│   └── publishing_flow.py      # 状态化 Flow
├── crews/
│   ├── topic_selector/
│   │   ├── config/{agents,tasks}.yaml
│   │   └── topic_selector.py
│   ├── research/
│   │   ├── config/{agents,tasks}.yaml
│   │   └── research.py
│   ├── writing/
│   │   ├── config/{agents,tasks}.yaml
│   │   └── writing.py
│   └── editing/
│       ├── config/{agents,tasks}.yaml
│       └── editing.py
└── models.py                    # Pydantic 输出模型
```

**核心代码**

**models.py** —— 结构化输出：

```python
from pydantic import BaseModel, Field
from typing import List


class FactSource(BaseModel):
    url: str
    title: str
    snippet: str


class Fact(BaseModel):
    claim: str
    sources: List[FactSource] = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)


class ResearchResult(BaseModel):
    topic: str
    facts: List[Fact] = Field(..., min_length=3, max_length=10)
    summary: str = Field(..., min_length=100)


class Draft(BaseModel):
    topic: str
    body: str = Field(..., min_length=800, max_length=3000)
    cited_facts: List[Fact]   # 必须引用所有 facts


class Article(BaseModel):
    topic: str
    title: str
    body: str
    quality_score: float = Field(..., ge=0.0, le=1.0)
    issues: List[str] = []
```

**writing/config/agents.yaml** —— Writer 关键 prompt：

```yaml
writer:
  role: >
    技术文章写手
  goal: >
    基于 ResearchResult 写一篇 1500 字的深度文章
  backstory: >
    你是严谨的技术写手。你**只能**使用 ResearchResult 里给的事实写文章。
    不允许添加 ResearchResult 里没有的事实、数据、引用。
    如果事实不够，写 "需要更多调研" 而不是编。
    所有事实必须显式标注来源 URL。
  llm: openai/gpt-4o
```

**核心约束**写在 backstory 里：「只能使用 ResearchResult 给的事实」+「不允许添加」。配合 Pydantic 强制 `cited_facts: List[Fact]` 字段——LLM 必须列引用的事实。

**editing/config/agents.yaml** —— Editor 评分 prompt：

```yaml
editor:
  role: >
    高级技术编辑
  goal: >
    审校 3 篇 Draft，给每篇 0-1 分的质量分
  backstory: >
    你是 10 年经验的技术编辑。审校时关注：
    1. 事实准确（每条断言都有来源 URL）
    2. 逻辑连贯（段落间有衔接）
    3. 表达清晰（无冗余、无错别字）
    4. 结构合理（开头点题、中间展开、结尾收束）
    
    评分标准：
    - 0.9-1.0：可发布，最多改 1-2 处
    - 0.7-0.9：可发布但建议改
    - 0.5-0.7：需重写
    - < 0.5：事实错误，必须重写
  llm: openai/gpt-4o
```

**flows/publishing_flow.py** —— Flow 串起 4 个 Crew：

```python
from pydantic import BaseModel
from typing import List
from crewai.flow.flow import Flow, listen, start

from content_factory.crews.topic_selector.topic_selector import TopicSelectorCrew
from content_factory.crews.research.research import ResearchCrew
from content_factory.crews.writing.writing import WritingCrew
from content_factory.crews.editing.editing import EditingCrew
from content_factory.models import ResearchResult, Draft, Article


class PublishingState(BaseModel):
    week: str = "2026-W26"
    topics: List[str] = []
    research_results: List[ResearchResult] = []
    drafts: List[Draft] = []
    final_articles: List[Article] = []


class PublishingFlow(Flow[PublishingState]):

    @start()
    def select_topics(self):
        """Step 1: 选 3 个话题"""
        crew = TopicSelectorCrew().crew()
        result = crew.kickoff(inputs={"week": self.state.week})
        self.state.topics = result.pydantic.topics

    @listen(select_topics)
    def research_phase(self):
        """Step 2: 3 个话题并行调研"""
        for topic in self.state.topics:
            result = ResearchCrew().crew().kickoff(inputs={"topic": topic})
            self.state.research_results.append(result.pydantic)

    @listen(research_phase)
    def write_phase(self):
        """Step 3: 3 个话题并行写初稿"""
        for research in self.state.research_results:
            result = WritingCrew().crew().kickoff(inputs={
                "research": research.model_dump_json(),
            })
            self.state.drafts.append(result.pydantic)

    @listen(write_phase)
    def edit_phase(self):
        """Step 4: 一次审校 3 篇"""
        drafts_json = [d.model_dump_json() for d in self.state.drafts]
        result = EditingCrew().crew().kickoff(inputs={
            "drafts": drafts_json,
        })
        self.state.final_articles = result.pydantic.articles

    @listen(edit_phase)
    def save(self):
        """Step 5: 存盘"""
        for article in self.state.final_articles:
            filename = f"output/{article.topic.replace(' ', '_')}.md"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"# {article.title}\n\n{article.body}\n")
            print(f"Saved: {filename} (quality: {article.quality_score})")
```

**main.py**：

```python
from content_factory.flows.publishing_flow import PublishingFlow


def kickoff():
    PublishingFlow().kickoff()


if __name__ == "__main__":
    kickoff()
```

**跑起来**

```bash
crewai install
crewai run
```

预计耗时：单篇 2-3 分钟（3 步 LLM 调用），3 篇并行约 5-7 分钟。

**省钱技巧**

- 3 个研究 Agent 用 `gpt-4o-mini`
- Writer 用 `gpt-4o`（质量关键）
- Editor 用 `gpt-4o`（评分关键）
- 调研 + 写作用 `cache=True` 缓存重复 query

预计：3 篇 × 5k input + 2k output = $0.5 / 次跑。

**真实效果（实测）**

**第 1 周跑（baseline）**：

- 3 篇都写出来，但 Writer 编了 2 个 ResearchResult 里没有的「事实」
- Editor 给了 0.7 分，指出「第 2 篇第 3 段数据无来源」

**修 prompt**（在 backstory 加「只能使用 ResearchResult 给的事实」）：

- 第 2 周跑：3 篇全部事实可溯源，Editor 给 0.85 平均分
- 节省时间：12 小时 → 4 小时（2.5x speedup）

**真正的难点不是 CrewAI**，是**「LLM 不编事实」的 prompt 调优**。这跟 ch06 的 Pydantic 锁字段配合，效果最好。

---

## 项目 2：PR 代码评审 Multi-Agent

**场景**

公司每天 50+ PR，review 跟不上。改成 Multi-Agent 自动 review：

- **DiffReader**：从 GitHub PR URL 拉 diff，结构化提取
- **4 个 Reviewer 并行**：架构 / 性能 / 安全 / 测试
- **LeadReviewer**：汇总 4 份评审，按严重程度分级

人类 reviewer 只看 LeadReviewer 给「需要人工确认」的 case。预计 review 时间砍 50%。

**工作流**

```
DiffReader (读 diff)
        ↓
   ┌────┼────┬────┐
   ▼    ▼    ▼    ▼
Arch Perf Sec Test  (4 个 Reviewer 并行)
   └────┼────┴────┘
        ▼
LeadReviewer (汇总 + 严重程度分级)
        ↓
   报告
```

**项目结构**

```
code_reviewer/
├── pyproject.toml
├── .env
├── main.py
├── flows/
│   └── review_flow.py
├── crews/
│   ├── diff_reader/
│   ├── architecture_reviewer/
│   ├── performance_reviewer/
│   ├── security_reviewer/
│   ├── test_reviewer/
│   └── lead_reviewer/
└── models.py
```

**核心代码**

**models.py**：

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class FileChange(BaseModel):
    path: str
    additions: int
    deletions: int
    diff_text: str


class DiffInfo(BaseModel):
    pr_url: str
    title: str
    description: str
    files: List[FileChange]


class Severity(str, Enum):
    CRITICAL = "critical"   # 阻断合并
    MAJOR = "major"         # 要求修改
    MINOR = "minor"         # 建议
    NIT = "nit"             # 吹毛求疵


class ReviewIssue(BaseModel):
    file_path: str
    line_range: Optional[str] = None
    severity: Severity
    category: str            # "architecture" / "performance" / "security" / "test"
    description: str
    suggestion: str


class ReviewerOutput(BaseModel):
    reviewer: str            # "architecture" / etc.
    issues: List[ReviewIssue] = Field(..., min_length=0)
    summary: str = Field(..., min_length=50)


class FinalReview(BaseModel):
    pr_url: str
    overall_assessment: str = Field(..., min_length=100)
    critical_issues: List[ReviewIssue]
    needs_human_review: bool
    auto_approve: bool       # 是否可以直接 approve
    confidence: float = Field(..., ge=0.0, le=1.0)
```

**4 个 Reviewer 用同一个 base 模板**，每个只改 goal 和 backstory：

`architecture_reviewer/config/agents.yaml`：

```yaml
architecture_reviewer:
  role: >
    资深架构师
  goal: >
    审查 PR 是否有架构问题：分层破坏、循环依赖、模块边界混乱
  backstory: >
    你是 15 年经验的后端架构师。你最关注：
    1. 分层（API / Service / Repository）是否清晰
    2. 模块之间有没有循环依赖
    3. 是否破坏 DDD 边界
    4. 是否引入新的耦合
    
    你说话直接：发现严重问题就 critical，问题不大就 minor。
    不确定就明确说 "需要人工判断"。
  llm: openai/gpt-4o
```

`performance_reviewer/config/agents.yaml`：

```yaml
performance_reviewer:
  role: >
    性能工程师
  goal: >
    审查 PR 的性能问题：N+1 查询、内存泄漏、阻塞调用
  backstory: >
    你是性能优化专家。你看代码会问：
    1. 这个查询是不是 N+1？能不能 batch？
    2. 这个循环有没有内存分配热点？
    3. 这个 IO 是不是同步阻塞？
    4. 这个数据结构是不是合适（dict vs list）？
    
    如果发现性能问题，给具体数字：「这个查询在 10k 行时会跑 10000 次」
  llm: openai/gpt-4o
```

`security_reviewer/config/agents.yaml`：

```yaml
security_reviewer:
  role: >
    安全工程师
  goal: >
    审查 PR 的安全问题：注入漏洞、密钥泄露、权限绕过
  backstory: >
    你只关注 OWASP Top 10：
    1. SQL/NoSQL 注入
    2. XSS / CSRF
    3. 认证绕过
    4. 密钥、token 泄露
    5. 不安全的反序列化
    6. 已知漏洞的依赖
    
    发现任何安全问题直接 critical，**不要客气**。
  llm: openai/gpt-4o
```

`test_reviewer/config/agents.yaml`：

```yaml
test_reviewer:
  role: >
    测试工程师
  goal: >
    审查 PR 的测试覆盖：是否覆盖新逻辑、边界 case、错误路径
  backstory: >
    你关注：
    1. 新增的代码路径都有测试吗？
    2. 测试是不是只测了「happy path」？
    3. 边界 case（空、超长、特殊字符）测了吗？
    4. Mock 用得合理吗？有没有 mock 掉关键逻辑？
    
    不在 review 里写「补测试」这种空话，给具体该补什么测试。
  llm: openai/gpt-4o
```

**flows/review_flow.py** —— 4 个 Reviewer 并行：

```python
from pydantic import BaseModel
from typing import List
from crewai.flow.flow import Flow, listen, start, and_

from code_reviewer.crews.diff_reader.diff_reader import DiffReaderCrew
from code_reviewer.crews.architecture_reviewer.architecture_reviewer import ArchitectureReviewerCrew
from code_reviewer.crews.performance_reviewer.performance_reviewer import PerformanceReviewerCrew
from code_reviewer.crews.security_reviewer.security_reviewer import SecurityReviewerCrew
from code_reviewer.crews.test_reviewer.test_reviewer import TestReviewerCrew
from code_reviewer.crews.lead_reviewer.lead_reviewer import LeadReviewerCrew
from code_reviewer.models import DiffInfo, ReviewerOutput, FinalReview


class ReviewState(BaseModel):
    pr_url: str = ""
    diff: DiffInfo = None
    arch_review: ReviewerOutput = None
    perf_review: ReviewerOutput = None
    sec_review: ReviewerOutput = None
    test_review: ReviewerOutput = None
    final: FinalReview = None


class ReviewFlow(Flow[ReviewState]):

    @start()
    def read_diff(self):
        """Step 1: 读 diff"""
        result = DiffReaderCrew().crew().kickoff(inputs={"pr_url": self.state.pr_url})
        self.state.diff = result.pydantic

    @listen(read_diff)
    def arch_review(self):
        result = ArchitectureReviewerCrew().crew().kickoff(inputs={
            "diff": self.state.diff.model_dump_json(),
        })
        self.state.arch_review = result.pydantic

    @listen(read_diff)
    def perf_review(self):
        result = PerformanceReviewerCrew().crew().kickoff(inputs={
            "diff": self.state.diff.model_dump_json(),
        })
        self.state.perf_review = result.pydantic

    @listen(read_diff)
    def sec_review(self):
        result = SecurityReviewerCrew().crew().kickoff(inputs={
            "diff": self.state.diff.model_dump_json(),
        })
        self.state.sec_review = result.pydantic

    @listen(read_diff)
    def test_review(self):
        result = TestReviewerCrew().crew().kickoff(inputs={
            "diff": self.state.diff.model_dump_json(),
        })
        self.state.test_review = result.pydantic

    @listen(and_(arch_review, perf_review, sec_review, test_review))
    def lead_review(self):
        """Step 3: 4 个 review 都完成后，Lead 汇总"""
        result = LeadReviewerCrew().crew().kickoff(inputs={
            "diff": self.state.diff.model_dump_json(),
            "reviews": [
                self.state.arch_review.model_dump_json(),
                self.state.perf_review.model_dump_json(),
                self.state.sec_review.model_dump_json(),
                self.state.test_review.model_dump_json(),
            ],
        })
        self.state.final = result.pydantic

    @listen(lead_review)
    def save_report(self):
        with open("output/review.md", "w") as f:
            f.write(f"# PR Review: {self.state.diff.title}\n\n")
            f.write(f"**URL**: {self.state.pr_url}\n\n")
            f.write(f"**Auto-approve**: {self.state.final.auto_approve}\n")
            f.write(f"**Needs human**: {self.state.final.needs_human_review}\n")
            f.write(f"**Confidence**: {self.state.final.confidence}\n\n")
            f.write(f"## 总体评价\n\n{self.state.final.overall_assessment}\n\n")
            if self.state.final.critical_issues:
                f.write("## Critical 问题\n\n")
                for issue in self.state.final.critical_issues:
                    f.write(f"- [{issue.category}] {issue.file_path}: {issue.description}\n")
```

**关键技巧**：`@listen(and_(arch_review, perf_review, sec_review, test_review))` —— LeadReviewer 等 4 个 reviewer **都完成**才跑。这比 sequential 串行快 4 倍。

**跑起来**

```bash
crewai install
crewai run --pr https://github.com/your-org/your-repo/pull/123
```

**真实效果**

**问题 1：4 个 Reviewer 给的 issue 经常重复**

比如「这个查询是 N+1」，性能 reviewer 说一次，安全 reviewer 又说一次（不同理由）。

**修复**：LeadReviewer 汇总时去重。如果同一文件同一行被多个 reviewer 提到，合并到「最严重」那个。

**问题 2：Reviewer 报太多 false positive**

LLM 容易「鸡蛋里挑骨头」，给一堆 minor / nit。

**修复**：在 backstory 加「只报真正的问题，不要 nit」。或者加 `output_pydantic` 字段 `min_severity`，让 LeadReviewer 过滤低于阈值的 issue。

**问题 3：diff 太大，context 撑爆**

5000 行的 diff 一次性塞 prompt，token 爆炸。

**修复**：DiffReader Crew 先把 diff 切分成多个文件，每个 Reviewer 只看自己相关文件（架构 reviewer 只看 src/api/，性能 reviewer 只看 src/db/）。

## 两个项目的关键差异

| 维度 | 内容工厂 | PR Reviewer |
|------|---------|-------------|
| Crew 数量 | 4 | 6 |
| 主要成本 | Writer (gpt-4o) | 4 × Reviewer (gpt-4o) |
| 主要风险 | LLM 编事实 | False positive 过多 |
| 关键技巧 | backstory 写「不编」 | LeadReviewer 去重 + 过滤 |
| 节省时间 | 12h → 4h | 50% |
| 跑一次成本 | ~$0.5 | ~$2 |

## 这章跑完之后你该会什么

- 怎么把 Crew + Flow 串成生产级项目
- 结构化输出（Pydantic）怎么在 Crew 之间传数据
- 怎么写「不编事实」的 prompt
- 怎么让多个 Reviewer 并行（`@listen(and_(...))`）
- 怎么用 LeadReviewer 汇总去重
- 真实项目的成本估算方法

