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
    "REPORT_FILE_GONE": 410,   # 报告渲染产物已随留存策略清理
    "FINDING_NOT_FOUND": 404,
    # 订单
    "BAD_SKU": 400,
    "ORDER_NOT_FOUND": 404,
    "ORDER_STATE": 409,
    "ORDER_NO_CONFLICT": 500,
    # worker（写入 tasks.error_code，不作为 API 响应；status=0 表示不适用）
    "WORKER_TIMEOUT": 0,
    "HANDLER_CRASH": 0,
    "UNKNOWN_TASK_TYPE": 0,
    # 平台化域（05 文档 v2.0）：系统管理 / 运维 / 附件 / 法务 / AI 治理 / 订阅
    "ORG_NOT_FOUND": 404,
    "ORG_HAS_CHILDREN": 409,     # 机构删除：存在子节点
    "ORG_HAS_USERS": 409,        # 机构删除：仍有在职用户挂靠
    "ORG_STATE": 409,            # 机构已停用等状态冲突
    "ROLE_NOT_FOUND": 404,
    "ROLE_IN_USE": 409,          # 角色删除：仍有用户绑定
    "ROLE_PROTECTED": 409,       # super_admin 内置角色不可删除/停用
    "MENU_NOT_FOUND": 404,
    "MENU_HAS_CHILDREN": 409,
    "USER_NOT_FOUND": 404,
    "USER_STATE": 409,           # 用户禁用/恢复状态冲突（如对 admin 自身操作）
    "CONFIG_NOT_FOUND": 404,
    "CONFIG_VALUE_INVALID": 400, # value_type 反序列化失败
    "DICT_NOT_FOUND": 404,
    "DICT_DATA_CONFLICT": 409,   # 字典取值重复
    "NOTICE_NOT_FOUND": 404,
    "NOTICE_STATE": 409,         # 公告状态机非法流转
    "JOB_NOT_FOUND": 404,
    "JOB_STATE": 409,            # job 已启用/停用冲突
    "ALERT_NOT_FOUND": 404,
    "ALERT_STATE": 409,          # 告警已确认
    "ATTACHMENT_NOT_FOUND": 404,
    "ATTACHMENT_TOO_LARGE": 413, # 附件 ≤20MB（与标书 100MB 上限分开）
    "ATTACHMENT_BAD_TYPE": 400,  # 类型白名单外
    "LEGAL_NOT_FOUND": 404,
    "LEGAL_STATE": 409,          # 法务版本状态机非法流转
    "LEGAL_VERSION_CONFLICT": 409,  # (doc_type, version) 重复
    "AI_MODEL_NOT_FOUND": 404,
    "AI_MODEL_CONFLICT": 409,    # model_code 重复
    "PROMPT_NOT_FOUND": 404,
    "PROMPT_STATE": 409,         # 激活条件不满足（eval_score 为空等）
    "PLAN_NOT_FOUND": 404,
    "PLAN_STATE": 409,
    "SUBSCRIPTION_NOT_FOUND": 404,
    "RULESET_NOT_FOUND": 404,
    "RULESET_STATE": 409,        # 规则库激活条件（同法版本唯一 active）
    "INVITE_CODE_INVALID": 400,  # 邀请码无效/过期/用尽
    "AGREEMENT_REQUIRED": 403,   # 法务新版生效后未签署（写操作拦截）
}


class AppError(Exception):
    """业务错误：status=HTTP 状态，code 必须在 ERROR_CODES 注册，message 为用户可读中文。"""

    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)
