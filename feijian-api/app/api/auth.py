import datetime as dt
import random

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import client_ip
from app.core.errors import AppError
from app.core.security import create_token
from app.models import User, VerificationCode
from app.schemas.auth import EmailCodeIn, EmailCodeOut, LoginIn, LoginOut, UserOut
from app.services import audit_svc

router = APIRouter(prefix="/auth", tags=["auth"])


def _send_email(to: str, code: str) -> None:
    # TODO(M1): 接入 Resend/SMTP（01·D8）。骨架版不真实发送，dev 环境直接返回固定码。
    pass


@router.post("/email-code", response_model=EmailCodeOut)
def request_code(body: EmailCodeIn, db: Session = Depends(get_db)):
    s = get_settings()
    now = dt.datetime.now(dt.UTC)

    last = (
        db.query(VerificationCode)
        .filter(VerificationCode.channel == "email", VerificationCode.target == body.email)
        .order_by(VerificationCode.id.desc())
        .first()
    )
    if last and (now - last.created_at).total_seconds() < 60:
        raise AppError(429, "CODE_TOO_FREQUENT", "发送太频繁，请 60 秒后再试")

    today = (
        db.query(func.count(VerificationCode.id))
        .filter(
            VerificationCode.channel == "email",
            VerificationCode.target == body.email,
            VerificationCode.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0),
        )
        .scalar()
        or 0
    )
    if today >= 10:
        raise AppError(429, "CODE_TOO_FREQUENT", "今日验证码发送次数已达上限")

    code = s.dev_fixed_code if s.env == "dev" else f"{random.randint(0, 999999):06d}"
    db.add(
        VerificationCode(
            channel="email",
            target=body.email,
            code=code,
            expires_at=now + dt.timedelta(minutes=10),
        )
    )
    db.commit()
    _send_email(body.email, code)
    return EmailCodeOut(sent=s.env != "dev", dev_code=code if s.env == "dev" else None)


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    now = dt.datetime.now(dt.UTC)
    vc = (
        db.query(VerificationCode)
        .filter(
            VerificationCode.channel == "email",
            VerificationCode.target == body.email,
            VerificationCode.code == body.code,
            VerificationCode.used_at.is_(None),
        )
        .order_by(VerificationCode.id.desc())
        .first()
    )
    if vc is None or vc.expires_at < now:
        raise AppError(401, "CODE_INVALID", "验证码错误或已过期")
    vc.used_at = now

    user = (
        db.query(User)
        .filter(User.email == body.email, User.deleted_at.is_(None))
        .first()
    )
    if user is None:  # 新邮箱自动注册（02 §9.1）
        user = User(email=body.email, nickname=body.email.split("@")[0])
        db.add(user)
        db.flush()
    if user.status == "banned":  # 封禁用户不发 token（deps 层还会兜底校验）
        db.rollback()
        raise AppError(403, "ACCOUNT_BANNED", "账号已被禁用，请联系客服")
    user.last_login_at = now
    db.commit()

    audit_svc.log(db, user.id, "login", target="email", ip=client_ip(request))
    return LoginOut(token=create_token(user.id, user.role), user=UserOut.model_validate(user))
