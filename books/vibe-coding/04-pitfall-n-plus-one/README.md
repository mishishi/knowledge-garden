# 04. 真坑 1：N+1 性能陷阱

2026 年 5 月中旬，我接手一个电商小程序后端项目（代号 EC-MINI-2026），商品列表接口用 vibe coding 全程生成。AI 第一版生成的代码：

```typescript
const products = await db.product.findMany({ skip, take });
for (const p of products) {
  p.category = await db.category.findUnique({ where: { id: p.categoryId } });
}
return products;
```

测试环境数据量小，接口 200ms 响应正常。我直接 commit 上线。结果晚高峰并发上来，**接口响应时间从 200ms 飙到 8 秒**，数据库连接池被打爆，整个商品列表页 5 分钟打不开。

紧急排查一晚上才发现：**循环里每条 product 都单独查一次 category，列表 20 条就 21 次查询**。这就是经典的 **N+1 查询**。

## 为什么 vibe coding 特别容易踩这个坑

传统编程你写循环时会本能地想"这里能不能批量"，这叫性能直觉。vibe coding 不写循环，AI 写循环——AI 在 vibe 模式下**默认走最容易想到的实现**，N+1 就是最容易想到的实现。

更要命的是，纯终端 vibe coding（Claude Code / TRAE Work）**没有 IDE 那种"我看到 N 个查询"的视觉提示**。你只看到 AI 说"完成了"，看不到它生成的循环里有几个 `await`。

## 怎么在 vibe coding 流程里防 N+1

三个手段叠着用：

**第一，口述需求模板里加一行**：

```
性能约束：列表类接口禁止 N+1 查询，必须用 join / include / in 查询一次性拿全。
```

这一行 20 字，能让 AI 第一版就避免 80% 的 N+1 案例。

**第二，修正口令里专门扫一遍 AI 生成的代码**：

> "扫一遍这个文件所有 db.xxx.findXxx 调用，列出每个调用在哪个循环里。如果有 N+1，帮我改成 join / include / in。"

让 AI 自己审计自己。AI 比你更熟悉它自己写的代码。

**第三，本地起一个慢查询日志**：

PostgreSQL 开 `log_min_duration_statement = 100`，MySQL 开慢查询日志 `long_query_time = 0.1`。vibe coding 跑完一个接口，**先看慢查询日志再 commit**。如果有同一条 SQL 出现 5 次以上，几乎肯定是 N+1。

## 修复示例

AI 第一版那段代码，正确写法是：

```typescript
const products = await db.product.findMany({
  skip,
  take,
  include: { category: true }
});
return products;
```

Prisma 的 `include` 会自动 join。SQLAlchemy 用 `joinedload` 或 `selectinload`。Sequelize 用 `include`。MyBatis 手写 join。

修复后接口从 8 秒回到 80ms。

## vibe coding 性能 checklist

我每个 vibe coding 项目都贴这份清单到 AI 对话开头：

```
性能约束清单：
- 列表接口禁止 N+1（必须 join / include / in）
- 禁止循环内 new 对象（用对象池或 hoist 出来）
- 禁止 select *（必须指定字段）
- 分页必须用 keyset / cursor，禁止 offset 在大表
- 任何 await 都要考虑可不可以 Promise.all
```

5 行字，能让 vibe coding 出来的代码性能从"上线就崩"变成"基本能跑"。

下一章讲第二个真坑——字段命名 / 规范割裂，这个比 N+1 更隐蔽，跨文件污染更严重。