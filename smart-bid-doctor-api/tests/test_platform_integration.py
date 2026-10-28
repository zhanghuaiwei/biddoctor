"""平台域集成测试（05 §11 实装门禁）：RBAC 越权 404 同形 / 平台功能留痕断言 /
报告闭环 / 法务签署留痕 —— 需要 FJ_TEST_DATABASE_URL"""

import uuid

import pytest

from tests.conftest import TEST_DB_URL

pytestmark = pytest.mark.skipif(not TEST_DB_URL, reason="需要 FJ_TEST_DATABASE_URL")


def _email(client, local: str) -> tuple[str, str]:
    email = f"{local}-{uuid.uuid4().hex[:6]}@test.dev"
    code = client.post("/api/auth/email-code", json={"email": email}).json()["dev_code"]
    return email, code


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _drain_tasks(max_rounds: int = 50) -> None:
    """内联任务排空：复用 runner 的 claim SQL 与 HANDLERS，把队列跑空（替代独立 worker 进程）。"""
    from app.core.db import SessionLocal
    from app.worker.runner import CLAIM_SQL, HANDLERS

    for _ in range(max_rounds):
        with SessionLocal() as db:
            row = db.execute(CLAIM_SQL).mappings().first()
        if row is None:
            return
        with SessionLocal() as db:
            HANDLERS[row["type"]](dict(row), db)


@pytest.fixture()
def user_token(client):
    email, code = _email(client, "plat-user")
    r = client.post("/api/auth/login", json={"email": email, "code": code})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture()
def admin_token(client):
    """seed_admin 路径：未绑定角色的管理员 = 全量权限（{"*"}）"""
    from app.core.security import create_token
    from app.models import User

    email = f"plat-admin-{uuid.uuid4().hex[:6]}@test.dev"
    from app.core.db import SessionLocal

    with SessionLocal() as db:
        u = User(email=email, role="admin")
        db.add(u)
        db.commit()
        uid = u.id
    return create_token(uid, "admin")


# ── RBAC 越权 404 同形（05 §11）──────────────────────────────────────────────


def test_admin_routes_404_same_shape_for_user(client, user_token):
    """普通用户访问管理端 → 404 同形（不泄露管理面存在性），三种常见方法各验一条"""
    h = _auth(user_token)
    for method, path in (
        ("get", "/api/admin/monitor/overview"),
        ("post", "/api/admin/sys/users/1/ban"),
        ("put", "/api/admin/sys/configs/quota.free_monthly"),
    ):
        r = getattr(client, method)(path, headers=h, **({"json": {}} if method != "get" else {}))
        assert r.status_code == 404, (method, path, r.status_code)
        assert r.json()["error"]["code"] == "NOT_FOUND"


def test_admin_routes_require_token(client):
    r = client.get("/api/admin/sys/users")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


# ── 参数配置：改值即生效 + sys_config_update 审计留痕（05 §11）───────────────


