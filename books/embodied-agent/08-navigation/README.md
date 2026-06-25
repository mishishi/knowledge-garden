# 08. 导航：移动机器人的 embodied agent

导航是 embodied agent 的另一个成熟方向——让机器人从 A 点移动到 B 点。这一章讲室内外导航、SLAM、路径规划、动态避障。

## 导航任务分类

**点导航（Point Navigation）**

从当前位置走到指定坐标。最基础的导航任务。

**物体导航（Object Navigation / ObjectNav）**

"去找到杯子"——机器人必须自己识别 + 找到目标物体。

**图像导航（Image Navigation）**

"去那张照片里的位置"——给一张目标地点照片，机器人导航过去。

**语义导航（Semantic Navigation）**

"去厨房拿苹果"——结合空间推理 + 物体识别 + 多步任务。

**视觉语言导航（VLN）**

"出门左转，第二个路口右转，进门后走到沙发旁边"——基于自然语言指令导航。

## 经典 SLAM 框架

SLAM（Simultaneous Localization and Mapping）= 边建图边定位。导航的"基础设施"。

**视觉 SLAM**：

- **ORB-SLAM3** — 经典、研究主流
- **VINS-Mono / VINS-Fusion** — 视觉 + IMU 融合
- **DSO** — 直接法
- **LSD-SLAM** — 大场景

**激光 SLAM**：

- **Cartographer**（Google）— 2D / 3D，最常用
- **LOAM** — 经典 3D 激光
- **LIO-SAM** — 激光 + IMU 融合

**深度学习 SLAM**（2020+）：

- **DROID-SLAM** — 深度特征，效果 SOTA
- **NeRF-SLAM** — 神经隐式表示
- **GS-SLAM**（3D Gaussian Splatting）— 新方向

**2026 年趋势**：3D Gaussian Splatting SLAM 成为新主流（NeRF / 3DGS / 高斯泼溅）。

## 经典路径规划

SLAM 建好图后，用路径规划算法找最优路径。

**图搜索类**：

- **A*** — 经典启发式搜索
- **Dijkstra** — 无启发式
- **JPS**（Jump Point Search）— 加速 A*

**采样类**：

- **RRT**（Rapidly-exploring Random Tree）— 快速探索
- **RRT*** — 最优 RRT
- **PRM**（Probabilistic Roadmap）— 概率路标

**优化类**：

- **CHOMP**（Covariant Hamiltonian Optimization）— 平滑路径
- **TrajOpt** — 轨迹优化

**实战最常用**：A* / Dijkstra（室内 2D 栅格地图）+ RRT*（3D / 复杂环境）。

## 现代导航：end-to-end 学习

传统 SLAM + 规划是模块化的：定位 → 建图 → 规划 → 控制。现代方法用 end-to-end 学习，直接从传感器输出动作。

**代表工作**：

- **NoMaD**（2024）— 视觉 + 语言导航
- **ViNT**（2023）— 视觉导航基础模型
- **NaviLLM**（2024）— LLM 驱动的导航
- **LM-Nav**（2022）— 用 LLM 做高层规划 + 传统导航做底层

**端到端导航的优势**：

- 不需要显式建图
- 能处理未知环境
- 语义理解强（"去厨房"能直接做，不用先去探索建图）

**劣势**：

- 解释性差（出问题时难 debug）
- 数据需求大
- 泛化到新环境差

## 动态避障

导航最难的部分——避开移动障碍物（人、宠物、其他机器人）。

**经典方法**：

- **DWA**（Dynamic Window Approach）—— 局部规划 + 速度采样
- **TEB**（Timed Elastic Band）—— 时间弹性带
- **MPC**（Model Predictive Control）—— 模型预测控制

**学习方法**：

- **CADRL**（Collision Avoidance with Deep RL）
- **RL-RRT**
- **MAPF**（Multi-Agent Path Finding）

**真实案例**：Boston Dynamics Spot 在仓库里避开 50+ 个移动工人，成功率 99%。

## 视觉语言导航（VLN）

最接近"机器人听懂人话自己走路"的任务。

**任务**：机器人按自然语言指令导航。

```
用户："出门左转，第二个路口右转，走到沙发旁边"
```

