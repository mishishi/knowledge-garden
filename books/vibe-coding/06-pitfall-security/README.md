# 06. 真坑 3：安全 / 鉴权 / 密钥硬编码

vibe coding 出来的代码最大的安全黑洞是**密钥硬编码**。AI 默认会写 `secret = "123456789"` 这种东西，因为它的训练数据里大量示例就是硬编码方便教学。

2025 年 Escape 安全公司扫了 5600 多个 vibe coding 应用，发现**超过 2000 个安全漏洞、400 多个暴露的密钥**。大部分是 JWT 密钥、数据库密码、第三方 API key。

我自己在 Go Gin 项目里 vibe 出过一个生产级 JWT 中间件，第一版的密钥就是硬编码：

```go
token, _ := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
    return []byte("123456789"), nil  // 硬编码密钥
})
```

测试环境跑得好好的，上线之后**整个 token 验证逻辑等于公开**——任何拿到这个 commit 的人都能伪造任意用户的 JWT。

## vibe coding 出来的代码五大安全雷区

**1. 密钥硬编码** — 上面那个案例。AI 默认写死字符串方便测试，你上线时没替换。

**2. SQL 拼接** — AI 用 `db.query("SELECT * FROM users WHERE id = " + userId)` 而不是参数化查询。vibe coding 出来的 ORM 用错或直接 raw SQL 时特别常见。

**3. 缺鉴权中间件** — AI 写业务接口时**默认有权限**，不会主动加 `@RequireAuth()` 装饰器。结果某些敏感接口裸奔。

**4. 错把"前端校验"当"后端校验"** — AI 看代码上下文有前端 form 校验，就以为后端不用校验了，直接信任 request body。

**5. 错把"内部调用"当"无需校验"** — AI 看到代码注释 `// internal API` 就跳过鉴权，但实际上 IP 白名单 / mTLS / API Gateway 一个都没配。

## 怎么破

口述需求模板里**必加一段安全约束**：

```
安全约束：
- 禁止任何密钥、token、密码硬编码到代码里。统一从环境变量读取（如 JWT_SECRET, DB_PASSWORD, REDIS_URL）
- 所有 SQL 必须参数化查询，禁止字符串拼接
- 所有写接口必须有鉴权装饰器（@RequireAuth / middleware('auth')）
- 所有用户输入必须后端校验（zod schema / joi / class-validator）
- 敏感操作必须有审计日志（who, when, what, result）
- 错误返回禁止泄露内部细节（stack trace, SQL, file path）
```

7 行字。贴到 AI 对话开头。这 7 行字能解决 80% 的 vibe coding 安全漏洞。

## 修正口令模板

发现 AI 第一版有安全问题，**用这套口令格式**：

> "以下安全问题必须修复：[列具体问题，附行号或函数名]。每个问题说明：1) 为什么是漏洞；2) 改成什么。"

反例：

> "这段代码不安全，改一下。"

AI 会瞎试，把对的改错。

正例：

> "JWTAuthMiddleware 函数第 12 行密钥硬编码 '123456789'，改为 os.Getenv('JWT_SECRET')，且启动时校验环境变量非空否则 panic。第 18 行 jwt.Parse 没 try/catch 包，区分 token 过期 (jwt.ErrTokenExpired) 和 token 无效，分别返回 401 '登录已过期' 和 401 '令牌无效'。第 25 行 token.Valid 没单独校验，即使 Parse 返回 nil err 也可能被篡改。"

具体到行号 + 具体改法，AI 一次到位。

## commit 前安全 checklist

```
安全 checklist：
- grep -r "password\s*=\s*['\"]" src/  返回空
- grep -r "secret\s*=\s*['\"]" src/  返回空
- 所有写接口有 @RequireAuth
- 所有 SQL 参数化
- 错误返回不泄露 stack
- 审计日志覆盖敏感操作
```

6 项。0 项不通过就不能 commit。

## 长期建议

vibe coding 出来的代码**必须经过第二人 review**，哪怕那个人只扫 30 分钟。我现在每个 vibe coding 项目都让组里另一个人扫一遍 commit，光这一道工序就拦下过 3 次密钥硬编码事故。

金融 / 医疗 / 政企 / 任何合规要求高的项目，**别用 vibe coding**。逐行写 + 逐行审 + SAST / DAST 工具扫。AI 写代码快但安全审计慢，省下的时间全在 review 阶段还回去了。

下一章讲多文件联动 / 全局重构——vibe coding 处理大改动的核心方法。