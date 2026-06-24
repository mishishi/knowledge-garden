# 04. Chunking 策略

> Chunking 是 RAG 流水线里**最容易被忽视、影响最大**的环节。切错了，再好的 embedding + 再贵的向量数据库都救不回来。

## 为什么 Chunking 重要

embedding 模型有 **token 上限**（BGE-M3 是 8192，OpenAI text-embedding-3 是 8191）。把整本 200 页的书塞进去：
- 要么被截断（只保留前 8K token，后面的全丢）
- 要么取平均向量（细节丢失，召回率暴跌）
- 要么算力爆表（O(n²) 注意力）

**正确做法**：把长文档切成**语义完整的 chunk**（每块 200-1000 token），每个 chunk 单独 embed，检索时也按 chunk 级别。

## 5 种主流 Chunking 策略

### 1. 固定大小切块（Fixed-size）

```python
def chunk_fixed(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start = end - overlap
    return chunks
```

**优点**：简单、可预测
**缺点**：在句子中间切断（「今天天气很」+「好，适合出门」）

**适用**：原型的第一步，先跑通再优化

### 2. 按句子切块（Sentence-based）

```python
import re
def chunk_sentences(text: str, sentences_per_chunk: int = 5) -> list[str]:
    sentences = re.split(r'(?<=[。！？.!?])\s*', text)
    chunks = []
    for i in range(0, len(sentences), sentences_per_chunk):
        chunks.append(' '.join(sentences[i:i + sentences_per_chunk]))
    return chunks
```

**优点**：不切断句子
**缺点**：可能 1 个 chunk 包含不相关内容（开头讲 A，结尾讲 Z）

**适用**：中等长度文档

### 3. 按段落切块（Paragraph-based）

```python
def chunk_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split('\n\n') if p.strip()]
```

**优点**：天然语义完整（人类写作就按段落组织）
**缺点**：段落长度不一（有的 50 字、有的 500 字）

**适用**：结构化文档（Markdown、博客）

### 4. 递归切块（Recursive）

LangChain 的 `RecursiveCharacterTextSplitter` 是事实标准：

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", ".", " ", ""],
)

chunks = splitter.split_text(text)
```

**逻辑**：先按段落切、切的 chunk 太大就按句子切、还大就按字符切，**递归降级**。

**优点**：兼顾语义和大小
**缺点**：仍有切断风险

**适用**：**大多数场景的默认选择**

### 5. 语义切块（Semantic）

先用 embedding 算相邻段落的相似度，**相似度低的地方就是自然分段点**：

```python
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer("BAAI/bge-m3")

def chunk_semantic(text: str, threshold: float = 0.5) -> list[str]:
    sentences = split_into_sentences(text)
    embs = model.encode(sentences)

    chunks = [[sentences[0]]]
    for i in range(1, len(sentences)):
        sim = np.dot(embs[i-1], embs[i]) / (
            np.linalg.norm(embs[i-1]) * np.linalg.norm(embs[i])
        )
        if sim < threshold:
            chunks.append([])  # 新 chunk
        chunks[-1].append(sentences[i])

    return [' '.join(c) for c in chunks]
```

**优点**：chunk 边界最自然（语义变化处断开）
**缺点**：慢（要先 embed 所有句子）、成本高

**适用**：**质量要求极高的场景**，或者你想为某个文档精调

## 实战选型

| 文档类型 | 推荐策略 |
|---|---|
| 长篇报告 / 论文 | Recursive（500 token，50 overlap）|
| Markdown / 博客 | Paragraph + Recursive fallback |
| FAQ / 短问答 | 整条问答 = 1 chunk |
| 代码 | 按函数 / 类切（保留完整语法单元）|
| 客服工单 | 1 工单 = 1 chunk，含 metadata（用户/时间）|
| 法律合同 | 按「条款」切，metadata 含条款编号 |

## 必须加 Metadata

每个 chunk 都要带 metadata，否则后续**没法过滤、没法引用、没法回溯**：

```python
chunk = {
    "id": "doc_abc_p5",  # 文档 ID + 页码 + 段落号
    "text": "...",        # chunk 内容
    "embedding": [...],   # 向量
    "metadata": {
        "doc_id": "abc",
        "page": 5,
        "section": "3.2 风险提示",
        "source": "/uploads/2024-q3-report.pdf",
        "created_at": "2024-10-15",
        "category": "财报",
    },
}
```

**没有 metadata 的 RAG 系统 = 没法上生产。**

## 实战代码：完整的 Chunking Pipeline

```python
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import hashlib

model = SentenceTransformer("BAAI/bge-m3")
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500, chunk_overlap=50,
    separators=["\n\n", "\n", "。", ".", " "],
)

def process_pdf(pdf_path: str, doc_id: str) -> list[dict]:
    # 1. 加载 + 按页读
    loader = PyPDFLoader(pdf_path)
    pages = loader.load()  # 每页 1 个 Document

    chunks = []
    for page in pages:
        page_num = page.metadata["page"]
        # 2. 切块
        page_chunks = splitter.split_text(page.page_content)
        for i, chunk_text in enumerate(page_chunks):
            chunk_id = f"{doc_id}_p{page_num}_c{i}"
            # 3. embed
            embedding = model.encode(chunk_text).tolist()
            # 4. metadata
            chunks.append({
                "id": chunk_id,
                "text": chunk_text,
                "embedding": embedding,
                "metadata": {
                    "doc_id": doc_id,
                    "page": page_num,
                    "chunk_idx": i,
                    "source": pdf_path,
                    "category": "财报",
                },
            })

    return chunks

# 批量入库
import glob
for pdf in glob.glob("/uploads/*.pdf"):
    doc_id = hashlib.md5(pdf.encode()).hexdigest()[:8]
    chunks = process_pdf(pdf, doc_id)
    qdrant_client.upsert(collection_name="docs", points=chunks)
```

## 调优参数

| 参数 | 范围 | 影响 |
|---|---|---|
| chunk_size | 200-1000 | 太小 → 上下文不够；太大 → 噪音多 |
| chunk_overlap | 0-100 | 太小 → 切断语义；太大 → 重复 embedding |

**起步推荐**：chunk_size=500, chunk_overlap=50（中文）+ chunk_size=800, chunk_overlap=100（英文，因 token 密度低）。

## 验证 Chunking 质量

跑完 chunking 后抽样看：

```python
# 抽样检查
import random
samples = random.sample(all_chunks, 10)
for s in samples:
    print(f"[{s['metadata']['doc_id']}_p{s['metadata']['page']}]")
    print(f"  {s['text'][:200]}...")
    print()
```

检查：
- ✅ 不在句子中间切
- ✅ metadata 字段完整
- ✅ 长度分布合理（没有 5 token 的「废 chunk」）

## 下篇

[05. 检索与 Reranking](../05-retrieval-and-reranking/) — 拿到 Top-K 候选后，如何精排出最相关的 3-5 条？
