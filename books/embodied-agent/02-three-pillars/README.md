# 02. 具身智能的三大支柱

具身智能是个综合技术栈，由三大支柱组成：**大脑（AI 模型）+ 身体（硬件）+ 训练场（仿真平台）**。每一支柱都决定最终能力上限，缺一不可。

## 支柱 1：大脑（Brain）

**任务**：理解环境、做决策、规划动作。

**核心组件**：

**a. 视觉编码器（Vision Encoder）**

把摄像头画面编码成向量。

主流方案：

- **CLIP**（OpenAI）— 经典 VLM 视觉编码器
- **DINOv2**（Meta）— 自监督学习，泛化好
- **SigLIP**（Google）— Sigmoid loss 替代 softmax loss
- **EVA-CLIP**（智源）— 中文友好
- **Vision Transformer (ViT)** — 各种 VLM 的底层架构

**b. 语言模型（LLM / Reasoning Model）**

处理指令、推理、规划。

主流方案：

- **GPT-6 / GPT-4o**（OpenAI）— 多模态原生
- **Claude Opus 4.7**（Anthropic）— reasoning 强
- **Gemini 2.0**（Google）— 多模态 + 长 context
- **DeepSeek V4**（深度求索）— 国产开源
- **Qwen2.5-VL**（阿里）— 国产多模态

**c. 动作规划器（Action Planner）**

把决策翻译成具体动作。

主流方案：

- **RT-2 / RT-X**（Google）— 视觉-语言-动作（VLA）模型
- **π0 / π0-FAST**（Physical Intelligence）— 通用机器人基础模型
- **OpenVLA**（开源）— Open X-Embodiment 衍生
- **DexVLG**（国产）— 灵巧手专用

**2026 年趋势**：VLA（Vision-Language-Action）模型成为主流——单一模型同时处理视觉 + 语言 + 动作输出，替代之前的"模块拼接"（视觉编码器 + LLM + 动作规划器分开）。

## 支柱 2：身体（Body）

**任务**：执行大脑的指令。

**形态分类**：

**a. 固定基座机械臂**

最简单、最成熟。固定在桌面 / 产线上，6-7 自由度。

代表产品：

- **Franka Panda**（德国）— 研究 / 教育首选
- **UR5e / UR10e**（丹麦）— 工业
- **Aloha / Aloha 2**（Stanford）— 低成本双臂
- **Realman**（国产）— 性价比

**适用**：工业抓取、实验室研究、教育。

**b. 轮式移动机器人**

底盘 + 机械臂。能移动到不同位置工作。

代表产品：

- **TIAGo**（PAL Robotics，西班牙）— 模块化
- **Fetch**（Fetch Robotics，美国）— 仓储
- **HSR**（Toyota，日本）— 家庭 / 办公
- **LoCoBot**（Carnegie Mellon）— 研究

**适用**：仓储物流、家庭服务、医院配送。

**c. 四足机器人**

四条腿，复杂地形通行能力强。

代表产品：

- **Spot**（Boston Dynamics，美国）— 行业标准
- **AnyMal**（瑞士 ANYbotics）— 工业巡检
- **宇树 B2 / Go1**（中国）— 性价比
- **CyberDog 2**（小米）— 消费级

**适用**：电力巡检、矿井救援、军事、安防。

**d. 双足人形机器人**

最复杂、通用性最强。

代表产品：

- **Optimus Gen 2**（Tesla）— 工业 / 家庭
- **Figure 02**（Figure AI）— 工厂 / 家庭
- **Atlas**（Boston Dynamics）— 研究 / 特种
- **H1 / H1+**（宇树）— 工厂
- **A2**（智元）— 工厂
- **Digit**（Agility Robotics）— 物流

**适用**：工厂、家庭、特种作业。**2026 年是量产元年**。

**e. 灵巧手（Dexterous Hands）**

多指机械手，能做精细操作。

代表产品：

- **Allegro Hand**（Wonik Robotics，韩国）— 研究
- **LEAP Hand**（CMU）— 低成本
- **Schunk SVH**（德国）— 工业
- **因时 RH56DFX**（国产）— 性价比

**适用**：精细操作（拧螺丝、拿鸡蛋、写字）。

## 支柱 3：训练场（Training Ground）

**任务**：让 AI 在虚拟环境学会技能。

**主流仿真平台**：

**a. NVIDIA Isaac Lab / Isaac Sim**

- 优点：物理仿真最真实、GPU 加速、和 NVIDIA 硬件深度集成
- 缺点：学习曲线陡、License 限制
- 适合：大规模训练、研究机构

**b. Genesis**

- 2024 年开源，新平台
- 优点：开源、Python 原生、性能好
- 缺点：生态还在建设
- 适合：中小团队

**c. MuJoCo**

- DeepMind 收购，物理引擎标杆
- 优点：物理精确、速度快
- 缺点：渲染一般、需要自己搭场景
- 适合：强化学习研究

**d. Isaac Gym**

- Isaac Lab 的前身，单 GPU 大规模并行训练
- 适合：快速 RL 实验

**e. SAPIEN**

- Meta 开源
- 优点：精细操作仿真好
- 适合：机械臂研究

**f. Habitat / Habitat 3.0**

- Meta 开源
- 优点：室内场景库大
- 适合：导航 / 移动机器人

**g. AI2-THOR / iGibson**

- 学术仿真平台
- 适合：研究

**2026 年最常用组合**：

- 研究：Isaac Lab + MuJoCo
- 工业：Isaac Sim + 自定义场景
- 个人开发者：Genesis + Habitat

## 三大支柱的协同

三大支柱不是独立工作，是**端到端协同**：

```
[真实世界传感器数据]（摄像头 / 激光雷达 / 触觉）
   ↓
[大脑：VLA 模型处理]
   - 视觉编码器
   - LLM 推理
   - 动作规划
   ↓
[动作指令]
   ↓
[身体：关节 / 电机 / 液压执行]
   ↓
[真实世界交互]
   ↓
[采集新数据 / 反馈给大脑]
```

**关键技术**：sim-to-real（仿真训练 + 真实部署）。在仿真里跑 100 万次试错，真实世界跑 100 次精调。这是 embodied agent 比传统机器人快得多的核心原因。

## 选型决策

**我要做 embodied agent 研究 / 创业，从哪里开始？**

**预算 $0**：Genesis + Habitat + 开源 VLA 模型（OpenVLA / π0）+ 仿真训练。

**预算 $10K**：买一台 Aloha 双臂（$25K 一套二手）+ 一台 RTX 4090 + 仿真训练为主。

**预算 $100K**：买 Figure 02 / 1X Neo / 宇树 H1（租赁）+ 4-8 张 H100 + Isaac Lab 大规模训练。

**预算 $1M+**：自研硬件 + 自建数据集 + 工业级部署。

**实战推荐**：先从仿真开始（成本最低、迭代最快），等算法稳定再上真机。

## 三大支柱 2026 年趋势

**大脑**：VLA 模型一统天下，从"模块拼接"走向"端到端"。

**身体**：人形机器人量产元年，单价从 $50K 降到 $20K。

**训练场**：仿真器收敛到 Genesis + Isaac Lab 两个主流，开源数据集（Open X-Embodiment）成为公共资源。

下一章讲世界模型——大脑里最关键的部分。