"""管理端 API 聚合（05 §10 /api/admin/*）：role + RBAC 双校验（deps.require_perm）。

权限点与 sys_menu.button 对应（admin:<域>:<动作>）；越权一律 404 同形响应。
"""

from fastapi import APIRouter

from app.api.admin import biz, logs, monitor, ops, stats, sys_

router = APIRouter(prefix="/admin")
router.include_router(sys_.router)
router.include_router(ops.router)
router.include_router(monitor.router)
router.include_router(logs.router)
router.include_router(stats.router)
router.include_router(biz.router)

admin_router = router
