"""认证契约（02 §9.1）"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.enums import UserRole


class EmailCodeIn(BaseModel):
    email: EmailStr


class LoginIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=6)
    # 邀测期注册管控开启（sys_config signup.require_invite）时新注册必填
    invite_code: str | None = None


class UserOut(BaseModel):
    id: int
    email: str
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class LoginOut(BaseModel):
    token: str
    user: UserOut


class EmailCodeOut(BaseModel):
    sent: bool
    dev_code: str | None = None  # 仅 dev 环境返回，便于联调
