"""JWT 签发与验签（01·D8 认证选型）。

安全基线（AGENTS.md 安全行）：
- 算法白名单 HS256——decode 显式传 algorithms，拒绝 alg 混淆攻击；
- secret 来自配置（prod 强制 ≥32 字符，config._prod_guard fail-fast）；
- sub 一律字符串存 user_id，任何取用方必须先验签（限流分桶/鉴权均如此）。
"""

import datetime as dt

import jwt

from app.core.config import get_settings


def create_token(user_id: int, role: str) -> str:
    s = get_settings()
    now = dt.datetime.now(dt.UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + dt.timedelta(days=s.jwt_expire_days),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.jwt_secret, algorithms=["HS256"])
