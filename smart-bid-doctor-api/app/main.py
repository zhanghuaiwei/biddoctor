import re
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api import api_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import request_id_var, setup_logging

# 客户端自带 request_id 只保留安全字符并截断（会进日志与审计 detail，防注入/超长）
_REQUEST_ID_BAD_CHARS = re.compile(r"[^A-Za-z0-9_-]")


def create_app() -> FastAPI:
    setup_logging()
    app_ = FastAPI(title="smart-bid-doctor-api", version=__version__, docs_url="/api/docs")
    s = get_settings()
    # add_middleware 后加的在外层。期望请求流：
    # request_id → security_headers → CORS → RateLimit → route
    # （限流在 CORS 内层，保证 429 响应也带 CORS 头）
    if s.rate_limit_per_min > 0:  # 02 §9：限流按账号+IP（healthz 豁免）
        from app.core.ratelimit import RateLimitMiddleware

        app_.add_middleware(RateLimitMiddleware, limit_per_min=s.rate_limit_per_min)
    app_.add_middleware(
        CORSMiddleware,
        allow_origins=[o for o in s.cors_origins.split(",") if o],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app_.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        # 基础安全头（04 §5）；CSP/HTTPS 由生产 nginx 层负责（deploy/nginx.conf）
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    @app_.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid_raw = _REQUEST_ID_BAD_CHARS.sub("", request.headers.get("X-Request-ID") or "")
        rid = rid_raw[:64] or uuid.uuid4().hex[:12]
        request_id_var.set(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    @app_.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app_.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        first = (exc.errors() or [{}])[0]
        loc = ".".join(str(x) for x in first.get("loc", []))
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "VALIDATION_ERROR", "message": f"{loc}: {first.get('msg', '')}"}},
        )

    @app_.exception_handler(StarletteHTTPException)
    @app_.exception_handler(HTTPException)
    async def http_error_handler(_: Request, exc: HTTPException | StarletteHTTPException):
        # 注册 starlette 父类：路由未匹配的 404/405 由 Starlette 抛出，
        # 只挂 fastapi.HTTPException 会漏掉它们，破坏统一错误体契约（02 §11）
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code, "message": str(exc.detail)}},
        )

    app_.include_router(api_router, prefix="/api")
    return app_


app = create_app()
