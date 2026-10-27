"""应用配置（单一 Settings 出口，前缀 FJ_，全键清单见根目录 README「配置说明」）。

范式约束：
- SKU 目录/模型名/供应商地址等业务参数一律进配置不进代码（换供应商不改代码）；
- prod 启动 fail-fast 校验强密钥与内部令牌（_prod_guard，04 §5）；
- get_settings lru_cache 单例——测试需要覆写时用 get_settings.cache_clear()
  或直接 Settings(**overrides) 构造注入。
"""

import json
import os
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings

# 文件名映射：settings.env 值域（dev|prod，业务逻辑依赖，见 auth_svc/_prod_guard）
# → dotenv 文件后缀（与前端 Vite 体系同名对齐）；test 仅本地/CI 测试用
_ENV_FILE_BY_ENV = {"dev": "development", "prod": "production", "test": "test"}


def _env_file_stack() -> tuple[str, ...]:
    """dotenv 加载栈（后者优先级高）：.env < .env.{development|production|test} < .env.{...}.local。

    - 环境名取 OS 环境变量 FJ_ENV（缺省 dev）；真实 OS 环境变量始终高于所有文件
      （pydantic-settings 固有语义），与 docker-compose environment 注入方式完全兼容；
    - 容器内无任何 .env 文件时栈中文件静默跳过，生产注入路径不受影响；
    - FJ_ENV 必须在 import app 前可从 OS 环境读到（conftest 已按此约定 setdefault）。
    """
    name = _ENV_FILE_BY_ENV.get(os.environ.get("FJ_ENV", "dev"), "development")
    return (".env", f".env.{name}", f".env.{name}.local")


class Settings(BaseSettings):
    env: str = "dev"  # dev | prod
    database_url: str = "postgresql+psycopg://smart-bid-doctor:smart-bid-doctor@localhost:5432/smart-bid-doctor"
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
    rate_limit_per_min: int = 120  # 每账号+IP 每分钟请求数（02 §9），0=关闭限流
    # LLM Provider（01·D1：智谱单供应商，OpenAI 兼容；模型版本随 lineup 更新，进配置不进代码）
    zhipu_api_key: str = ""  # M1 接入真实调用时必填
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_model_heavy: str = "glm-4.6"  # 重任务：条款抽取/对照判定（02 §7）
    llm_model_light: str = "glm-4.5-flash"  # 轻任务：分类/摘要/兜底重试

    @model_validator(mode="after")
    def _prod_guard(self):
        """prod 启动 fail-fast：防止默认密钥/空内部令牌带上线（04 §5）"""
        prefix = self.model_config.get("env_prefix", "")
        if self.env == "prod":
            if self.jwt_secret == "dev-secret-change-me" or len(self.jwt_secret) < 32:
                raise ValueError(f"prod 环境必须设置强随机 {prefix}JWT_SECRET（≥32 字符）")
            if not self.internal_token:
                raise ValueError(f"prod 环境必须设置 {prefix}INTERNAL_TOKEN")
            if self.cors_origins.strip() == "*":
                raise ValueError("prod 环境不允许 CORS 全放开")
        return self

    @property
    def skus(self) -> dict:
        return json.loads(self.sku_catalog)

    model_config = {"env_prefix": "FJ_", "env_file": _env_file_stack(), "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
