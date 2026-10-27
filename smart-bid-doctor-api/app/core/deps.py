import ipaddress

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.enums import UserRole, UserStatus
from app.core.errors import AppError
from app.core.security import decode_token
from app.models import User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if cred is None:
        raise AppError(401, "UNAUTHORIZED", "缺少登录凭证")
    try:
        payload = decode_token(cred.credentials)
    except Exception as exc:
        raise AppError(401, "UNAUTHORIZED", "登录已过期，请重新登录") from exc
    user = db.get(User, int(payload["sub"]))
    if user is None or user.deleted_at is not None or user.status != UserStatus.ACTIVE:
        raise AppError(401, "UNAUTHORIZED", "账号不可用")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise AppError(403, "FORBIDDEN", "需要管理员权限")
    return user


def client_ip(request: Request) -> str:
    """取真实客户端 IP（限流分桶 / 审计 / 登录防爆破共用，口径必须一致）。

    反代（nginx）场景 request.client.host 是代理 IP；仅当对端为内网/回环地址时
    才信任 X-Forwarded-For 最左值——公网客户端无法把源地址伪装成内网 IP。
    生产另在 uvicorn 开 --proxy-headers（compose.prod），两层冗余。
    """
    host = request.client.host if request.client else ""
    if not host:
        return ""
    xff = request.headers.get("X-Forwarded-For", "")
    try:
        behind_trusted_proxy = ipaddress.ip_address(host).is_private
    except ValueError:  # TestClient 等非 IP 对端，按直连处理
        behind_trusted_proxy = False
    if behind_trusted_proxy and xff:
        return xff.split(",")[0].strip()
    return host
