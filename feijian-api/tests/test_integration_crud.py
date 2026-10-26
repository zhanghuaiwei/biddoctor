"""DB 集成测试：登录 → 项目 → 上传 → 订单核销 → 对照发起全链路（非业务 CRUD 主干）"""

import uuid

import pytest

from tests.conftest import TEST_DB_URL, make_minimal_pdf

pytestmark = pytest.mark.skipif(not TEST_DB_URL, reason="需要 FJ_TEST_DATABASE_URL")


@pytest.fixture(scope="module")
def user_token(client):
    email = f"it-{uuid.uuid4().hex[:8]}@test.dev"
    r = client.post("/api/auth/email-code", json={"email": email})
    assert r.status_code == 200
    code = r.json()["dev_code"]  # dev 环境返回固定码
    r = client.post("/api/auth/login", json={"email": email, "code": code})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token(client):
    from app.core.db import SessionLocal
    from app.core.security import create_token
    from app.models import User

    with SessionLocal() as db:
        email = f"it-admin-{uuid.uuid4().hex[:8]}@test.dev"
        user = User(email=email, role="admin")
        db.add(user)
        db.commit()
        return create_token(user.id, "admin")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_full_crud_flow(client, user_token, admin_token):
    h = _auth(user_token)

    # 1. 配额初始状态
    quota = client.get("/api/me/quota", headers=h).json()
    assert quota["free_left"] == 3 and quota["packs"] == []

    # 2. 项目 CRUD（含 02 §9.2 的 ?status= 过滤契约）
    r = client.post("/api/projects", headers=h, json={"name": "集成测试项目"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert client.get("/api/projects", headers=h).json()["total"] == 1
    assert client.get("/api/projects", headers=h, params={"status": "draft"}).json()["total"] == 1
    assert client.get("/api/projects", headers=h, params={"status": "archived"}).json()["total"] == 0

    # 2.1 清单为空表（引擎未接入，返回 0 项 + 分类统计空）
    empty = client.get(f"/api/projects/{pid}/check-items", headers=h).json()
    assert empty["items"] == [] and empty["total"] == 0 and empty["stats"] == {}

    # 3. 上传招标文件（真实最小 PDF）
    pdf = make_minimal_pdf()
    r = client.post(
        f"/api/projects/{pid}/documents", headers=h,
        files={"file": ("tender.pdf", pdf, "application/pdf")}, data={"role": "tender"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["dup"] is False and body["task_id"] is not None
    tender_doc_id = body["document_id"]

    # 3.1 解析状态查询（02 §9.2 GET /documents/{id}/status）
    st = client.get(f"/api/projects/documents/{tender_doc_id}/status", headers=h).json()
    assert st["parse_status"] == "pending" and st["task_id"] == body["task_id"]
    assert st["warnings"] == []

    # 4. 上传同一 PDF 作为投标文件 → sha256 去重 → parse_status=done
    r = client.post(
        f"/api/projects/{pid}/documents", headers=h,
        files={"file": ("bid.pdf", pdf, "application/pdf")}, data={"role": "bid"},
    )
    assert r.json()["dup"] is True

    # 5. 未付款发起对照 → 402
    r = client.post(f"/api/projects/{pid}/compare", headers=h)
    assert r.status_code == 402 and r.json()["error"]["code"] == "QUOTA_EXCEEDED"

    # 6. 下单 → 管理员核销 → 次数到账
    r = client.post("/api/orders", headers=h, json={"sku": "cmp_x5"})
    assert r.status_code == 201, r.text
    order_no = r.json()["order_no"]
    r = client.post(f"/api/admin/orders/{order_no}/grant", headers=_auth(admin_token))
    assert r.status_code == 200, r.text
    packs = client.get("/api/me/quota", headers=h).json()["packs"]
    assert packs and packs[0]["remain"] == 5

    # 7. 模拟 worker 完成解析（集成测试不启动 worker）→ 对照 202
    from app.core.db import SessionLocal
    from app.models import Document

    with SessionLocal() as db:
        doc = db.get(Document, tender_doc_id)
        doc.parse_status = "done"
        db.commit()
    r = client.post(f"/api/projects/{pid}/compare", headers=h)
    assert r.status_code == 202, r.text
    task_id = r.json()["task_id"]
    assert client.get(f"/api/tasks/{task_id}", headers=h).status_code == 200
    assert client.get("/api/me/quota", headers=h).json()["packs"][0]["remain"] == 4

    # 8. 重复核销 → 409
    r = client.post(f"/api/admin/orders/{order_no}/grant", headers=_auth(admin_token))
    assert r.status_code == 409

    # 9. 删除项目 → 列表归零
    assert client.delete(f"/api/projects/{pid}", headers=h).status_code == 204
    assert client.get("/api/projects", headers=h).json()["total"] == 0


def test_cross_user_isolation(client, user_token):
    """越权防护：他人项目/文档/任务一律 404"""
    h = _auth(user_token)
    other_email = f"it-x-{uuid.uuid4().hex[:8]}@test.dev"
    code = client.post("/api/auth/email-code", json={"email": other_email}).json()["dev_code"]
    other_token = client.post(
        "/api/auth/login", json={"email": other_email, "code": code}
    ).json()["token"]
    oh = _auth(other_token)

    pid = client.post("/api/projects", headers=h, json={"name": "A 的项目"}).json()["id"]
    pdf = make_minimal_pdf()
    did = client.post(
        f"/api/projects/{pid}/documents", headers=h,
        files={"file": ("a.pdf", pdf, "application/pdf")}, data={"role": "tender"},
    ).json()["document_id"]

    assert client.get(f"/api/projects/{pid}", headers=oh).status_code == 404
    assert client.get(f"/api/projects/documents/{did}/status", headers=oh).status_code == 404
    assert client.delete(f"/api/projects/{pid}", headers=oh).status_code == 404
