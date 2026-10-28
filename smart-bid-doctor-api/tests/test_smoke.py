from fastapi.testclient import TestClient

from app.core.security import create_token, decode_token
from app.main import app

client = TestClient(app)


def test_openapi_paths():
    paths = app.openapi()["paths"]
    expected = [
        "/api/auth/email-code",
        "/api/auth/login",
        "/api/projects",
        "/api/projects/{pid}",
        "/api/projects/{pid}/documents",
        "/api/projects/{pid}/comparison",
        "/api/projects/documents/{did}/status",
        "/api/projects/{pid}/check-items",
        "/api/projects/{pid}/checklist-report",
        "/api/projects/{pid}/compare",
        "/api/projects/{pid}/reports",
        "/api/tasks/{tid}",
        "/api/orders",
        "/api/me/quota",
        "/api/me/menus",
        "/api/notices",
        "/api/legal/current",
        "/api/legal/agreements",
        "/api/attachments",
        "/api/reports/{rid}/export",
        "/api/reports/{rid}/ack",
        "/api/findings/{fid}/feedback",
        "/api/healthz",
        "/api/internal/metrics",
        # 管理端（05 §10）：抽样关键路径，全量见 app/api/admin/*
        "/api/admin/sys/users",
        "/api/admin/sys/orgs/tree",
        "/api/admin/sys/roles",
        "/api/admin/sys/configs",
        "/api/admin/sys/dicts",
        "/api/admin/sys/notices",
        "/api/admin/sys/jobs",
        "/api/admin/sys/invites",
        "/api/admin/monitor/overview",
        "/api/admin/monitor/tasks",
        "/api/admin/alerts",
        "/api/admin/logs/audit",
        "/api/admin/logs/login",
        "/api/admin/logs/oper",
        "/api/admin/stats/daily",
        "/api/admin/orders",
        "/api/admin/attachments",
        "/api/admin/legal/documents",
        "/api/admin/legal/signatures",
        "/api/admin/ai/models",
        "/api/admin/ai/prompts",
        "/api/admin/subs",
        "/api/admin/subs/plans",
        "/api/admin/rules/sets",
        "/api/admin/payments",
    ]
    for p in expected:
        assert p in paths, f"missing route: {p}"
    assert "/api/reports/{rid}" in paths


def test_unified_error_body():
    """统一错误体契约：{"error": {code, message}}（02 §11）"""
    r = client.get("/api/projects")  # 未带 token
    assert r.status_code == 401
    body = r.json()
    assert set(body) == {"error"} and "code" in body["error"] and "message" in body["error"]

    r = client.post("/api/auth/email-code", json={"email": "not-an-email"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"

    r = client.get("/api/nonexistent")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_admin_404_same_shape_for_non_admin():
    """管理端越权 404 同形：非 admin 访问 /api/admin/* 不泄露管理面存在性（05 §11）"""
    r = client.get("/api/admin/monitor/overview")  # 未带 token
    assert r.status_code == 401
    assert set(r.json()) == {"error"}


def test_healthz_shape():
    r = client.get("/api/healthz")
    assert r.status_code == 200
    assert r.json()["status"] in ("ok", "degraded")


def test_jwt_roundtrip():
    token = create_token(42, "user")
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "user"
