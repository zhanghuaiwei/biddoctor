
from pydantic import BaseModel, EmailStr, Field


class EmailCodeIn(BaseModel):
    email: EmailStr


class LoginIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=6)


class UserOut(BaseModel):
    id: int
    email: str
    role: str

    model_config = {"from_attributes": True}


class LoginOut(BaseModel):
    token: str
    user: UserOut


class EmailCodeOut(BaseModel):
    sent: bool
    dev_code: str | None = None  # 仅 dev 环境返回，便于联调
