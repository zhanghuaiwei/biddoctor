"""接口限流（02 §9：限流按账号+IP，GET /healthz 除外）。

单机内存滑动窗口实现（设计基线：单机部署、不引入 Redis）。
说明：uvicorn 多 worker 时各进程独立计数，限流为近似值——
MVP 规模（日检查 100 次）足够；量大后切 Redis 集中计数。
"""

import time
from collections import defaultdict, deque

import jwt as pyjwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# 这些路径不做限流：探活与调试文档
EXEMPT_PATHS = {"/api/healthz", "/docs", "/openapi.json", "/redoc"}
EXEMPT_PREFIXES = ("/api/docs",)


class SlidingWindowLimiter:
    """内存滑动窗口计数器（中间件与登录节流共用）。"""

    def __init__(self, limit: int, window_seconds: float = 60.0):
        self.limit = max(1, limit)
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str) -> tuple[bool, int]:
        """记录一次并返回 (是否放行, 建议重试秒数)。"""
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False, int(self.window - (now - hits[0])) + 1
        hits.append(now)
        return True, 0

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)


def _account_id(request: Request) -> str | None:
    """验签取 JWT sub 作为账号分桶键；无效/伪造 token 一律回退 IP 分桶。"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    from app.core.config import get_settings

    try:
        payload = pyjwt.decode(
            auth.removeprefix("Bearer "),
            get_settings().jwt_secret,
            algorithms=["HS256"],  # 必须验签：unverified sub 可被伪造刷桶绕过限流
        )
    except Exception:
        return None
    sub = payload.get("sub")
    return f"u:{sub}" if sub else None


def _client_key(request: Request) -> str:
    """分桶键：优先验签后的账号；否则用真实客户端 IP（与 deps.client_ip 同口径）。
    局部导入避免循环依赖（deps → models）。"""
    account = _account_id(request)
    if account:
        return account
    from app.core.deps import client_ip

    return f"ip:{client_ip(request) or 'unknown'}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit_per_min: int = 120):
        super().__init__(app)
        self.limiter = SlidingWindowLimiter(limit_per_min, 60.0)

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path in EXEMPT_PATHS or \
                request.url.path.startswith(EXEMPT_PREFIXES):
            return await call_next(request)

        ok, retry_after = self.limiter.hit(_client_key(request))
        if not ok:
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={"error": {"code": "RATE_LIMITED",
                                   "message": "请求过于频繁，请稍后再试"}},
            )
        return await call_next(request)
