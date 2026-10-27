"""统一业务错误：抛 AppError，由 handler 包装为 {"error": {code, message}}（02 §11）。

错误码注册表：新增码必须先在 ERROR_CODES 登记（code → 约定 HTTP 状态），
tests/test_errors_registry.py 会静态扫描 app/ 下所有 AppError 调用点做守卫——
未登记或状态不一致的码会让测试失败，防止「抛了码没进表」的漂移。
"""

# 业务错误码（AppError 抛出）；status 为约定 HTTP 状态，各抛出点必须一致
ERROR_CODES: dict[str, int] = {
    # 认证
    "UNAUTHORIZED": 401,
    "CODE_INVALID": 401,
    "LOGIN_LOCKED": 429,
    "ACCOUNT_BANNED": 403,
    "CODE_TOO_FREQUENT": 429,
    # 通用（以下三个由 main.py handler / ratelimit 中间件直接产出，不经 AppError）
    "VALIDATION_ERROR": 422,
    "NOT_FOUND": 404,
    "HTTP_ERROR": 0,  # 动态状态，随 HTTPException
    "RATE_LIMITED": 429,
    "FORBIDDEN": 403,
    # 项目 / 文件
    "PROJECT_NOT_FOUND": 404,
    "DOCUMENT_NOT_FOUND": 404,
    "TASK_NOT_FOUND": 404,
    "REPORT_NOT_FOUND": 404,
    "COMPARISON_NOT_FOUND": 404,
    "BAD_ROLE": 400,
    "FILE_TOO_LARGE": 413,
    "FILE_TOO_MANY_PAGES": 413,
    "PARSE_ENCRYPTED": 400,
    "PARSE_CORRUPT": 400,
    # 对照 / 清单
    "DOC_MISSING": 400,
    "DOC_NOT_READY": 400,
    "QUOTA_EXCEEDED": 402,
    "NOT_IMPLEMENTED": 501,
    # 订单
    "BAD_SKU": 400,
    "ORDER_NOT_FOUND": 404,
    "ORDER_STATE": 409,
    "ORDER_NO_CONFLICT": 500,
    # worker（写入 tasks.error_code，不作为 API 响应；status=0 表示不适用）
    "WORKER_TIMEOUT": 0,
    "HANDLER_CRASH": 0,
    "UNKNOWN_TASK_TYPE": 0,
}


class AppError(Exception):
    """业务错误：status=HTTP 状态，code 必须在 ERROR_CODES 注册，message 为用户可读中文。"""

    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)
