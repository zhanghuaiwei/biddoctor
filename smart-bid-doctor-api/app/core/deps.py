from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
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
    if user is None or user.deleted_at is not None or user.status != "active":
        raise AppError(401, "UNAUTHORIZED", "账号不可用")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise AppError(403, "FORBIDDEN", "需要管理员权限")
    return user


def client_ip(request: Request) -> str:
    return request.client.host if request.client else ""
