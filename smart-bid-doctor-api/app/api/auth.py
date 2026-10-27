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
