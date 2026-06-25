# 06. 真机部署：sim-to-real 最后一公里

仿真训练出来的策略，部署到真实机器人上往往性能下降 20-50%。这一章讲 sim-to-real 的实战经验——怎么让仿真训练的效果真正迁移到真实世界。

## sim-to-real gap 的 4 类原因

**1. 物理参数不匹配**

仿真里的摩擦系数 / 关节阻尼 / 质量分布 / 电机响应曲线都不可能 100% 精确。

**2. 感知差异**

仿真渲染再真实，和真实摄像头拍出来的图还是不一样——噪声、运动模糊、镜头畸变、自动曝光、HDR。

**3. 执行器差异**

仿真假设关节能瞬间到位，真实电机有延迟、有扭矩限制、有死区。

**4. 动态环境**

仿真里物体是静态的或简单的动力学，真实世界有风、人碰、宠物捣乱、地板打滑。

## 5 种 sim-to-real 方法

### 方法 1：Real-world fine-tuning

**最简单、最常用**。仿真训完，真实环境跑 100-1000 episode 做 fine-tune。

**优点**：直接、有效。

**缺点**：需要真实机器人时间、试错风险。

**实战代码**：

```python
class SimToRealFT:
    def __init__(self, sim_policy, real_robot):
        self.policy = sim_policy
        self.robot = real_robot
    
    async def finetune(self, num_episodes=200):
        optimizer = Adam(self.policy.parameters(), lr=1e-5)
        
        for episode in range(num_episodes):
            obs = await self.robot.reset()
            episode_loss = 0
            
            for step in range(MAX_STEPS):
                # 用当前策略选动作
                action = self.policy(obs)
                
                # 真实执行
                next_obs, done = await self.robot.step(action)
                
                # 计算 loss（基于成功示范或自监督）
                loss = self.compute_loss(action, self.get_demo_action(obs))
                
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                
                episode_loss += loss.item()
                obs = next_obs
                if done:
                    break
```

**实战数据**：仿真成功率 95% → 真实 fine-tune 后 92%，差距从 50% 缩到 3%。

### 方法 2：Domain Randomization（DR）

仿真里加足够多的随机性，模型见过足够多"变体"，迁移到真实世界时不会崩。

**视觉 DR**：

```python
def randomize_visual(env):
    # 随机光照
    env.set_light_intensity(uniform(0.2, 1.5))
    env.set_light_color(uniform_rgb())
    
    # 随机材质
    for obj in env.objects:
        obj.set_color(uniform_rgb())
        obj.set_texture(uniform_choice(texture_lib))
    
    # 随机相机
    env.set_camera_noise(gaussian(0, 0.05))
    env.set_camera_exposure(uniform(0.5, 2.0))
    
    # 随机背景
    env.set_background(uniform_choice(background_lib))
```

**物理 DR**：

```python
def randomize_physics(env):
    for obj in env.objects:
        obj.mass *= uniform(0.8, 1.2)
        obj.friction *= uniform(0.7, 1.3)
    
    for joint in env.robot.joints:
        joint.damping *= uniform(0.8, 1.2)
        joint.friction *= uniform(0.8, 1.2)
```

**DR 的强度经验值**：

- 视觉 DR：**中强度**（太强训练难，太弱迁移差）
- 物理 DR：**中强度**
- 任务 DR（物体初始位置 / 目标位置）：**高强度**

### 方法 3：Domain Adaptation

用 GAN / 对比学习把仿真图像翻译成真实图像。

**代表工作**：

- **CycleGAN-based sim-to-real**
- **MMD-based feature alignment**
- **Contrastive learning for domain-invariant features**

**实战代码骨架**：

```python
class DomainAdaptation:
    def __init__(self):
        self.sim_encoder = VisualEncoder()
        self.real_encoder = VisualEncoder()
        self.discriminator = DomainDiscriminator()
    
    def forward(self, sim_img, real_img):
        # 编码
        sim_feat = self.sim_encoder(sim_img)
        real_feat = self.real_encoder(real_img)
        
        # 对抗训练：让编码器骗过判别器
        sim_domain = self.discriminator(sim_feat)
        real_domain = self.discriminator(real_feat)
        
        # 对抗 loss
        adv_loss = BCE(sim_domain, real_domain)  # 让 sim 编码像 real
        
        # 对比 loss：同一场景 sim 和 real 编码相似
        contrast_loss = NT_Xent(sim_feat, real_feat)
        
        return adv_loss + contrast_loss
```

**优点**：不需要真实数据 fine-tune。

**缺点**：训练复杂、效果不一定好。

### 方法 4：System Identification

精确测量真实机器人参数，在仿真里调成一样的。

