# 03. 世界模型：embodied agent 的大脑核心

世界模型（World Model）是 embodied agent 大脑里最关键的部分——它让 agent 能在"脑子里"模拟"如果我做 X 会发生什么"，而不需要真的去做 X。

这一章讲世界模型的原理、训练、应用。

## 为什么需要世界模型

传统机器人控制是"感知 → 反应"：看到障碍物 → 立即绕开。这种 reactive 方式在已知环境好用，**未知复杂环境就崩**——比如家里突然多了一只猫、杯子掉地上碎了。

世界模型让 agent 能"想象未来"：在脑子里模拟 3 步后的状态，评估哪个动作更好。

**例子**：

agent 想从客厅走到厨房。世界模型在脑子里模拟：

```
[动作 1：直走 5 米]
   ↓ 世界模型预测
[状态：撞到茶几]
   ↓ 评分：差

[动作 2：左转 30° + 走 5 米]
   ↓ 世界模型预测
[状态：到达厨房门口]
   ↓ 评分：好

[动作 3：右转 + 走 3 米 + 左转 + 走 2 米]
   ↓ 世界模型预测
[状态：到达厨房门口，但耗时更长]
   ↓ 评分：中
```

agent 选动作 2。

## 世界模型的 3 类架构

**a. 自回归生成式（GPT 风格）**

把世界建模成 token 序列，预测下一个 token。

代表：

- **GAIA-1**（Wayve）— 自动驾驶世界模型
- **UniSim**（Google）— 通用世界模型
- **DreamerV3**（DeepMind）— 强化学习世界模型

**优点**：能处理任意模态（图像、文本、动作）。

**缺点**：生成慢、容易 drift（预测几步后偏离真实）。

**b. 隐空间动力学（Latent Dynamics）**

把状态编码到隐空间，在隐空间预测下一步。

代表：

- **Dreamer** 系列（DeepMind）
- **World Models**（Ha & Schmidhuber, 2018 经典论文）
- **MuZero**（DeepMind）— 不用真实环境也能学

**优点**：快、稳、适合 RL 训练。

**缺点**：隐空间难解释，调试困难。

**c. 物理仿真式（Physics-based）**

直接用物理引擎（MuJoCo / Isaac）做前向仿真。

代表：

- **Isaac Sim**（NVIDIA）
- **MuJoCo XLA**（Google）
- **Genesis**（开源）

**优点**：物理精确、可解释。

**缺点**：仿真和真实世界有 gap（sim-to-real 问题）。

**2026 年主流**：**混合架构**——物理仿真做短期精确预测（< 1 秒），隐空间动力学做长期粗略预测（> 1 秒）。

## 训练世界模型

**数据来源**：

**a. 真实数据**

自动驾驶公司（Wayve / Tesla / Waymo）有海量真实驾驶数据，训练世界模型效果好但成本高（数据采集 + 标注）。

**b. 仿真数据**

Isaac Sim / Genesis 生成仿真数据。便宜、量大，但 sim-to-real gap。

**c. 互联网视频**

YouTube / 公开数据集（如 Open X-Embodiment 有 2M+ 机器人轨迹）。

**d. 大模型合成**

用 GPT-6 / Claude 生成"场景描述 + 动作序列"作为训练数据。LLM 世界模型（Voyager / SPRING）。

## 世界模型的 4 类应用

**应用 1：规划（Planning）**

agent 在执行前先在世界模型里跑 N 个候选动作，选最优。

```python
class AgentWithWorldModel:
    def __init__(self, vla_model, world_model):
        self.vla = vla_model
        self.world = world_model
    
    async def plan(self, observation, goal):
        # 生成 N 个候选动作序列
        candidates = await self.vla.generate_candidates(observation, goal, n=10)
        
        # 在世界模型里模拟每个候选
        scores = []
        for action_seq in candidates:
            simulated_states = await self.world.simulate(observation, action_seq, horizon=10)
            scores.append(self.evaluate_goal_achievement(simulated_states, goal))
        
        # 选最高分
        best = candidates[argmax(scores)]
        return best
```

**应用 2：想象训练（Imagination-Based RL）**

agent 在世界模型里"想象"训练，不用真实环境跑，节省 1000x 成本。

代表：**DreamerV3**。在 Minecraft 上达到人类水平，训练只用 1 张 GPU。

**应用 3：异常检测**

真实世界状态偏离世界模型预测 → 异常 → 安全停机。

