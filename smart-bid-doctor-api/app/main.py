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

    @app_.middleware("http")
    async def admin_oper_log_middleware(request: Request, call_next):
        """管理端请求级操作日志（sys_oper_log，05 §5.1）：仅 /api/admin/*。

        只记 method/path/query/status/cost（不记请求体——防凭据类字段入日志）；
        user_id 从 JWT sub 解析（验签失败按匿名记，不阻断请求）。
        """
        import time as _time

        if not request.url.path.startswith("/api/admin"):
            return await call_next(request)
        started = _time.perf_counter()
        response = await call_next(request)
        try:
            from app.core.db import SessionLocal
            from app.core.security import decode_token

            user_id = None
            auth_header = request.headers.get("Authorization") or ""
            if auth_header.startswith("Bearer "):
                try:
                    user_id = int(decode_token(auth_header[7:])["sub"])
                except Exception:
                    user_id = None
            segments = [seg for seg in request.url.path.split("/") if seg]
            # /api/admin/<域>/<...> → module=admin_<域>，action 取域+末段
            domain = segments[2] if len(segments) > 2 else "root"
            action = f"{domain}:{segments[-1]}" if len(segments) > 3 else domain
            db = SessionLocal()
            try:
                from app.services import log_svc

                log_svc.write_oper_log(
                    db, user_id=user_id, module=f"admin_{domain}"[:32],
                    action=action[:48], method=request.method,
                    path=request.url.path, status_code=response.status_code,
                    cost_ms=int((_time.perf_counter() - started) * 1000),
                    query=str(request.url.query) or None,
                    ip=request.client.host if request.client else None,
                )
            finally:
                db.close()
        except Exception:  # 日志失败不阻断管理请求
            pass
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
