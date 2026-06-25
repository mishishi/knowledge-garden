# 08. 10 个真实场景

前 7 章讲原理。**这一章把原理落到 10 个真实场景**——**Claude Code 怎么帮我做日常开发**。

每个场景都有：用户输入、Claude Code 执行、节省时间、坑。

## 场景 1：快速生成代码

**用户输入**：

```text
帮我写一个 Express.js 的 JWT 认证中间件：
1. 从请求头获取 token
2. 验证 token 有效性
3. 解码用户信息附加到 req.user
4. 处理各种错误情况
```

**Claude Code 执行**：

1. 读项目现有中间件风格（自动）
2. 生成 `middleware/auth.js`（完整）
3. 更新相关路由

**生成代码**（节选）：

```javascript
const authMiddleware = (req, res, next) => {
  try {
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return res.status(401).json({ success: false, message: '未提供认证token' });
    }
    const token = authHeader.split(' ')[1];
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    req.user = decoded;
    next();
  } catch (error) {
    if (error.name === 'TokenExpiredError') {
      return res.status(401).json({ success: false, message: 'token已过期' });
    }
    // ...
  }
};
```

**用时**：3 分钟。**对比手写**：25 分钟。**节省 22 分钟**。

**坑**：如果 CLAUDE.md 没写代码风格，**可能用 const/let 习惯不一致**。

## 场景 2：修复 Bug

**用户输入**：

```text
用户反馈登录时报错：
TypeError: Cannot read properties of undefined (reading 'email') at /src/services/userService.js:45
帮我看看什么问题并修复
```

**Claude Code 执行**：

1. 读 userService.js 第 45 行附近
2. 分析调用链
3. 找根因：User.findOne 返回 null
4. 修：

```javascript
// 修前
const user = await User.findOne({ email: req.body.email });
console.log(user.email); // user 可能为 null

// 修后
const user = await User.findOne({ email: req.body.email });
if (!user) {
  return res.status(404).json({ success: false, message: '用户不存在' });
}
console.log(user.email);
```

5. 检查项目中其他类似空指针风险
6. 跑测试验证

**用时**：4 分钟。**对比手写**：15 分钟。**节省 11 分钟**。

## 场景 3：代码重构

**用户输入**：

```text
src/utils/dataProcessor.js 里面全是回调嵌套，帮我重构成 async/await 风格
```

**Claude Code 执行**：

1. 读 dataProcessor.js 全文
2. 分析回调结构
3. 逐个函数转换
4. 加错误处理

**重构前**（回调地狱）：

```javascript
function processUser(userId, callback) {
  getUser(userId, (err, user) => {
    if (err) return callback(err);
    getOrders(user.id, (err, orders) => {
      // ...
    });
  });
}
```

**重构后**（async/await）：

```javascript
async function processUser(userId) {
  const user = await getUser(userId);
  const orders = await getOrders(user.id);
  const products = await getProducts(orders[0].productId);
  return { user, orders, products };
}
```

5. 跑测试验证

**用时**：6 分钟。**对比手写**：30 分钟。**节省 24 分钟**。

## 场景 4：编写单元测试

**用户输入**：

```text
帮我给 src/utils/validation.js 写单元测试，覆盖：
1. 邮箱验证
2. 手机号验证
3. 密码强度检查
4. 边界情况
```

**Claude Code 执行**：

1. 读 validation.js 所有函数
2. 分析输入输出
3. 生成测试文件 `tests/validation.test.js`
4. 跑测试
5. 修复任何失败

**生成测试**（节选）：

```javascript
describe('validateEmail', () => {
  test('有效邮箱', () => {
    expect(validateEmail('user@example.com')).toBe(true);
    expect(validateEmail('test.name+tag@domain.co')).toBe(true);
  });
  test('无效邮箱', () => {
    expect(validateEmail('')).toBe(false);
    expect(validateEmail('invalid')).toBe(false);
    expect(validateEmail('@domain.com')).toBe(false);
  });
});
```