def test_config_update_writes_audit(client, admin_token):
    from app.core.db import SessionLocal
    from app.models import AuditLog

    h = _auth(admin_token)
    r = client.put(
        "/api/admin/sys/configs/quota.free_monthly",
        headers=h, json={"value": "5"},
    )
    assert r.status_code == 200, r.text
    rid = r.headers.get("X-Request-ID")
    with SessionLocal() as db:
        row = (
            db.query(AuditLog)
            .filter(AuditLog.action == "sys_config_update")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert row is not None
        assert row.detail.get("request_id") == rid
        assert row.detail.get("new") == "5"
    # 坏值拒绝
    r = client.put("/api/admin/sys/configs/quota.free_monthly", headers=h, json={"value": "abc"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "CONFIG_VALUE_INVALID"


# ── 公告：发布 → 用户端可见（05 §3.3）───────────────────────────────────────


def test_notice_publish_flow_visible_to_user(client, admin_token):
    h = _auth(admin_token)
    r = client.post("/api/admin/sys/notices", headers=h, json={
        "title": "维护通知", "content": "今晚 22:00 例行维护", "level": "warn", "type": "notice",
    })
    assert r.status_code == 201, r.text
    nid = r.json()["id"]
    r = client.post(f"/api/admin/sys/notices/{nid}/publish", headers=h)
    assert r.status_code == 200, r.text
    # 用户端（公开端点）可见
    r = client.get("/api/notices")
    assert r.status_code == 200
    assert any(n["id"] == nid for n in r.json())
    # 非登录端点：公开可读
    r2 = client.get("/api/notices")
    assert r2.status_code == 200


# ── 法务签署留痕（05 §8 / PIPL）─────────────────────────────────────────────


def test_legal_sign_writes_audit(client, user_token):
    from app.core.db import SessionLocal
    from app.models import AuditLog, UserAgreement

    h = _auth(user_token)
    r = client.get("/api/legal/current", headers=h)
    assert r.status_code == 200
    docs = r.json()["documents"]
    signed = set(r.json()["signed_ids"])
    pending_ids = [d["id"] for d in docs if d["id"] not in signed]
    assert pending_ids, "bootstrap 种子应有生效版法务文档"
    r = client.post("/api/legal/agreements", headers=h, json=pending_ids)
    assert r.status_code == 200, r.text
    assert set(r.json()["signed_ids"]) >= set(pending_ids)
    # 留痕：签署记录 + 审计
    with SessionLocal() as db:
        assert (
            db.query(UserAgreement)
            .filter(UserAgreement.legal_doc_id.in_(pending_ids))
            .count()
        ) >= 1
        row = (
            db.query(AuditLog)
            .filter(AuditLog.action == "agreement_signed")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert row is not None and row.detail.get("legal_doc_ids")


# ── 报告闭环：上传→解析→清单任务→报告落库→导出（M1/D 非引擎部分）────────────


def test_checklist_report_loop(client, user_token):
    import io

    import fitz

    from app.core.db import SessionLocal
    from app.models import AuditLog

    # 生成一份含标题层级的多页文本 PDF（避开 make_minimal_pdf 的空页 need_review 路径）
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "第一章 投标须知", fontsize=18)
    page.insert_text((72, 140), "1.1 投标人须具备独立法人资格，提供营业执照副本复印件。", fontsize=11)
    page.insert_text((72, 160), "1.2 投标文件未按要求签字盖章的，作废标处理。", fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()

    h = _auth(user_token)
    r = client.post("/api/projects", headers=h, json={"name": "平台测试项目", "industry": "general"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    r = client.post(
        f"/api/projects/{pid}/documents",
        headers=h,
        files={"file": ("tender.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"role": "tender"},
    )
    assert r.status_code == 201, r.text
    task_id = r.json()["task_id"]

    # 内联排空任务队列（parse → extract 链）
    _drain_tasks()
    st = client.get(f"/api/tasks/{task_id}", headers=h)
    assert st.json()["status"] == "succeeded", st.text

    # 生成清单报告（202）→ 轮询 checklist 任务终态
    r = client.post(f"/api/projects/{pid}/checklist-report", headers=h)
    assert r.status_code == 202, r.text
    ck_task = r.json()["task_id"]
    _drain_tasks()
    st = client.get(f"/api/tasks/{ck_task}", headers=h)
    assert st.json()["status"] == "succeeded", st.text

    # 报告落库可查 + 免责确认 + 导出 200
    r = client.get(f"/api/projects/{pid}/reports", headers=h)
    assert r.status_code == 200
    reports = r.json()["items"]
    assert reports and reports[0]["kind"] == "checklist"
    rid = reports[0]["id"]
    r = client.post(f"/api/reports/{rid}/ack", headers=h)
    assert r.status_code == 200 and r.json()["disclaimer_ack"] is True
    r = client.get(f"/api/reports/{rid}/export", headers=h)
    assert r.status_code == 200
    assert b"AI" in r.content  # AIGC 标识（05 §9.2）
    # 阅后即焚：报告生成后项目文档应已软删
    r = client.get(f"/api/projects/{pid}/documents", headers=h)
    assert all(d["id"] is not None for d in r.json()["items"])
    assert len(r.json()["items"]) == 0  # 阅后即焚软删后列表为空
    # 审计留痕：report_generated / report_ack / report_exported
    with SessionLocal() as db:
        actions = {a for (a,) in db.query(AuditLog.action).order_by(AuditLog.id.desc()).limit(50).all()}
        assert "report_generated" in actions
        assert "report_ack" in actions
        assert "report_exported" in actions


# ── 附件上传/归属/下载（05 §7）──────────────────────────────────────────────


def test_attachment_upload_download(client, user_token, admin_token):
    import io

    png = b"\x89PNG\r\n\x1a\n" + b"0" * 128
    h = _auth(user_token)
    r = client.post(
        "/api/attachments",
        headers=h,
        files={"file": ("receipt.png", io.BytesIO(png), "image/png")},
        data={"module": "profile"},
    )
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    # 类型不符拒绝
    r = client.post(
        "/api/attachments",
        headers=h,
        files={"file": ("evil.png", io.BytesIO(b"MZ" + b"0" * 100), "image/png")},
        data={"module": "profile"},
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "ATTACHMENT_BAD_TYPE"
    # 本人下载 200；管理员走管理端端点 200（用户端归属校验对管理员同样 404——权限分离）
    assert client.get(f"/api/attachments/{aid}/download", headers=h).status_code == 200
    assert client.get(f"/api/admin/attachments/{aid}/download", headers=_auth(admin_token)).status_code == 200
    other_email, other_code = _email(client, "plat-other")
    other_token = client.post(
        "/api/auth/login", json={"email": other_email, "code": other_code}
    ).json()["token"]
    r = client.get(f"/api/attachments/{aid}/download", headers=_auth(other_token))
    assert r.status_code == 404
