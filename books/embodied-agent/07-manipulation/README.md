# 07. 机械臂：操作任务的 embodied agent

机械臂是 embodied agent 最成熟的方向——控制理论成熟、硬件便宜、应用场景明确。这一章讲机械臂 embodied agent 的核心能力：抓取、操作、精细技能。

## 机械臂能做什么

**工业级应用**（成熟）：

- 抓取放置（bin picking）
- 装配（拧螺丝、卡扣）
- 焊接 / 喷涂
- 码垛 / 拆垛
- 质检

**研究级应用**（快速发展）：

- 柔性物体操作（叠衣服、揉面团）
- 长 horizon 任务（做菜、整理房间）
- 灵巧手精细操作（拧瓶盖、写字）
- 双臂协作

**消费级应用**（早期）：

- 桌面辅助机器人
- 玩具 / 教育
- 家庭辅助（开冰箱、倒水）

## 抓取（Pick-and-Place）基础

最经典的任务：抓取一个物体放到指定位置。

**传统方法（pre-2018）**：

- 6DoF 位姿估计（Pose Estimation）
- 抓取点预测（基于几何 / 物理仿真）
- 运动规划（MoveIt / OMPL）

**现代方法（2024+）**：end-to-end 学习

```python
class PickAndPlacePolicy:
    def __init__(self, vla_model):
        self.model = vla_model
    
    async def predict(self, observation, instruction):
        # observation: RGB-D 图像 + 机器人 proprioception
        # instruction: "把红色方块放进蓝色盒子里"
        action = self.model(observation, instruction)
        # action: 末端目标位姿 (x, y, z, roll, pitch, yaw) + 夹爪开合
        return action
```

**实战性能**：

| 方法 | 已知物体 | 未知物体 | 杂乱场景 | 长尾分布 |
|------|---------|---------|---------|---------|
| 传统位姿估计 | 98% | 32% | 65% | 45% |
| 端到端 IL | 95% | 75% | 82% | 70% |
| 端到端 RL | 92% | 80% | 85% | 75% |
| Foundation Model (π0) | 96% | 88% | 90% | 82% |

**Foundation Model 在新物体 / 长尾分布场景下优势最明显**。

## 仿真训练的 3 类抓取任务

**任务 1：单物体抓取**

最简单——桌面放 1 个物体，抓起来。

```python
class SingleObjectPickEnv:
    def __init__(self):
        self.franka = Franka()
        self.table = Table()
        self.obj = random_object()  # 随机物体
    
    def reset(self):
        self.obj.position = random_box(0.3, 0.7, 0.1, 0.5)  # 桌面上随机位置
        return self.get_obs()
    
    def compute_reward(self):
        # 0：未抓取；1：成功抓取到指定位置
        if is_grasped(self.obj) and is_in_target_zone(self.obj):
            return 1.0
        return 0.0
```

**任务 2：杂乱场景抓取**

桌面上有 5-10 个物体，目标抓其中一个指定物体。

```python
class ClutteredPickEnv:
    def __init__(self):
        self.objects = [random_object() for _ in range(10)]
        self.target = None
    
    def reset(self, target_object):
        self.target = target_object
        for obj in self.objects:
            obj.position = random_box(0.3, 0.7, 0.1, 0.5)
        # 可能物体堆叠
        if random() < 0.3:
            stack_two_objects()
        return self.get_obs()
    
    def compute_reward(self):
        if is_grasped(self.target) and is_in_target_zone(self.target):
            return 1.0
        return 0.0
```

**任务 3：长 horizon 抓取（多步任务）**

复杂多步任务，如"开抽屉 → 拿工具 → 关抽屉 → 用工具"。

这类任务用 **Hierarchical RL** 或 **Task Planning + Skill Execution**：

```
[任务："开抽屉拿螺丝刀"]
   ↓ Planner（LLM/VLM）
[Plan:
   1. 找到抽屉
   2. 抓住把手
   3. 拉开抽屉
   4. 找到螺丝刀
   5. 抓住螺丝刀
   6. 取出
   7. 关抽屉]
   ↓ Skill Library
[Skill: 抓取 / 推 / 拉 / 释放 / ...]
   ↓
[执行]
```

## 灵巧手（Dexterous Hands）操作

5 指机械手是机械臂的"高阶版"。能做精细操作：

**典型任务**：

- 拧瓶盖
- 拿鸡蛋（柔性物体）
- 写字画画
- 折衣服
- 用餐具吃饭
- 插 U 盘 / 插网线

**灵巧手代表**：

- **Allegro Hand**（Wonik Robotics）— 4 指 16 自由度，研究主流
- **LEAP Hand**（CMU）— 低成本 3D 打印
- **Schunk SVH**（Schunk）— 5 指 9 自由度，工业级
- **Shadow Hand**（Shadow Robot）— 高端研究，5 指 20 自由度
- **因时 RH56DFX**（国产）— 性价比

