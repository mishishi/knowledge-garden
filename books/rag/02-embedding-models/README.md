# 02. Embedding 模型选型

> Embedding 是把文字转成「机器能比较相似度」的向量。选错模型，下游检索全盘皆输。

## Embedding 是什么

把一段文字转成一个**浮点数数组**（向量），让语义相近的文字在向量空间里距离也近：

```python
# "猫" 和 "狗" 是近义词 → 向量距离小
emb("猫") = [0.21, -0.34, 0.87, ...]   # 1536 维
emb("狗") = [0.19, -0.31, 0.85, ...]   # 距离很近

# "猫" 和 "汽车" 不相关 → 向量距离大
emb("汽车") = [-0.55, 0.78, -0.12, ...] # 距离远
```

距离用**余弦相似度**（cosine similarity）算，范围 [-1, 1]，1 = 完全相同。

## 主流模型对比（2026 版）

| 模型 | 维度 | 中文 | MTEB 分数 | 价格 | 备注 |
|---|---|---|---|---|---|
| text-embedding-3-small | 1536 | 中等 | 62.3 | $0.02/1M tokens | OpenAI 性价比首选 |
| text-embedding-3-large | 3072 | 中等 | 64.6 | $0.13/1M tokens | OpenAI 高质量 |
| BGE-M3 | 1024 | **强** | 65.0 | 自托管免费 | 中文 SOTA |
| m3e-large | 1024 | 强 | 63.5 | 自托管免费 | 早期中文 SOTA |
| Cohere embed-v3 | 1024 | 中等 | 64.0 | $0.10/1M tokens | 多语言均衡 |
| BGE-large-zh-v1.5 | 1024 | 强 | 64.5 | 自托管免费 | 中文专用 |
| multilingual-e5-large | 1024 | 中等 | 64.0 | 自托管免费 | 微软出品 |

**中文场景首推 BGE-M3**——开源、自托管免费、中文效果好、支持多语言。

## 选型的 4 个维度

### 1. 维度数

维度越高理论上表达力越强，但**存储和检索都更贵**：

```
1536 维 × 4 bytes = 6 KB / 向量
100 万向量 = 6 GB（光是向量存储，不算索引开销）
```

不要盲目选大维度。**先 1024 起步，效果不够再升。**

### 2. 中文支持

很多英文 SOTA 模型（OpenAI ada、e5-large）中文效果一般。中文文档必须用中文专门训练过的模型（BGE-zh、m3e）。

### 3. MTEB 分数

[MTEB](https://huggingface.co/spaces/mteb/leaderboard) 是 HuggingFace 的 embedding benchmark 排行榜。看分数时注意：
- **看子任务分数**，不要只看总分（检索 / 分类 / 聚类是不同能力）
- **看中文子任务**，不是英文
- **看实际业务测试**，benchmark ≠ 你的场景

### 4. 成本

**自托管 vs API**：
- **API**（OpenAI、Cohere）：方便、按量付费、数据出域（合规风险）
- **自托管**（BGE、m3e）：要 GPU/算力、首次部署麻烦、数据不出域

中文 + 数据敏感 + 量大 → 自托管 BGE-M3。量小 / 临时跑 / 多语言 → API。

## 实战代码

```python
# 方案 A：OpenAI API（简单但中文一般）
from openai import OpenAI
client = OpenAI()

def embed(text: str) -> list[float]:
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return resp.data[0].embedding

# 方案 B：BGE-M3 自托管（中文场景首推）
# pip install sentence-transformers
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-m3")

def embed(text: str) -> list[float]:
    return model.encode(text).tolist()

# 使用：余弦相似度
import numpy as np
def cosine_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

q_emb = embed("什么是 RAG")
d_emb = embed("RAG 是检索增强生成")
print(cosine_sim(q_emb, d_emb))  # 0.87（高相关）
```

## 关键陷阱

### 1. 维度必须一致

混用不同模型的向量会得到 nonsense 距离。同一向量库里所有向量必须来自**同一个模型**。

### 2. chunk 前先 embed

是**整段文档 embed** 还是**每个 chunk 单独 embed**？实战里：
- 检索时用 **chunk 级** embedding（小段，精确）
- 上下文恢复时拿 chunk 的 parent_id 找回整段

### 3. 文本预处理影响大

```python
# 直接 embed HTML/JSON
embed("<div class='foo'>你好</div>")  # 噪声大

# 先清洗
from bs4 import BeautifulSoup
text = BeautifulSoup(html_doc, "html.parser").get_text()
embed(text)
```

去除 HTML 标签、特殊字符、多余空白。中文文档还要去掉全角空格、Unicode 转义。

### 4. 长文本截断

大多数 embedding 模型有 token 上限（512 或 8192）。超长文本要么截断、要么按句切分后**取平均向量**：

```python
def embed_long(text: str, max_tokens=512) -> list[float]:
    chunks = split_into_chunks(text, max_tokens)
    embs = [model.encode(c) for c in chunks]
    return np.mean(embs, axis=0).tolist()
```

但**平均向量会丢失细节**——下一章的 chunking 才是正确解法。

