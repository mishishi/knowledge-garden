# 04. 仿真训练：embodied agent 的核心工程

真实机器人训练成本极高——一台 Optimus 一年折旧 + 电费 + 维护 ≈ 30 万人民币，1 天能跑的实验次数 < 100。

仿真训练是 embodied agent 的**核心工程能力**。在虚拟环境训出 99% 的能力，再用 1% 真实数据微调。

这一章讲仿真训练的全流程：场景搭建、任务设计、强化学习、sim-to-real。

## 为什么必须仿真训练

**真实训练 3 个致命问题**：

**1. 成本高**：1 台机器人 1 小时实验 ≈ ¥500，1 万小时实验 = ¥500 万。

**2. 速度慢**：真实机器人 1 秒 1 个动作决策，仿真 1 秒可以跑 1000 个并行环境。

**3. 安全风险**：训练早期策略很烂，机械臂乱挥可能砸坏硬件、伤到人。仿真里随便乱搞。

**数据对比**：

| | 真实训练 | 仿真训练 |
|---|---------|---------|
| 1 小时成本 | ¥500 | ¥10 |
| 1 秒决策数 | 1-10 | 100-10000（并行）|
| 试错风险 | 高（砸坏硬件）| 零（虚拟）|
| 数据多样性 | 受限（真实物理）| 无限（domain randomization）|

## 仿真训练全流程

```
[任务定义] → [场景搭建] → [仿真器选择] → [策略训练] → [sim-to-real 迁移]
```

### Step 1：任务定义

明确 agent 要学什么。常见任务分类：

**导航任务**：从 A 点到 B 点（避开障碍物）。
**抓取任务**：把物体抓起来放到指定位置。
**操作任务**：开门、倒水、拧瓶盖、按按钮。
**多步任务**：开冰箱 → 拿饮料 → 关冰箱 → 递给用户。
**长 horizon 任务**：整理房间、做一道菜。

任务定义要包含：

- **观测空间**：摄像头 RGB / 深度 / 激光雷达 / 触觉 / proprioception
- **动作空间**：关节角度 / 末端位姿 / 离散动作 / 速度指令
- **奖励函数**：成功 +1，失败 -1，过程奖励（中间步骤）
- **终止条件**：成功 / 失败 / 超时

### Step 2：场景搭建

**3 种方式**：

**a. 用仿真器自带场景库**

Isaac Lab / Genesis / Habitat 都内置场景：办公室、家庭、工厂、户外。直接用，省时间。

**b. 从公开数据集导入**

- **Matterport3D**：室内 3D 扫描数据集
- **Replica**：室内场景数据集
- **HM3D**：Habitat-Matterport 3D
- **Open X-Embodiment**：机器人轨迹数据集

**c. 自己造场景**

用 Blender / Unreal Engine 5 建模，导出 USD / FBX 给仿真器。最灵活但最费时。

### Step 3：仿真器选择

按任务选：

| 任务 | 推荐仿真器 |
|------|-----------|
| 机械臂抓取 | Isaac Lab / MuJoCo / SAPIEN |
| 室内导航 | Habitat / AI2-THOR / iGibson |
| 自动驾驶 | CARLA / Waymax |
| 移动操作 | Isaac Lab / Genesis |
| 灵巧手 | SAPIEN / Isaac Lab |
| 人形机器人 | Genesis / Isaac Lab / MuJoCo |

### Step 4：策略训练

3 种主流方法：

**方法 1：模仿学习（IL）**

从人类示范数据学习。Open X-Embodiment 提供了 2M+ 机器人轨迹，直接在这些数据上做 supervised fine-tuning。

```python
class ImitationLearning:
    def __init__(self, vla_model):
        self.model = vla_model
    
    async def train_step(self, obs_seq, action_seq):
        # 预测动作
        pred_actions = self.model(obs_seq)
        
        # 计算 loss
        loss = MSE(pred_actions, action_seq)
        
        loss.backward()
        self.optimizer.step()
```

**优点**：稳定、能用真实数据。

**缺点**：需要大量示范数据、不能超越示范水平。

**方法 2：强化学习（RL）**

让 agent 在仿真里试错，根据奖励信号学。PPO / SAC / TD3 是主流算法。

