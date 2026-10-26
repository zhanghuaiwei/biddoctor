import json
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    env: str = "dev"  # dev | prod
    database_url: str = "postgresql+psycopg://feijian:feijian@localhost:5432/feijian"
    jwt_secret: str = "dev-secret-change-me"
    jwt_expire_days: int = 7
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 100
    max_pages: int = 500
    free_projects_per_month: int = 3
    internal_token: str = ""  # 为空则 /internal/* 回退为管理员鉴权
    dev_fixed_code: str = "123456"  # 仅 env=dev 生效
    sku_catalog: str = (
        '{"cmp_x5": {"amount_cny": 99, "title": "对照检查 5 次包"},'
        ' "cmp_x20": {"amount_cny": 199, "title": "对照检查 20 次包"}}'
    )
    cors_origins: str = "http://localhost:5173"

    @model_validator(mode="after")
    def _prod_guard(self):
        """prod 启动 fail-fast：防止默认密钥/空内部令牌带上线（04 §5）"""
        if self.env == "prod":
            if self.jwt_secret == "dev-secret-change-me" or len(self.jwt_secret) < 32:
                raise ValueError("prod 环境必须设置强随机 FJ_JWT_SECRET（≥32 字符）")
            if not self.internal_token:
                raise ValueError("prod 环境必须设置 FJ_INTERNAL_TOKEN")
            if self.cors_origins.strip() == "*":
                raise ValueError("prod 环境不允许 CORS 全放开")
        return self

    @property
    def skus(self) -> dict:
        return json.loads(self.sku_catalog)

    model_config = {"env_prefix": "FJ_", "env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
