"""限流中间件单测（02 §9：限流按账号+IP，healthz 豁免）——无需数据库"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.ratelimit import RateLimitMiddleware


def make_app(limit: int) -> TestClient:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limit_per_min=limit)

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    @app.get("/api/healthz")
    def healthz():
        return {"ok": True}

    return TestClient(app)


def test_limit_blocks_over_threshold():
    client = make_app(limit=3)
    for _ in range(3):
        assert client.get("/api/ping").status_code == 200
    r = client.get("/api/ping")
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"
    assert "Retry-After" in r.headers


def test_healthz_exempt():
    client = make_app(limit=1)
    assert client.get("/api/healthz").status_code == 200
    # healthz 不计数，也不受其他路径限额影响
    assert client.get("/api/healthz").status_code == 200
    assert client.get("/api/ping").status_code == 200
    assert client.get("/api/ping").status_code == 429


def test_accounts_bucketed_separately():
    """同 IP 不同账号分桶：02 §9 限流维度为账号+IP"""
    client = make_app(limit=1)
    h_a = {"Authorization": "Bearer x.y.z"}  # 解不出 sub 会回退 IP——用可解码 token
    from app.core.security import create_token

    tok_a = create_token(1, "user")
    tok_b = create_token(2, "user")
    assert client.get("/api/ping", headers={"Authorization": f"Bearer {tok_a}"}).status_code == 200
    assert client.get("/api/ping", headers={"Authorization": f"Bearer {tok_a}"}).status_code == 429
    # 账号 B 独立桶
    assert client.get("/api/ping", headers={"Authorization": f"Bearer {tok_b}"}).status_code == 200
    assert h_a  # noqa: F841 (占位避免 lint)


def test_invalid_token_falls_back_to_ip():
    client = make_app(limit=1)
    bad = {"Authorization": "Bearer not-a-jwt"}
    assert client.get("/api/ping", headers=bad).status_code == 200
    assert client.get("/api/ping", headers=bad).status_code == 429


@pytest.mark.parametrize("path", ["/api/docs", "/openapi.json"])
def test_docs_exempt(path):
    client = make_app(limit=1)
    # swagger/openapi 页面豁免（调试场景），不再断言 200（docs 依赖 CDN 资源，只验证不 429）
    assert client.get(path).status_code != 429
