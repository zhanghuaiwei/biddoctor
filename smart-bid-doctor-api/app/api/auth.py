"""认证接口（02 §9.1）：POST /auth/email-code、POST /auth/login。

api 层职责边界：只做参数接收（Pydantic 校验）→ 调 auth_svc → 审计留痕 → 组装响应，
**禁直接 ORM 查询**。IP 一律取 `deps.client_ip`（登录防爆破与审计同口径）；
JWT 签发在 api 层完成（登录成功即发 token，7 天有效期见 core/security.py）。
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import client_ip
from app.core.security import create_token
from app.schemas.auth import EmailCodeIn, EmailCodeOut, LoginIn, LoginOut, UserOut
from app.services import audit_svc, auth_svc

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/email-code", response_model=EmailCodeOut)
def request_code(body: EmailCodeIn, db: Session = Depends(get_db)):
    sent, dev_code = auth_svc.request_email_code(db, body.email)
    return EmailCodeOut(sent=sent, dev_code=dev_code)


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request)
    user = auth_svc.login(db, body.email, body.code, ip=ip)
    audit_svc.log(db, user.id, audit_svc.AuditAction.LOGIN, target="email", ip=ip)
    return LoginOut(token=create_token(user.id, user.role), user=UserOut.model_validate(user))
