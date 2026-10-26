"""集成测试夹具：需要真实 PostgreSQL（pgvector）。
设置 FJ_TEST_DATABASE_URL（如 postgresql+psycopg://feijian:feijian@localhost:5432/feijian_test）启用；
未设置时集成测试自动跳过（CI 中由 postgres service 提供）。"""

import os

import pytest

TEST_DB_URL = os.environ.get("FJ_TEST_DATABASE_URL")

os.environ.setdefault("FJ_ENV", "dev")
os.environ.setdefault("FJ_UPLOAD_DIR", "/tmp/fj_test_uploads")
if TEST_DB_URL:
    # 必须在 app 首次导入前生效（get_settings 有 lru_cache）
    os.environ["FJ_DATABASE_URL"] = TEST_DB_URL


def make_minimal_pdf() -> bytes:
    """pypdf 可读的单页最小 PDF（集成测试上传用）。
    用 pypdf 自身生成而非手写字节串：手写结构缺 xref 等要素，
    pypdf 版本升级后容易判为损坏（PARSE_CORRUPT）。"""
    import io

    from pypdf import PdfWriter

    buf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
def client():
    if not TEST_DB_URL:
        pytest.skip("需要 FJ_TEST_DATABASE_URL 才能跑集成测试", allow_module_level=False)
    os.environ["FJ_DATABASE_URL"] = TEST_DB_URL
    from alembic.config import Config
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from alembic import command
    from app.core.db import engine
    from app.main import app

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    yield TestClient(app)

    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
