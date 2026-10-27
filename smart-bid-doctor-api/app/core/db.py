"""数据库引擎与会话（04 §2 单库基线）。

- pool_pre_ping=True：PG 重启/断连后自愈，避免残留坏连接；
- expire_on_commit=False：commit 后对象仍可读（api 层组装响应不触发二次查询）；
- get_db 每请求一事务：api/service 层显式 commit，异常路径由调用方 rollback
  （范式见 AGENTS.md 事务行）。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
