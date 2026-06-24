"""
10-production-checklist / 02_tool_authorization.py

工具权限控制：每个工具限定可调用的角色。

运行：
    python 02_tool_authorization.py
"""
from enum import Enum
from functools import wraps


class Role(Enum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


# ============================================================
# 工具权限表
# ============================================================
TOOL_PERMISSIONS = {
    "search": [Role.USER, Role.ADMIN, Role.SUPER_ADMIN],
    "read_file": [Role.USER, Role.ADMIN, Role.SUPER_ADMIN],
    "write_file": [Role.ADMIN, Role.SUPER_ADMIN],
    "delete_file": [Role.ADMIN, Role.SUPER_ADMIN],
    "drop_database": [Role.SUPER_ADMIN],
    "send_email": [Role.USER, Role.ADMIN, Role.SUPER_ADMIN],
    "create_ticket": [Role.USER, Role.ADMIN, Role.SUPER_ADMIN],
}


def check_permission(tool_name: str, user_role: Role) -> bool:
    """检查用户角色是否有权调用工具"""
    allowed_roles = TOOL_PERMISSIONS.get(tool_name, [])
    return user_role in allowed_roles


def require_permission(tool_name: str):
    """装饰器：自动检查权限"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, user_role: Role, **kwargs):
            if not check_permission(tool_name, user_role):
                return f"⛔ 权限不足：{user_role.value} 不能调用 {tool_name}"
            return func(*args, user_role=user_role, **kwargs)
        return wrapper
    return decorator


# ============================================================
# 示例工具
# ============================================================
@require_permission("drop_database")
def drop_database(table_name: str, user_role: Role) -> str:
    return f"✓ 删除表 {table_name}"


@require_permission("delete_file")
def delete_file(file_path: str, user_role: Role) -> str:
    return f"✓ 删除文件 {file_path}"


@require_permission("search")
def search(query: str, user_role: Role) -> str:
    return f"✓ 搜索 {query}"


# ============================================================
# 演示
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("工具权限控制演示")
    print("=" * 60)

    print("\n--- 用户尝试 drop database ---")
    print(drop_database("users", user_role=Role.USER))

    print("\n--- 管理员尝试 drop database ---")
    print(drop_database("temp_logs", user_role=Role.ADMIN))

    print("\n--- Super admin drop database ---")
    print(drop_database("temp_logs", user_role=Role.SUPER_ADMIN))

    print("\n--- 用户搜索（普通操作）---")
    print(search("Multi-Agent", user_role=Role.USER))

    print("\n--- 用户删文件 ---")
    print(delete_file("/tmp/junk.txt", user_role=Role.USER))