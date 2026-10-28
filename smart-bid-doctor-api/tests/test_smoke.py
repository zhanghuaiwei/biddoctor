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
        "/api/projects/{pid}/compare",
        "/api/tasks/{tid}",
        "/api/orders",
        "/api/me/quota",
        "/api/admin/orders/{order_no}/grant",
        "/api/healthz",
        "/api/internal/metrics",
    ]
    for p in expected:
        assert p in paths, f"missing route: {p}"
    # 01 §6 接口总览：报告导出端点必须存在（业务未接入，501 占位）
    assert "/api/reports/{rid}/export" in paths
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


def test_business_stub_is_501_documented():
    """业务端点必须显式 501 且在 OpenAPI 中声明，不许半实现"""
    spec = app.openapi()
    op = spec["paths"]["/api/projects/{pid}/checklist-report"]["post"]
    assert "501" in op.get("responses", {})
    op_export = spec["paths"]["/api/reports/{rid}/export"]["get"]
    assert "501" in op_export.get("responses", {})


def test_healthz_shape():
    r = client.get("/api/healthz")
    assert r.status_code == 200
    assert r.json()["status"] in ("ok", "degraded")


def test_jwt_roundtrip():
    token = create_token(42, "user")
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "user"
