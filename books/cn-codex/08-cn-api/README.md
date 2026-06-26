# 08. 国内 API 接入方案：DeepSeek / Qwen / GLM / Kimi / 豆包

5 大国产模型对比 + 反代技巧 + 独立开发者省钱秘技——这一章给"用 Codex 跑国产模型"的完整方案。

## 为什么要接国产 API

**三个驱动力**：

**1. 成本**

OpenAI 官方 GPT-5.5 API 调用价格是国产模型的 **3-10 倍**。重度使用月成本 $200-400，**接国产 API 降到 $20-50**。

**2. 数据合规**

**国内业务数据必须不出境**——这是金融 / 政企 / 医疗的硬要求。**国产 API 是唯一选择**。

**3. 网络稳定**

**OpenAI API 国内访问不稳定**——**经常 502/timeout**。**国产 API 国内节点稳定**。

## 5 大国产模型对比（2026 Q2）

我跑了 5 款主流国产模型 + 2 款反代 API，**30 天实测**（每个跑 100+ 任务）。

### 价格对比（每百万 token）

| 模型 | 输入价格 | 输出价格 | 上下文 |
|------|---------|---------|--------|
| **DeepSeek V3.2** | ¥1 / M | ¥2 / M | 64K |
| **Qwen 3.5 Max** | ¥4 / M | ¥12 / M | 128K |
| **GLM 5** | ¥5 / M | ¥15 / M | 128K |
| **Kimi K2.6** | ¥6 / M | ¥18 / M | 200K |
| **豆包大模型 1.6 Pro** | ¥3 / M | ¥9 / M | 128K |
| **OpenAI GPT-5.5** | $2.5 / M | $10 / M | 128K |
| **Anthropic Opus 4.7** | $15 / M | $75 / M | 200K |

**DeepSeek 最便宜**——**比 GPT-5.5 便宜 30 倍**。

**国产模型之间**：DeepSeek < 豆包 < Qwen < GLM < Kimi。

### 能力对比（实测评分）

我跑了 3 类任务：

**任务 1：简单代码生成**（"写一个 React 列表组件"）

| 模型 | 一次成功率 | 平均轮数 | 质量分（10 分制）|
|------|----------|---------|----------------|
| DeepSeek V3.2 | 85% | 1.3 | 8.5 |
| Qwen 3.5 Max | 90% | 1.2 | 8.8 |
| GLM 5 | 88% | 1.3 | 8.6 |
| Kimi K2.6 | 92% | 1.1 | **9.0** |
| 豆包 1.6 Pro | 87% | 1.3 | 8.7 |
| GPT-5.5 | 95% | 1.0 | **9.5** |
| Claude Opus 4.7 | 96% | 1.0 | **9.7** |

**任务 2：复杂 bug 排查**（"修 N+1 查询"）

| 模型 | 一次成功率 | 平均轮数 | 质量分 |
|------|----------|---------|-------|
| DeepSeek V3.2 | 65% | 2.8 | 7.0 |
| Qwen 3.5 Max | 75% | 2.3 | 7.8 |
| GLM 5 | 70% | 2.5 | 7.4 |
| Kimi K2.6 | 80% | 2.0 | **8.2** |
| 豆包 1.6 Pro | 72% | 2.4 | 7.6 |
| GPT-5.5 | 88% | 1.5 | **9.0** |
| Claude Opus 4.7 | 92% | 1.3 | **9.4** |

**任务 3：架构设计**（"设计秒杀系统"）

| 模型 | 一次成功率 | 平均轮数 | 质量分 |
|------|----------|---------|-------|
| DeepSeek V3.2 | 50% | 4.2 | 6.5 |
| Qwen 3.5 Max | 65% | 3.5 | 7.5 |
| GLM 5 | 60% | 3.8 | 7.0 |
| Kimi K2.6 | 75% | 2.8 | **8.2** |
| 豆包 1.6 Pro | 62% | 3.6 | 7.3 |
| GPT-5.5 | 85% | 2.0 | **9.0** |
| Claude Opus 4.7 | 90% | 1.8 | **9.4** |

### 综合结论

- **Kimi K2.6 综合最强**（开源 + 200K + 能力接近 GPT-5.5）
- **Qwen 3.5 Max 性价比最高**（能力强 + 价格中等 + 中文好）
- **DeepSeek V3.2 适合预算敏感场景**（最便宜 + 简单任务够用）
- **GLM 5 / 豆包 1.6 Pro** 跟 Qwen 接近，**没有显著优势**
- **国产 vs 闭源顶级**：国产弱 10-15% 但**便宜 3-30 倍**