```python
class RLTraining:
    async def train_step(self):
        # 1. 在仿真里跑 N 步
        obs_seq, action_seq, reward_seq = await self.collect_trajectories(n_steps=10000)
        
        # 2. 计算 advantage（GAE）
        advantages = self.compute_gae(reward_seq, value_seq)
        
        # 3. PPO 更新
        loss = self.ppo_loss(obs_seq, action_seq, advantages)
        loss.backward()
        self.optimizer.step()
```

**优点**：能超越人类、发现新策略。

**缺点**：不稳定、奖励函数难设计。

**方法 3：IL + RL 混合**

先用 IL 学到基础策略，再用 RL fine-tune。

代表：**RLDG**（Reinforcement Learning from Demonstration Generation）、**HIL-SERL**（Human-in-the-Loop Sample-Efficient RL）。

**实战推荐**：**IL 起手 + RL 精调**。最稳。

### Step 5：Domain Randomization

**核心思想**：仿真里加各种随机性，让模型见过足够多的"变体"，迁移到真实世界时不会崩。

随机化对象：

**视觉随机化**：

- 光照强度（明亮 / 昏暗 / 强光）
- 物体颜色 / 纹理
- 相机噪声 / 模糊
- 背景杂物

**物理随机化**：

- 物体质量（±20%）
- 摩擦系数（±30%）
- 关节阻尼
- 模拟器物理参数

**任务随机化**：

- 物体初始位置 / 姿态
- 目标位置
- 障碍物配置

```python
class RandomizedEnv:
    def reset(self):
        # 视觉随机化
        self.env.set_light_intensity(uniform(0.3, 1.0))
        self.env.set_object_color(uniform_rgb())
        
        # 物理随机化
        for obj in self.env.objects:
            obj.mass *= uniform(0.8, 1.2)
            obj.friction *= uniform(0.7, 1.3)
        
        # 任务随机化
        target_pos = uniform_box(-1, 1, 3)
        obj_pos = uniform_box(-1, 1, 3)
        
        return self.env.reset(obj_pos=obj_pos, target_pos=target_pos)
```

**实战经验**：DR 太弱 sim-to-real gap 大；DR 太强训练困难。**经验值**：视觉 DR 强度中、物理 DR 强度中、任务 DR 强度高。

### Step 6：Sim-to-Real 迁移

**5 种主流方法**：

**1. Real-world fine-tuning**

仿真训完，真实环境跑 100-1000 个 episode 做 fine-tuning。最简单。

**2. Domain Adaptation**

用 GAN / 对比学习把仿真图像翻译成真实图像，再训。

**3. System Identification**

精确测量真实机器人参数（质量、阻尼、延迟），在仿真里调成一样的。

**4. Real2Sim2Real**

真实数据训仿真器（数字孪生），仿真里训策略，再迁移回真实。

**5. Foundation Models**

用 OpenVLA / π0 这类基础模型，已经见过大量真实 + 仿真数据，直接部署或少量 fine-tune。

**实战推荐**：**Foundation Models + Real-world fine-tuning**。成本最低、效果最好。

## 仿真训练的实战性能

我跟踪过一个抓取任务（把不同物体放进盒子里）的仿真训练：

| 训练方式 | 仿真成功率 | 真实成功率 | 训练时长 | 训练成本 |
|---------|----------|----------|---------|---------|
| 仅仿真（无 DR）| 95% | 38% | 12 小时 | ¥50 |
| 仿真 + 中 DR | 92% | 65% | 18 小时 | ¥80 |
| 仿真 + 强 DR | 88% | 82% | 36 小时 | ¥150 |
| 仿真 + 强 DR + 真实 FT | 95% | 94% | 36 + 2 小时 | ¥150 + ¥1000 |

**强 DR + 真实 fine-tune** 性价比最高——仿真成本 ¥150，真实微调 ¥1000，总 ¥1150；真实成功率 94%。

## 实战 checklist

```
仿真训练 checklist：
[ ] 任务定义清晰（观测 / 动作 / 奖励 / 终止）
[ ] 场景搭建（用库 or 自建）
[ ] 仿真器选择（按任务）
[ ] 训练方法选择（IL / RL / 混合）
[ ] Domain randomization（视觉 + 物理 + 任务）
[ ] Sim-to-real 方案（FT / DR / Foundation Model）
[ ] 评估指标（仿真成功率 / 真实成功率）
[ ] 安全约束（碰撞检测 / 关节限位）
[ ] 数据管理（每次实验 config + log 留档）
```

9 项。

下一章讲主流仿真平台深度对比——Isaac Lab / Genesis / MuJoCo / Habitat / CARLA 各自怎么选。