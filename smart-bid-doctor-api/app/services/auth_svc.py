"""认证业务（02 §9.1）：验证码签发 / 登录。api 层只做参数接收与 token 签发。

事务边界：本模块拥有自己的 commit；登录防爆破节流为进程内内存实现。
"""

import datetime as dt
import hmac
import random

import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import LoginResult, UserStatus, VerificationChannel
from app.core.errors import AppError
from app.core.ratelimit import SlidingWindowLimiter
from app.models import User, VerificationCode
from app.services import config_svc

# 登录验证码暴力破解防护：按 IP 计失败，5 次失败锁 5 分钟（内存实现，多 worker 近似）
_login_throttle = SlidingWindowLimiter(limit=5, window_seconds=300)


def _normalize_email(raw: str) -> str:
    """EmailStr 只规范化域名段；local 段手动 lower，避免 Foo@ 与 foo@ 注册成两个账号。"""
    return raw.strip().lower()


def _send_email(to: str, code: str) -> None:
    # TODO(M1): 接入 Resend/SMTP（01·D8）。骨架版不真实发送，dev 环境直接返回固定码。
    pass


def request_email_code(db: Session, raw_email: str) -> tuple[bool, str | None]:
    """签发验证码。返回 (是否真实发信, dev 环境明文码)。"""
    s = get_settings()
    email = _normalize_email(raw_email)
    now = dt.datetime.now(dt.UTC)

    last = (
        db.query(VerificationCode)
        .filter(
            VerificationCode.channel == VerificationChannel.EMAIL,
            VerificationCode.target == email,
        )
        .order_by(VerificationCode.id.desc())
        .first()
    )
    if last and (now - last.created_at).total_seconds() < 60:
        raise AppError(429, "CODE_TOO_FREQUENT", "发送太频繁，请 60 秒后再试")

    today = (
        db.query(func.count(VerificationCode.id))
        .filter(
            VerificationCode.channel == VerificationChannel.EMAIL,
            VerificationCode.target == email,
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
            channel=VerificationChannel.EMAIL,
            target=email,
            code=code,
            expires_at=now + dt.timedelta(minutes=10),
        )
    )
    db.commit()
    _send_email(email, code)
    return s.env != "dev", code if s.env == "dev" else None


def login(db: Session, raw_email: str, code: str, ip: str,
          user_agent: str | None = None, invite_code: str | None = None) -> User:
    """验证码登录（新邮箱自动注册）。成功返回用户；ip/UA 由 api 层采集。

    每次尝试落 sys_login_log（05 §5.1，独立事务不阻断主流程）；
    邀测管控开关（sys_config signup.require_invite）开启时，新注册必须携带有效邀请码。
    """
    from app.services import log_svc, rbac_svc

    email = _normalize_email(raw_email)
    ua = (user_agent or "")[:256]

    def _log(user_id: int | None, result: str, fail_reason: str | None = None):
        log_svc.write_login_log(
            db, user_id=user_id, email=email, result=result,
            fail_reason=fail_reason, ip=ip, user_agent=ua,
        )

    ok, retry_after = _login_throttle.hit(f"fail:{ip}")
    if not ok:
        _log(None, LoginResult.FAIL, "locked")
        raise AppError(429, "LOGIN_LOCKED", f"失败次数过多，请 {retry_after} 秒后再试")

    now = dt.datetime.now(dt.UTC)
    vc = (
        db.query(VerificationCode)
        .filter(
            VerificationCode.channel == VerificationChannel.EMAIL,
            VerificationCode.target == email,
            VerificationCode.used_at.is_(None),
        )
        .order_by(VerificationCode.id.desc())
        .first()
    )
    # 常量时间比较，避免逐位时序侧信道
    code_ok = vc is not None and hmac.compare_digest(vc.code, code)
    if not code_ok or vc.expires_at < now:
        _log(None, LoginResult.FAIL, "code_invalid")
        raise AppError(401, "CODE_INVALID", "验证码错误或已过期")
    # 原子消费：并发同码请求只有一个能把 used_at 置位（rowcount=0 即已被抢用）
    consumed = db.execute(
        sa.update(VerificationCode)
        .where(VerificationCode.id == vc.id, VerificationCode.used_at.is_(None))
        .values(used_at=now)
    )
    if consumed.rowcount == 0:
        _log(None, LoginResult.FAIL, "code_invalid")
        raise AppError(401, "CODE_INVALID", "验证码已被使用，请重新获取")
    _login_throttle.reset(f"fail:{ip}")  # 成功后清零失败计数

    user = (
        db.query(User)
        .filter(User.email == email, User.deleted_at.is_(None))
        .first()
    )
    if user is None:  # 新邮箱自动注册（02 §9.1）
        # 邀测期注册管控：一次性邀请码原子消费（used_count+rowcount），失败即拒绝
        if config_svc.get_bool(db, "signup.require_invite", False):
            if not invite_code or not rbac_svc.consume_invite_code(db, invite_code):
                db.rollback()
                _log(None, LoginResult.FAIL, "invite_invalid")
                raise AppError(400, "INVITE_CODE_INVALID", "邀请码无效或已用尽")
        user = User(email=email, nickname=email.split("@")[0])
        db.add(user)
        db.flush()
    if user.status == UserStatus.BANNED:  # 封禁用户不发 token（deps 层还会兜底校验）
        db.rollback()
        _log(None, LoginResult.FAIL, "banned")
        raise AppError(403, "ACCOUNT_BANNED", "账号已被禁用，请联系客服")
    user.last_login_at = now
    db.commit()
    _log(user.id, LoginResult.SUCCESS)
    return user