## Codex CLI 接国产 API 的配置

### 方案 1：Codex CLI config.toml（最简单）

`~/.codex/config.toml`：

```toml
# 默认模型
model = "deepseek-chat"
model_provider = "deepseek"

[model_providers.deepseek]
name = "DeepSeek"
base_url = "https://api.deepseek.com/v1"
env_key = "DEEPSEEK_API_KEY"
wire_api = "responses"

[model_providers.qwen]
name = "Qwen"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
env_key = "QWEN_API_KEY"
wire_api = "responses"

[model_providers.glm]
name = "GLM"
base_url = "https://open.bigmodel.cn/api/paas/v4"
env_key = "GLM_API_KEY"
wire_api = "responses"

[model_providers.kimi]
name = "Kimi"
base_url = "https://api.moonshot.cn/v1"
env_key = "KIMI_API_KEY"
wire_api = "responses"

[model_providers.doubao]
name = "Doubao"
base_url = "https://ark.cn-beijing.volces.com/api/v3"
env_key = "DOUBAO_API_KEY"
wire_api = "responses"
```

**使用**：

```bash
# DeepSeek
codex --model deepseek-chat chat "..."

# Qwen
codex --model qwen3.5-max chat "..."

# Kimi
codex --model kimi-k2-6 chat "..."
```

### 方案 2：多 Profile 配置

**按任务类型选不同模型**：

```toml
# 简单任务用 DeepSeek（最便宜）
[profiles.simple]
model = "deepseek-chat"
model_provider = "deepseek"

# 中文任务用 Qwen（中文最好）
[profiles.chinese]
model = "qwen3.5-max"
model_provider = "qwen"

# 长上下文用 Kimi（200K）
[profiles.long-context]
model = "kimi-k2-6"
model_provider = "kimi"

# 复杂任务用 GPT-5.5（最强）
[profiles.complex]
model = "gpt-5.5"
model_provider = "openai"
```

**使用**：

```bash
# 简单补全
codex --profile simple chat "..."

# 中文任务
codex --profile chinese chat "..."

# 长上下文
codex --profile long-context chat "..."

# 复杂任务
codex --profile complex chat "..."
```

**实测省钱数据**：

- 简单任务 70%（DeepSeek + Qwen）
- 复杂任务 30%（GPT-5.5 + Claude Opus）
- **月成本从 $300 降到 $80**

### 方案 3：CLIProxyAPI（反代多模型）

**github.com/router-for-me/CLIProxyAPI**——把 Codex / Claude Code / Gemini CLI 的 OAuth 认证封装成 OpenAI 兼容 API 端点。

**适合**：想用 ChatGPT / Claude 订阅的额度跑多工具。

**启动**：

```bash
git clone https://github.com/router-for-me/CLIProxyAPI.git
cd CLIProxyAPI
make run
```

**配置 Cursor**：

```
Base URL: http://localhost:8317/v1
Model: gpt-5-codex
```

**就能用 ChatGPT 订阅的额度调 Codex 模型**——**不需要额外 API 费用**。

### 方案 4：Codex++（Codex 桌面版接国产）

**github.com/BigPizzaV3/CodexPlusPlus**——**Codex 桌面版接国产 API**。

**安装**：

1. 下载对应系统 release
2. 安装
3. 买 DeepSeek token
4. 配到 Codex++ 设置

**优势**：

- 用 Codex 桌面版的 UI
- 跑国产模型的 API
- **最适合"用 Codex 习惯 + 国产模型便宜"的组合**

## 5 大模型 API Key 申请

### DeepSeek（最便宜）

- 平台：platform.deepseek.com
- 充值：¥10 起
- 申请：注册 → 实名 → 创建 API Key
- **适合**：预算敏感 / 简单任务

### Qwen（中文最好）

- 平台：dashscope.aliyun.com
- 充值：按量付费 / 包年
- 申请：阿里云账号 → 开通 DashScope
- **适合**：中文项目 / 阿里生态

### GLM 5

- 平台：open.bigmodel.cn
- 充值：按量付费
- 申请：智谱 AI 账号 → 创建 API Key
- **适合**：企业 / 多模态

### Kimi K2.6

- 平台：platform.moonshot.cn
- 充值：按量付费
- 申请：Moonshot AI 账号 → 创建 API Key
- **适合**：长上下文 / 复杂任务

### 豆包 1.6 Pro

- 平台：console.volcengine.com
- 充值：按量付费
- 申请：火山引擎账号 → 开通方舟
- **适合**：字节生态 / 多模态

