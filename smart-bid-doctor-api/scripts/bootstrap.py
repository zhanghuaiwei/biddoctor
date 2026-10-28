"""开发库初始化（唯一建表入口）：建扩展 → alembic upgrade head → 平台种子。
生产同样执行本脚本（容器 command），不再单独维护 create_all 路径。
用法：python scripts/bootstrap.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 支持直接 python scripts/xxx.py

from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.core.db import engine


def main() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    # 平台种子（幂等）：内置角色/菜单/参数/定时任务/法务 v1/AI 模型注册
    from app.core.db import SessionLocal
    from app.services import seed_svc

    with SessionLocal() as db:
        stats = seed_svc.run(db)
    print(f"bootstrap done: extensions + migrations applied (head), seed={stats}")


if __name__ == "__main__":
    main()
