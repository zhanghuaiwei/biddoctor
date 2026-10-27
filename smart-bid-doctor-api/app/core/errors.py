"""统一业务错误：抛 AppError，由 handler 包装为 {"error": {code, message}}（02 §11）

======================== 错误码注册表（新增码必须在此登记） ========================
认证
  UNAUTHORIZED          未登录/token 无效           401
  CODE_INVALID          验证码错误或已过期           401
  LOGIN_LOCKED          登录失败次数过多（防爆破）    429
  ACCOUNT_BANNED        账号被禁用                  403
  CODE_TOO_FREQUENT     验证码发送过频               429
通用
  VALIDATION_ERROR      请求参数校验失败             422（main.py handler）
  NOT_FOUND             路由不存在                   404（main.py handler）
  HTTP_ERROR            其他 HTTP 异常               -
  RATE_LIMITED          接口限流                     429（ratelimit 中间件）
  FORBIDDEN             非管理员访问管理端点          403
项目/文件
  PROJECT_NOT_FOUND     项目不存在或越权             404
  DOCUMENT_NOT_FOUND    文件不存在或越权             404
  TASK_NOT_FOUND        任务不存在或越权             404
  REPORT_NOT_FOUND      报告不存在或越权             404
  COMPARISON_NOT_FOUND  无对照记录                   404
  BAD_ROLE              上传 role 非法               400
  FILE_TOO_LARGE        超 100MB                    413
  FILE_TOO_MANY_PAGES   超 500 页                   413
  PARSE_ENCRYPTED       加密 PDF                    400
  PARSE_CORRUPT         损坏/非 PDF                 400
对照/清单
  DOC_MISSING           缺招标或投标文件             400
  DOC_NOT_READY         文档解析未完成               400
  QUOTA_EXCEEDED        次数/免费额度不足            402
  NOT_IMPLEMENTED       业务引擎未接入（骨架桩）      501
订单
  BAD_SKU               不存在的商品                 400
  ORDER_NOT_FOUND       订单不存在                   404
  ORDER_STATE           订单状态不允许核销            409
  ORDER_NO_CONFLICT     订单号重试耗尽               500
worker（任务表 error_code，不抛 API）
  WORKER_TIMEOUT        心跳超时回收失败              -
  HANDLER_CRASH         handler 异常重试耗尽          -
  UNKNOWN_TASK_TYPE     未知任务类型                 -
====================================================================================
"""


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)
