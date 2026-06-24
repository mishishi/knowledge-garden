"""
10-production-checklist / 11_prompt_versioning.py

Prompt 版本管理：每个 Agent 的 prompt 放配置文件，支持回滚。

运行：
    python 11_prompt_versioning.py
"""
import json
import time
from pathlib import Path

# ============================================================
# Prompt 配置（生产推荐放 YAML/JSON 文件）
# ============================================================
PROMPTS_DIR = Path("prompts")


def ensure_prompts_dir():
    PROMPTS_DIR.mkdir(exist_ok=True)


def save_prompt_version(agent_name: str, version: str, prompt: dict):
    """保存 prompt 版本"""
    ensure_prompts_dir()
    path = PROMPTS_DIR / f"{agent_name}_{version}.json"
    path.write_text(json.dumps(prompt, indent=2, ensure_ascii=False))
    return path


def load_prompt(agent_name: str, version: str = "latest") -> dict:
    """加载 prompt 版本"""
    if version == "latest":
        # 找最新的版本
        files = list(PROMPTS_DIR.glob(f"{agent_name}_v*.json"))
        if not files:
            return {}
        latest = max(files, key=lambda p: p.stat().st_mtime)
        return json.loads(latest.read_text())
    else:
        path = PROMPTS_DIR / f"{agent_name}_{version}.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text())


# ============================================================
# 部署记录
# ============================================================
def record_deployment(version: str, prompts: dict):
    """记录每次部署"""
    deploy_log = {
        "version": version,
        "prompts": prompts,
        "deployed_at": time.time(),
    }
    log_path = Path("deploy_log.jsonl")
    with log_path.open("a") as f:
        f.write(json.dumps(deploy_log, ensure_ascii=False) + "\n")
    return deploy_log


# ============================================================
# 演示
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Prompt 版本管理演示")
    print("=" * 60)

    # 保存 v1
    print("\n--- 保存 v1 ---")
    p_v1 = save_prompt_version(
        "researcher",
        "v1",
        {
            "role": "研究员",
            "goal": "调研 {topic}",
            "backstory": "你是研究员。",
        },
    )
    print(f"  保存到 {p_v1}")

    # 保存 v2
    print("\n--- 保存 v2 ---")
    p_v2 = save_prompt_version(
        "researcher",
        "v2",
        {
            "role": "研究员",
            "goal": "深入调研 {topic}，输出 3 条关键事实",
            "backstory": "你是资深研究员，专注于深度事实输出。",
        },
    )
    print(f"  保存到 {p_v2}")

    # 加载特定版本
    print("\n--- 加载 v1 ---")
    prompt = load_prompt("researcher", "v1")
    print(f"  {prompt}")

    print("\n--- 加载最新 ---")
    prompt = load_prompt("researcher", "latest")
    print(f"  {prompt}")

    # 记录部署
    print("\n--- 记录部署 ---")
    record_deployment("v2.1", {"researcher": "v2", "writer": "v1"})

    print("\n=== 回滚演示 ===")
    print("  发现 v2 效果不好 → 改用 load_prompt('researcher', 'v1') 即可")