```python
async def detect_anomaly(real_state):
    predicted_state = await world_model.predict(real_state, action)
    divergence = kl_divergence(real_state, predicted_state)
    
    if divergence > THRESHOLD:
        await emergency_stop()
        return "异常：环境超出模型预测范围"
```

自动驾驶、工业机器人必备——避免在未知环境瞎操作。

**应用 4：零样本迁移**

在世界模型里训练好策略，直接迁移到不同硬件 / 不同任务。Pi 0 / OpenVLA 这类基础模型的核心能力。

## 真实案例：Tesla Optimus 世界模型

Tesla 公开过 Optimus 的世界模型设计：

**架构**：

- 视觉编码器：CLIP-ViT-Large
- 隐空间动力学：基于 Transformer
- 训练数据：Tesla FSD 数据 + Optimus 真实运行数据
- 训练硬件：1 万张 H100

**关键能力**：

- 在未知家庭环境自主导航
- 抓取没见过的物体
- 多步任务（开冰箱 → 拿饮料 → 关冰箱 → 递给用户）

**2026 年现状**：Optimus 在 Tesla 工厂做简单搬运（成功率 92%），家庭场景仍在测试。

## 真实案例：DeepMind DreamerV3

**成就**：在 150+ 个不同任务上达到人类水平，包括 Minecraft、Atari、机器人控制、围棋。

**核心创新**：

- 不需要真实环境交互，全部在"梦"（世界模型）里训练
- 训练效率极高，1 张 GPU 训 1 天达到人类水平
- 算法简单（2000 行代码），可复现

**对我的启发**：做 embodied agent 不一定要真机——世界模型里训够了再上真机，能省 90% 真实数据采集成本。

## 世界模型的 5 大挑战

**挑战 1：长 horizon 预测漂移**

预测 1 秒很准，预测 10 秒后偏离严重。**修法**：hierarchical 预测（短期精确 + 长期粗略）。

**挑战 2：sim-to-real gap**

仿真训练的模型部署到真实世界性能下降。**修法**：domain randomization（仿真里加各种噪声）+ real-world fine-tuning。

**挑战 3：分布外泛化**

训练数据没见过的场景，模型表现差。**修法**：数据多样性 + 大规模预训练。

**挑战 4：实时性**

世界模型推理慢，决策延迟高。**修法**：模型蒸馏 + 硬件加速。

**挑战 5：评估困难**

世界模型预测准不准很难测——你不知道真实世界未来是什么。**修法**：合成 benchmark + 人类评估。

## 实战：搭一个最小世界模型

```python
import torch
import torch.nn as nn

class SimpleWorldModel(nn.Module):
    def __init__(self, obs_dim, action_dim, hidden_dim=256):
        super().__init__()
        # 视觉编码器（简化版）
        self.encoder = nn.Sequential(
            nn.Linear(obs_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
        )
        
        # 动力学：给定当前隐状态 + 动作，预测下一步隐状态
        self.dynamics = nn.GRU(
            input_size=action_dim,
            hidden_size=hidden_dim,
            num_layers=2,
        )
        
        # 解码器：隐状态 → 观测
        self.decoder = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, obs_dim),
        )
        
        # 奖励预测
        self.reward_head = nn.Linear(hidden_dim, 1)
    
    def forward(self, obs_seq, action_seq):
        # 编码观测序列
        hidden = self.encoder(obs_seq[:, 0])
        
        # 在隐空间预测
        outputs = []
        rewards = []
        for t in range(action_seq.size(1)):
            out, hidden = self.dynamics(action_seq[:, t].unsqueeze(0), hidden.unsqueeze(0))
            outputs.append(out.squeeze(0))
            rewards.append(self.reward_head(out.squeeze(0)))
        
        # 解码
        pred_obs = torch.stack([self.decoder(o) for o in outputs], dim=1)
        pred_rewards = torch.stack(rewards, dim=1)
        
        return pred_obs, pred_rewards
```

训练时最小化预测误差：

```python
loss = (
    MSE(pred_obs, true_obs) +
    MSE(pred_rewards, true_rewards) +
    0.1 * reg_loss,
).backward()
optimizer.step()
```

## 选型建议

**做研究 / 发表论文**：用 DreamerV3 / GAIA-1 类架构（学术主流）。

**做工业产品**：用 Isaac Sim + 物理仿真的混合世界模型。

**做个人项目**：用开源 world models on HuggingFace（World Models on HuggingFace 已有 200+ 预训练模型）。

下一章讲仿真训练——怎么在虚拟环境训出能用的 embodied agent。