```python
# 真实机器人测量
real_params = {
    "link_1_mass": 1.05,  # kg, 真实测量
    "link_1_com": [0.0, 0.0, 0.05],  # m, 重心位置
    "joint_1_damping": 0.5,  # N·m·s/rad
    "joint_1_friction": 0.1,  # N·m
    "motor_1_delay": 5,  # ms
    "motor_1_max_torque": 100,  # N·m
}

# 在仿真里设置
sim.set_robot_params(real_params)
```

**优点**：能消除大部分物理 gap。

**缺点**：测量成本高、参数可能随时间漂移（机械磨损）。

### 方法 5：Foundation Models

用 OpenVLA / π0 / RT-X 这类基础模型，直接 zero-shot 或 few-shot 部署到新硬件。

```python
from transformers import AutoModelForVision2Seq

# 加载 OpenVLA（已在 2M+ 机器人轨迹上预训练）
policy = AutoModelForVision2Seq.from_pretrained("openvla/openvla-7b")

# 直接部署到真实机器人
obs = robot.get_observation()
action = policy.predict_action(obs)
robot.execute(action)
```

**优点**：不用自己训、数据多样性大。

**缺点**：基础模型不一定覆盖你的任务、模型大（7B 参数）、延迟高。

**实战推荐**：**OpenVLA / π0 + 少量真实 fine-tune**。2026 年最实用方案。

## 真实部署的工程坑

**坑 1：通信延迟**

真实机器人和主控电脑之间有通信延迟（ROS / DDS / TCP），5-50ms。仿真里假设 0 延迟。

**修法**：在仿真里加延迟噪声。

```python
# 仿真里加 10-50ms 随机延迟
action_with_delay = apply_latency(action, distribution=uniform(0.01, 0.05))
```

**坑 2：硬件故障**

真实机器人会出故障——关节卡死、传感器漂移、电缆接触不良。

**修法**：加异常检测 + 安全停机。

```python
async def safe_step(action):
    # 检查关节状态
    for joint in robot.joints:
        if joint.current_temp > 80:
            await emergency_stop(reason=f"joint {joint.id} 过热")
            return
    
    # 检查传感器
    if robot.camera.is_black():
        await emergency_stop(reason="摄像头画面异常")
        return
    
    robot.execute(action)
```

**坑 3：标定漂移**

手眼标定（camera → robot base）在使用中会漂移（机械臂振动 / 螺丝松动）。

**修法**：定期重新标定 + 运行时监测。

**坑 4：电源 / 计算资源限制**

实验室跑策略用 RTX 4090，真机部署可能只有 Jetson Orin（~10x 慢）。

**修法**：模型蒸馏 / 量化 / 剪枝。

```python
# 蒸馏：小模型学大模型
teacher = load_policy("openvla-7b")  # 7B 参数
student = SmallPolicy(num_params="100M")  # 1 亿参数

for obs_batch in dataset:
    teacher_action = teacher(obs_batch)
    student_action = student(obs_batch)
    loss = MSE(student_action, teacher_action)
    loss.backward()
    optimizer.step()

# 部署到 Jetson
torch.quantization.quantize_dynamic(student, {nn.Linear}, dtype=torch.qint8)
student.save("policy_jetson.pt")
```

## 真实部署的评估方法

仿真成功率 ≠ 真实成功率。必须有真实评估指标：

**指标 1：任务成功率**

跑 100 次任务，看完成率。

**指标 2：平均完成时间**

快 vs 慢。

**指标 3：失败模式分类**

- 完全失败（没碰到目标）
- 抓取失败（滑落）
- 放置失败（放错位置）
- 安全停机（异常触发）

```python
async def evaluate_real(num_episodes=100):
    success = 0
    failure_modes = {"miss": 0, "slip": 0, "misplace": 0, "safety": 0}
    
    for ep in range(num_episodes):
        result = await run_real_episode()
        if result == "success":
            success += 1
        else:
            failure_modes[result] += 1
    
    return {
        "success_rate": success / num_episodes,
        "failure_breakdown": failure_modes,
    }
```

**指标 4：人类评估**

让真人打分：agent 完成得好不好、自然不自然。

## 真实部署 checklist

```
sim-to-real checklist：
[ ] 物理参数 system identification
[ ] 视觉 / 物理 / 任务 domain randomization
[ ] 通信延迟模拟
[ ] 安全约束（碰撞检测 / 关节限位 / 异常停机）
[ ] 模型蒸馏 / 量化（适配部署硬件）
[ ] 真实评估（任务成功率 + 完成时间 + 失败模式）
[ ] 人在回路（human-in-the-loop）安全开关
[ ] 日志系统（每个 episode 记录 obs / action / result）
[ ] 回滚机制（policy 出问题能切回旧版本）
[ ] 监控告警（成功率突降 / 异常频率突增）
```

10 项。

下一章讲机械臂——embodied agent 最成熟的应用方向。