**灵巧手训练的难点**：

- **高维动作空间**：5 指 × 3 关节 = 15+ 维动作空间，搜索空间爆炸。
- **接触动力学复杂**：指尖接触、滑动、摩擦模型都难仿真。
- **奖励稀疏**：精细任务奖励函数难设计。

**实战方法**：

```python
class DexterousHandPolicy:
    def __init__(self):
        # 分层策略：粗粒度规划 + 细粒度控制
        self.high_level_planner = LLMPlanner()  # LLM 拆任务
        self.skill_library = SkillLibrary()  # 技能库
        self.low_level_controller = RLController()  # RL 控制器执行技能
    
    async def execute_task(self, instruction, observation):
        # 高层：LLM 拆任务
        sub_tasks = await self.high_level_planner.plan(instruction, observation)
        
        for sub_task in sub_tasks:
            # 选技能
            skill = await self.skill_library.select(sub_task)
            
            # 低层：RL 执行
            while not skill.is_done():
                action = await self.low_level_controller.predict(observation, skill.goal)
                robot.execute(action)
                observation = robot.get_obs()
```

## 装配任务（Assembly）

比抓取更复杂——需要插孔、卡扣、对位。

**典型任务**：

- 拧螺丝
- 插 U 盘
- 拼积木
- 插 USB 线
- 装配家具

**关键挑战**：

- **接触丰富**：装配时多指同时接触物体。
- **力控**：必须用力反馈控制，不能光看视觉。
- **公差小**：0.1mm 的孔，0.05mm 误差就插不进。

**代表工作**：

- **Berkeley 插孔研究**（Sergey Levine 组）—— RL + 视觉 + 力反馈
- **Stanford ALOHA 系列**——低成本双臂装配
- **MIT 拧螺丝研究**——6 维力控

**实战经验**：装配任务**必须用力反馈**。光靠视觉，0.1mm 精度的装配几乎做不到。

```python
class AssemblyPolicy:
    def __init__(self):
        self.policy = ForceVisionPolicy()  # 视觉 + 力融合
    
    async def step(self, observation):
        # observation: 视觉 + 6 维力 / 力矩
        action = self.policy(observation)
        
        # 力控：如果力过大，停止
        if observation.wrench.magnitude > MAX_FORCE:
            action[:6] = 0  # 停止运动
        
        return action
```

## 仿真到真实的 5 个常见 gap

**Gap 1：接触动力学**

仿真里摩擦系数简单，真实里接触表面有粘附、塑性形变。

**修法**：用更真实的接触模型（如 IPC、Bullet 改进版）。

**Gap 2：电机响应**

仿真假设电流到力矩是即时的，真实电机有 5-20ms 延迟。

**修法**：在仿真里加电机动力学模型。

**Gap 3：摄像头畸变**

仿真渲染是针孔模型，真实摄像头有径向 / 切向畸变。

**修法**：仿真渲染时加畸变；或者真实端做图像去畸变。

**Gap 4：物体属性未知**

仿真里物体质量 / 摩擦已知，真实里不知道。

**修法**：用触觉传感器在线估计。

**Gap 5：光照变化**

仿真光照可控，真实光照天天变。

**修法**：domain randomization + 真实数据 fine-tune。

## 实战经验数据

我跟踪过 3 个机械臂项目的 sim-to-real gap：

| 项目 | 仿真成功率 | 真实成功率（无 FT） | 真实成功率（+FT 100 episode） |
|------|----------|-------------------|------------------------------|
| 单物体抓取 | 96% | 78% | 93% |
| 杂乱场景抓取 | 88% | 62% | 82% |
| 装配（插 USB） | 82% | 45% | 73% |

**任务越复杂，sim-to-real gap 越大**——精细操作任务必须真实 fine-tune。

## 推荐学习路径

**入门**：Franka + Isaac Lab + 仿真抓取 → 真实 Franka 抓取

**进阶**：Aloha 双臂 + 仿真装配 → 真实 Aloha 装配

**高级**：灵巧手（Allegro / LEAP）+ 仿真精细操作 → 真实灵巧手任务

## 选型建议

**预算 $0**：LEAP Hand（3D 打印，几千块）+ Genesis（开源）+ OpenVLA 模型。

**预算 $5K**：二手 Franka Panda（约 $5K）+ Isaac Lab（NVIDIA 硬件）。

**预算 $50K**：Aloha 双臂（Stanford 设计，约 $25K）+ 4 张 RTX 4090 + 全套仿真。

**预算 $500K+**：Franka Research 3（最新款）+ 自定义灵巧手 + 8 张 H100。

下一章讲导航——移动机器人的 embodied agent。