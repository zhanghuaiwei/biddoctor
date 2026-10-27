"""purge 生命周期任务集成测试（03 §5）——需要 FJ_TEST_DATABASE_URL"""

import datetime as dt

import pytest

from tests.conftest import TEST_DB_URL

pytestmark = pytest.mark.skipif(not TEST_DB_URL, reason="需要 FJ_TEST_DATABASE_URL")

OLD = dt.datetime.now(dt.UTC) - dt.timedelta(days=400)


@pytest.fixture()
def seeded_expired_project(client):
    """造一个 retain_until 已过期的项目：2 份在册 documents + 过期运维数据"""
    import uuid

    from app.core.db import SessionLocal
    from app.core.security import create_token
    from app.models import AuditLog, Document, LlmCall, Project, Task, User

    with SessionLocal() as db:
        user = User(email=f"purge-{uuid.uuid4().hex[:8]}@test.dev")
        db.add(user)
        db.flush()
        project = Project(
            user_id=user.id, name="过期项目", status="archived",
            retain_until=dt.datetime.now(dt.UTC) - dt.timedelta(days=1),
        )
        db.add(project)
        db.flush()
        doc_new = Document(
            project_id=project.id, role="tender", orig_name="a.pdf",
            stored_path="/nonexistent/a" + uuid.uuid4().hex, sha256="a" * 64,
            size_bytes=1,
        )
        doc_old = Document(
            project_id=project.id, role="bid", orig_name="b.pdf",
            stored_path="/nonexistent/b" + uuid.uuid4().hex, sha256="b" * 64,
            size_bytes=1,
            deleted_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=200),
        )
        db.add_all([doc_new, doc_old])
        db.flush()
        db.add(Task(type="parse", status="succeeded", project_id=project.id,
                    created_at=OLD, finished_at=OLD))
        db.add(LlmCall(purpose="extract", model="glm-4.6", created_at=OLD))
        db.add(AuditLog(action="login", created_at=OLD))
        db.commit()
        yield {
            "user_token": create_token(user.id, "user"),
            "project_id": project.id,
            "doc_new_id": doc_new.id,
            "doc_old_id": doc_old.id,
        }


def _run_purge():
    from app.core.db import SessionLocal
    from app.worker.handlers import purge

    with SessionLocal() as db:
        purge.run({"id": 0}, db)


def test_purge_soft_deletes_expired_docs_and_hard_deletes_ops(client, seeded_expired_project):
    from app.core.db import SessionLocal
    from app.models import AuditLog, Document, LlmCall, Task

    _run_purge()

    with SessionLocal() as db:
        # 1) retain_until 过期 → 在册 documents 软删
        doc_new = db.get(Document, seeded_expired_project["doc_new_id"])
        assert doc_new.deleted_at is not None
        # 2) 软删未满 180 天的不硬删（200 天那份超期应被硬删）
        assert db.get(Document, seeded_expired_project["doc_old_id"]) is None
        # 3) 过期运维数据硬删
        assert db.query(Task).filter(Task.created_at < OLD).count() == 0
        assert db.query(LlmCall).filter(LlmCall.created_at < OLD).count() == 0
        assert db.query(AuditLog).filter(
            AuditLog.created_at < OLD, AuditLog.action != "data_purge"
        ).count() == 0
        # 4) 清理动作写审计
        purge_logs = (
            db.query(AuditLog)
            .filter(AuditLog.action == "data_purge")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert purge_logs is not None
        assert purge_logs.detail.get("documents_soft_deleted") == 1
        assert purge_logs.detail.get("documents_hard_deleted") == 1


def test_daily_purge_task_idempotent(client):
    from app.worker import runner

    bj = dt.datetime.now(dt.UTC) + dt.timedelta(hours=8)
    # 未到 03:05 → 不建
    early = bj.replace(hour=2, minute=0)
    assert runner.enqueue_daily_purge(early) is None
    # 到点 → 建一条
    at_time = bj.replace(hour=4, minute=0)
    tid = runner.enqueue_daily_purge(at_time)
    assert tid is not None
    # 同日重复调用 → 幂等不重建
    assert runner.enqueue_daily_purge(at_time + dt.timedelta(hours=1)) is None
