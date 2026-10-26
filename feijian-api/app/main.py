import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import api_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import request_id_var, setup_logging


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="feijian-api", version="0.1.0", docs_url="/api/docs")
    s = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o for o in s.cors_origins.split(",") if o],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request_id_var.set(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        first = (exc.errors() or [{}])[0]
        loc = ".".join(str(x) for x in first.get("loc", []))
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "VALIDATION_ERROR", "message": f"{loc}: {first.get('msg', '')}"}},
        )

    @app.exception_handler(StarletteHTTPException)
    @app.exception_handler(HTTPException)
    async def http_error_handler(_: Request, exc: HTTPException | StarletteHTTPException):
        # 注册 starlette 父类：路由未匹配的 404/405 由 Starlette 抛出，
        # 只挂 fastapi.HTTPException 会漏掉它们，破坏统一错误体契约（02 §11）
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code, "message": str(exc.detail)}},
        )

    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