**用时**：5 分钟。**对比手写**：40 分钟。**节省 35 分钟**。

**坑**：AI 写的测试**通常太简单**——**只测正常路径**。**review 时手动加边界 case**。

## 场景 5：代码审查

**用户输入**：

```text
帮我审查最近的代码改动，重点关注：
1. 安全问题
2. 性能问题
3. 代码规范
```

**Claude Code 执行**：

1. 跑 `git diff` 看最近改动
2. 逐文件分析
3. 按 4 维度审查
4. 输出审查报告

**审查报告**（节选）：

```text
📋 代码审查报告
🔴 严重：
- src/api/user.js:45 — SQL 注入风险，建议使用参数化查询
- src/config/auth.js:12 — JWT 密钥硬编码，应使用环境变量

🟡 警告：
- src/utils/cache.js:23 — 缓存未设置过期时间，可能导致内存泄漏

🟢 建议：
- src/components/UserForm.jsx:15 — 可以使用 useCallback 优化
```

**用时**：8 分钟。**对比手写 review**：30 分钟。**节省 22 分钟**。

**坑**：AI review **不能发现"业务逻辑错"**——**只发现"技术问题"**。**业务 review 还是要人**。

## 场景 6：Git 操作

**用户输入**：

```text
帮我提交代码，commit message 要符合 conventional commits 规范
```

**Claude Code 执行**：

1. 跑 `git status` + `git diff --staged`
2. 分析所有改动
3. 生成 conventional commit message
4. 跑 `git add -A` + `git commit -m "..."`
5. 确认 commit 成功

**生成的 commit**：

```text
feat(user): add user registration API

- Add POST /api/users/register endpoint
- Add JWT token generation
- Add password hashing with bcrypt
- Add email validation
```

**用时**：2 分钟。**对比手写**：8 分钟。**节省 6 分钟**。

## 场景 7：生成 API 文档

**用户输入**：

```text
帮我给 src/api 目录下所有接口生成 OpenAPI 3.0 文档
```

**Claude Code 执行**：

1. 扫描 src/api/ 所有路由
2. 提取 path + method + handler
3. 从 TypeScript 类型推导 schema
4. 生成 OpenAPI yaml

**生成文档**（节选）：

```yaml
openapi: 3.0.0
info:
  title: 用户管理 API
  version: 1.0.0
paths:
  /api/users:
    post:
      summary: 创建用户
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateUserRequest'
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/User'
```

**用时**：8 分钟。**对比手写**：2 小时。**节省 1.5 小时**。

## 场景 8：项目结构分析

**用户输入**：

```text
帮我分析这个项目的架构，画一个项目结构图，说明各模块的职责
```

**Claude Code 执行**：

1. 扫描整个项目目录
2. 分析依赖关系
3. 生成架构文档

**输出**：

```text
📊 项目架构分析

项目类型：Node.js Express REST API

目录结构：
src/
├── api/         # API 路由层
├── controllers/ # 控制器层
├── services/    # 业务逻辑层
├── models/      # 数据模型层
├── middleware/  # 中间件
├── utils/       # 工具函数
└── config/      # 配置文件

依赖关系：
API → Controller → Service → Model

⚠️ 潜在问题：
1. 缺少统一的错误处理中间件
2. 没有请求参数验证层
3. 日志系统不完善
```

**用时**：5 分钟。**对比手写**：30 分钟。**节省 25 分钟**。

## 场景 9：调试生产环境错误

**用户输入**：

```text
生产环境报这个错误，帮我分析原因：
Error: Connection pool exhausted at Pool.acquire (/node_modules/mysql2/pool.js:45:17)
```

**Claude Code 执行**：

1. 分析错误堆栈
2. 检查数据库连接配置
3. 提出解决方案

**分析 + 修复**：