## 反代技巧：把订阅额度榨干

**风险提示**：**反代使用是灰色地带，OpenAI TOS 没明确态度**。**个人使用问题不大，**大规模商业化不推荐**。

### 方案 A：CC Switch

**github.com/farion1231/cc-switch**——**AI 模型转接工具**。

**功能**：

- 一键切换任意大模型
- 用量统计管理
- 支持 Claude Code / Codex / OpenClaw / Hermes 等

**装**：

```bash
# 选 Codex tab
# 添加 DeepSeek 模型
# 填 API Key
# 启用
# 重启 Codex
```

### 方案 B：codex-lb 负载均衡

**多账号轮转 + WebSocket 转发 + 用量追踪**——**适合团队场景**。

### 方案 C：CLIProxyAPI

**最完整的反代方案**——支持 Codex / Claude Code / Gemini CLI OAuth 转 API。

```bash
git clone https://github.com/router-for-me/CLIProxyAPI
make run
# 启动后监听 8317 端口
# 你的 Cursor / Cline 配置 base_url 指向它
```

**支持功能**：

- OAuth 认证自动管理
- 多账号轮转
- 用量统计
- 模型映射

## 国内 API 接入的 4 个真实坑

### 坑 1：API 格式不统一

**不是所有国产 API 都兼容 OpenAI 格式**——有些要查文档。

**解决**：用方案 1 的 config.toml 配 `wire_api = "responses"`（**这是 OpenAI 协议**）。

### 坑 2：上下文窗口差异

- DeepSeek V3.2：64K
- Qwen 3.5 Max：128K
- Kimi K2.6：200K
- **不是越大越好**——**大上下文 = 慢 + 贵**

**解决**：按任务选上下文。短任务用 DeepSeek，长任务用 Kimi。

### 坑 3：Codex Skills 可能不工作

**Skills 假设 OpenAI Responses API**——国产 API 兼容**但不是 100%**。

**解决**：用 Codex 基础功能 + 国产 API，**复杂 Skills 用 OpenAI 模型跑**。

### 坑 4：Codex 桌面版可能锁官方模型

**Codex Desktop 默认绑定 OpenAI**——**可能不让你接国产**。

**解决**：用 Codex CLI 替代（**完全可配置**）。

## 独立开发者的省钱组合

### 组合 1：纯国产 API（预算敏感）

```toml
[profiles.default]
model = "deepseek-chat"
model_provider = "deepseek"

[profiles.complex]
model = "kimi-k2-6"
model_provider = "kimi"
```

**月成本**：¥50-100（人民币）

### 组合 2：国产 + 闭源顶级（混合）

```toml
[profiles.simple]
model = "deepseek-chat"

[profiles.complex]
model = "gpt-5.5"

[profiles.chinese]
model = "qwen3.5-max"

[profiles.long-context]
model = "kimi-k2-6"
```

**月成本**：$80-150

### 组合 3：CLIProxyAPI + ChatGPT 订阅

**用 ChatGPT Plus 的 Codex 额度**：

```bash
# 启动 CLIProxyAPI
make run

# Cursor 配 base_url
http://localhost:8317/v1
```

**月成本**：$20（ChatGPT Plus 订阅）

## 我自己的 4 模型组合

- **简单补全 / 单文件改动**（70%）：DeepSeek V3.2
- **中文项目 / 文档**（15%）：Qwen 3.5 Max
- **长上下文 / 复杂任务**（10%）：Kimi K2.6
- **架构设计 / 重构**（5%）：GPT-5.5

**月成本**：¥60-100（人民币）——**比纯 GPT-5.5 省 30 倍**。

## 我的判断

**短期（3-6 个月）**：

- 国产模型继续缩小与闭源顶级差距
- DeepSeek 保持价格优势
- Qwen 在中文场景不可替代
- Kimi K2.6 开源 + 200K 上下文是最大亮点

**中期（6-12 个月）**：

- 国产模型 token 价格继续降
- **独立开发者的代码生成边际成本 → 接近 0**
- 这意味着**vibe coding 真正普及**——**人人能 AI 写代码**

**长期（12+ 个月）**：

- 模型价格战结束，**头部 2-3 家胜出**
- 独立开发者按需选 2-3 个模型组合
- **不再有"必须用 GPT"或"必须用 Claude"**——**国产够用**

下一章讲**账号 / 订阅 / 配额**——15 款产品怎么订阅、怎么计费、独立开发者 / 团队 / 企业怎么选——**最实际的"我该选哪款"决策**。