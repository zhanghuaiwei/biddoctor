"""统一业务错误：抛 AppError，由 handler 包装为 {"error": {code, message}}（02 §11）"""


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)