**VLN 的 3 个子任务**：

1. **指令理解**：解析自然语言指令
2. **视觉定位**：理解当前看到的环境
3. **行动决策**：决定下一步往哪走

**2026 年 SOTA**：

- **NavGPT**（OpenAI）— 用 GPT-4V 做导航规划
- **MapGPT**（2024）— 用地图增强 LLM 导航
- **NaVid**（2024）— 视频版 VLN

**实测性能**：VLN 在熟悉环境成功率 70-80%，陌生环境 40-50%。

## 室外导航（自动驾驶）

室外导航 = 自动驾驶。这一块单独一个大产业。

**仿真平台**：CARLA（前面讲过）。

**核心任务**：

- 车道保持
- 跟车 / 变道
- 红绿灯 / 标志识别
- 行人 / 自行车避让
- 高速巡航
- 城区驾驶

**2026 年自动驾驶现状**：

- **Waymo**：美国 L4 robotaxi，凤凰城 / 旧金山运营
- **特斯拉 FSD**：L2+ 辅助驾驶，量产
- **百度 Apollo**：中国 L4 robotaxi，武汉 / 北京
- **小马智行 / 文远知行**：中国 L4 robotaxi
- **华为 ADS**：量产 L2++

**端到端自动驾驶**：

- **Tesla FSD V12**（2024）—— 端到端神经网络
- **Wayve**（英国）—— AV 基础模型
- **Waymo** —— 也在转端到端

**趋势**：传统模块化（感知 + 规划 + 控制）转向端到端神经网络。

## 导航的实战性能

我跟踪过 3 个室内导航项目的性能：

| 项目 | 任务 | 成功率 | 平均完成时间 | 失败模式 |
|------|------|--------|------------|---------|
| 室内 2D 点导航 | 5m 范围内 | 98% | 12s | 极少 |
| 室内 ObjectNav | 找指定物体 | 82% | 45s | 找不到目标 |
| 室内 VLN | 自然语言指令 | 68% | 90s | 走错方向 / 卡住 |

**VLN 任务最复杂**，需要语义理解 + 视觉定位 + 长 horizon 规划。

## 实战代码骨架

```python
class NavigationPolicy:
    def __init__(self, vlm, planner):
        self.vlm = vlm  # 视觉语言模型
        self.planner = planner  # 路径规划器
    
    async def navigate(self, instruction, current_obs):
        # 1. 用 VLM 解析指令，提取关键路标
        landmarks = await self.vlm.extract_landmarks(instruction)
        # landmarks = ["door", "kitchen", "apple"]
        
        # 2. 局部规划 + 控制循环
        for step in range(MAX_STEPS):
            # 观察当前环境
            obs = self.robot.get_observation()
            
            # 用 VLM 决策下一步动作
            action = await self.vlm.predict_action(
                instruction, obs, landmarks,
            )
            # action = "go_forward", "turn_left", "turn_right", "stop"
            
            # 执行动作
            self.robot.execute(action)
            
            # 检查是否到达目标
            if self.is_at_goal(landmarks):
                return "success"
        
        return "timeout"
```

## 选型建议

**做研究 / 发论文**：Habitat + AI2-THOR（室内）/ CARLA（室外）+ 端到端学习方法。

**做工业产品**：Cartographer + ROS Navigation（成熟稳定）。

**做个人项目**：Habitat + NoMaD / ViNT 基础模型。

**做自动驾驶**：CARLA + Waymax + 端到端学习。

## 关键挑战

**挑战 1：长距离导航**

100 米以上的导航，传统 SLAM 容易漂移。**修法**：拓扑地图 + 视觉地标。

**挑战 2：动态环境**

人在前面走，机器人必须实时避障。**修法**：DWA / MPC + 多传感器融合。

**挑战 3：语义理解**

"去厨房拿苹果"——机器人要认识"厨房"、"苹果"。**修法**：开放词汇检测（Grounding DINO / YOLO-World）。

**挑战 4：多机器人协作**

多个机器人在同一空间，不能撞。**修法**：MAPF + 通信协议。

下一章讲家庭服务机器人——具身智能最接近消费者市场的应用。