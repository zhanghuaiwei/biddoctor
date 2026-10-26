"""认证安全集成测试：登录节流（暴力破解防护）+ 限流分桶验签——需要 FJ_TEST_DATABASE_URL"""

import uuid

import pytest

from tests.conftest import TEST_DB_URL

pytestmark = pytest.mark.skipif(not TEST_DB_URL, reason="需要 FJ_TEST_DATABASE_URL")


@pytest.fixture(autouse=True)
def _clean_throttle():
    """登录节流为模块级内存状态，测试间必须清零避免相互污染"""
    from app.api.auth import _login_throttle

    _login_throttle._hits.clear()
    yield
    _login_throttle._hits.clear()


def _email(client, local: str) -> tuple[str, str]:
    """注册邮箱并返回 (email, 正确验证码)"""
    email = f"{local}@fjtest.dev"
    code = client.post("/api/auth/email-code", json={"email": email}).json()["dev_code"]
    return email, code


def test_login_bruteforce_locked(client):

    email, code = _email(client, "bf-lock")
    # 5 次错误验证码
    for _ in range(5):
        r = client.post("/api/auth/login", json={"email": email, "code": "000000"})
        assert r.status_code == 401
    # 第 6 次即使验证码正确也被锁（429）
    r = client.post("/api/auth/login", json={"email": email, "code": code})
    assert r.status_code == 429 and r.json()["error"]["code"] == "LOGIN_LOCKED"


def test_login_success_resets_throttle(client):
    email, code = _email(client, "bf-reset")
    for _ in range(4):
        client.post("/api/auth/login", json={"email": email, "code": "000000"})
    # 成功登录清零
    assert client.post("/api/auth/login", json={"email": email, "code": code}).status_code == 200
    # 计数已清零：再来 4 次失败仍是 401 而非 429
    for _ in range(4):
        r = client.post("/api/auth/login", json={"email": email, "code": "000000"})
        assert r.status_code == 401


def test_ratelimit_forged_token_falls_back_to_ip_bucket(client):
    """伪造 JWT 拿不到账号桶，必须落入 IP 桶（防限流绕过）"""
    from fastapi import Request

    from app.core.ratelimit import _account_id

    forged = "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI5OTk5In0.FORGED"
    # 直接验证 _account_id 对伪造 token 返回 None
    scope = {
        "type": "http", "method": "GET", "path": "/",
        "headers": [(b"authorization", forged.encode())],
        "client": ("1.2.3.4", 80),
    }

    class _StubReceive:
        async def __call__(self):
            return {"type": "http.disconnect"}

    req = Request(scope, _StubReceive())
    assert _account_id(req) is None


def test_email_normalized_case_insensitive(client):
    """email local 段归一：大写输入落库为小写，且与后续小写请求命中同一 target（冷却证明）"""
    from app.core.db import SessionLocal
    from app.models import User

    upper = f"Case.Test-{uuid.uuid4().hex[:6]}@FJTEST.DEV"
    code = client.post("/api/auth/email-code", json={"email": upper}).json()["dev_code"]
    r = client.post("/api/auth/login", json={"email": upper, "code": code})
    assert r.status_code == 200

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == upper.lower()).first()
        assert user is not None  # 落库即小写，大写变体不产生第二个账号
        assert db.query(User).filter(User.email == upper).first() is None

    # 小写变体再发码 → 命中同一 target 的 60s 冷却（归一化生效的直接证据）
    r2 = client.post("/api/auth/email-code", json={"email": upper.lower()})
    assert r2.status_code == 429 and r2.json()["error"]["code"] == "CODE_TOO_FREQUENT"


def test_audit_detail_carries_request_id(client):
    """全生命周期留痕：审计 detail 自动关联 request_id（响应头 ↔ audit_logs 互查）"""
    import uuid

    from app.core.db import SessionLocal
    from app.models import AuditLog

    email = f"rid-{uuid.uuid4().hex[:8]}@fjtest.dev"
    code = client.post("/api/auth/email-code", json={"email": email}).json()["dev_code"]
    r = client.post("/api/auth/login", json={"email": email, "code": code})
    rid = r.headers.get("X-Request-ID")
    assert rid

    with SessionLocal() as db:
        log = (
            db.query(AuditLog)
            .filter(AuditLog.action == "login", AuditLog.user_id.is_not(None))
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert log is not None
        assert log.detail.get("request_id") == rid