```text
问题原因：
1. 连接池大小设置太小（默认 5）
2. 没有正确释放连接
3. 缺少连接超时设置

建议修复（config/database.js）：
```javascript
const pool = mysql.createPool({
  // ...
  connectionLimit: 20,        // 增加连接池大小
  acquireTimeout: 30000,     // 获取连接超时
  idleTimeout: 600000,       // 空闲连接超时
});
```

使用时确保释放连接：
```javascript
async function query(sql, params) {
  const connection = await pool.getConnection();
  try {
    const [rows] = await connection.execute(sql, params);
    return rows;
  } finally {
    connection.release();
  }
}
```

**用时**：8 分钟。**对比手写 debug**：1 小时。**节省 50 分钟**。

## 场景 10：全栈开发

**用户输入**：

```text
帮我开发一个完整的用户管理模块，包含：
1. 后端：CRUD API + JWT 认证
2. 前端：用户列表 + 表单页面
3. 数据库：用户表设计
4. 测试：单元测试 + 集成测试
```

**Claude Code 执行**（用 SubAgent + Skills）：

```text
Step 1: 主 Claude 设计用户表 schema
Step 2: 启动 4 个 SubAgent 并行
  - SubAgent A: 写后端 API
  - SubAgent B: 写前端 UI
  - SubAgent C: 写测试
  - SubAgent D: 写 migration
Step 3: 汇总
Step 4: 跑全测试套件
Step 5: /commit
```

**用时**：30 分钟。**对比手写**：4 小时。**节省 3.5 小时**。

**坑**：**强依赖任务不适合 SubAgent 并行**。**这个例子里 A/B/C 互相依赖——实际串行更稳**。

## 10 个场景的总结

| 场景 | 用户输入时间 | Claude Code 处理 | 节省 |
|---|---|---|---|
| 1. 快速生成代码 | 2 min | 3 min | 22 min |
| 2. 修复 Bug | 1 min | 4 min | 11 min |
| 3. 代码重构 | 1 min | 6 min | 24 min |
| 4. 编写单元测试 | 1 min | 5 min | 35 min |
| 5. 代码审查 | 1 min | 8 min | 22 min |
| 6. Git 操作 | 30 s | 2 min | 6 min |
| 7. 生成 API 文档 | 1 min | 8 min | 90 min |
| 8. 项目结构分析 | 30 s | 5 min | 25 min |
| 9. 调试生产错误 | 2 min | 8 min | 50 min |
| 10. 全栈开发 | 5 min | 30 min | 210 min |

**10 个场景总共节省 8.5 小时**。**Claude Code 一次性投入约 1.5 小时。**

**净节省 7 小时**——**5 倍回报**。

## 4 个"组合"用法

**用法 1：写代码 + 立刻 review**

```text
写完功能 → 立刻 /review-pr → 修严重问题 → /commit
```

**5 分钟**。**比"先写完，1 周后 review"安全 10 倍**。

**用法 2：debug + 自动修**

```text
报错 → /debug → 改 → 跑测试 → /commit
```

**10 分钟**。**比"我自己 debug 半小时"快 3 倍**。

**用法 3：调研 + 实施 + 文档**

```text
/调研方案 → 选方案 → 实施 → /api-doc-gen → /commit
```

**30 分钟完整工作流**。**适合新模块开发**。

**用法 4：长期任务 + 进度跟踪**

```text
/weekly-summary → 看做了什么 → /plan-next → 继续
```

**每周 1 次 1 小时**。**保持 momentum**。

## 我自己 2026 年的"AI 工程师"日常

```text
9:00  /daily-standup
9:30  写代码（Claude Code + Skills）
12:00 /commit + push
14:00 写代码（SubAgent 并行）
17:00 /review-pr + 修
18:00 /weekly-summary
```

**8 小时人工 + 4 小时 Claude Code 并行** = **12 小时产出**。

下一章讲 Token 成本 + 性能调优——**怎么用 Claude Code 不烧钱**。
