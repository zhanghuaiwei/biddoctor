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

# 这些路径不做限流：探活与浏览器 CORS 预检
EXEMPT_PATHS = {"/api/healthz", "/docs", "/openapi.json", "/redoc"}
EXEMPT_PREFIXES = ("/api/docs",)


def _client_key(request: Request) -> str:
    """限流维度：优先账号（JWT sub，不校验签名/查库，仅用于分桶），无凭据回退 IP。"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = pyjwt.decode(
                auth.removeprefix("Bearer "),
                options={"verify_signature": False, "verify_exp": False},
            )
            sub = payload.get("sub")
            if sub:
                return f"u:{sub}"
        except Exception:
            pass
    ip = request.client.host if request.client else "unknown"
    return f"ip:{ip}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit_per_min: int = 120):
        super().__init__(app)
        self.limit = max(1, limit_per_min)
        self.window = 60.0
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path in EXEMPT_PATHS or \
                request.url.path.startswith(EXEMPT_PREFIXES):
            return await call_next(request)

        key = _client_key(request)
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            retry_after = int(self.window - (now - hits[0])) + 1
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={"error": {"code": "RATE_LIMITED",
                                   "message": "请求过于频繁，请稍后再试"}},
            )
        hits.append(now)
        return await call_next(request)
