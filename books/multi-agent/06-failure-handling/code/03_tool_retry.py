"""
06-failure-handling / 03_tool_retry.py

工具层指数退避重试 + Fallback 演示。

运行：
    python 03_tool_retry.py
"""
import random
import time
from functools import wraps


def retry_with_backoff(max_retries=3, base_delay=0.5):
    """指数退避重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt == max_retries - 1:
                        break
                    delay = base_delay * (2 ** attempt)
                    print(f"  重试 {attempt + 1}/{max_retries}，等待 {delay}s...")
                    time.sleep(delay)
            raise last_error
        return wrapper
    return decorator


# ============================================================
# 一个不稳定的工具（50% 失败率）
# ============================================================
@retry_with_backoff(max_retries=3, base_delay=0.5)
def unstable_api(query: str) -> str:
    """模拟一个不稳定的 API 调用（50% 失败）"""
    if random.random() < 0.5:
        raise ConnectionError(f"API 暂时不可用")
    return f"查询结果: {query}"


# ============================================================
# 带 Fallback 的工具
# ============================================================
def weather_with_fallback(city: str) -> str:
    """多级 Fallback"""
    # 第 1 尝试：主 API
    try:
        return primary_weather_api(city)
    except Exception as e:
        print(f"  主 API 失败: {e}")

    # 第 2 尝试：备 API
    try:
        return secondary_weather_api(city)
    except Exception as e:
        print(f"  备 API 失败: {e}")

    # 第 3 降级：返回"不知道"
    return f"{city}: 天气暂时无法查询"


def primary_weather_api(city: str) -> str:
    if random.random() < 0.7:
        raise ConnectionError("主 API 限流")
    return f"{city}: 22°C, 晴"


def secondary_weather_api(city: str) -> str:
    if random.random() < 0.5:
        raise ConnectionError("备 API 也挂了")
    return f"{city}: 20°C, 多云"


# ============================================================
# 演示
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("演示 1: 指数退避重试")
    print("=" * 60)
    for i in range(3):
        try:
            result = unstable_api(f"query-{i}")
            print(f"  ✓ 成功: {result}")
        except Exception as e:
            print(f"  ✗ 最终失败: {e}")

    print("\n" + "=" * 60)
    print("演示 2: 多级 Fallback")
    print("=" * 60)
    for city in ["Tokyo", "Beijing", "Shanghai"]:
        result = weather_with_fallback(city)
        print(f"  {city} → {result}")