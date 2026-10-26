"""开发库初始化（唯一建表入口）：建扩展 → alembic upgrade head。
生产同样执行本脚本（容器 command），不再单独维护 create_all 路径。
用法：python scripts/bootstrap.py
"""

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
    print("bootstrap done: extensions + migrations applied (head)")


if __name__ == "__main__":
    main()
