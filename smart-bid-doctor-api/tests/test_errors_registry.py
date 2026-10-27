"""错误码注册表守卫：AppError 抛出点必须登记在 ERROR_CODES 且状态一致。

注册表（app/core/errors.py）之前只活在 docstring 里，新增码不登记也能抛；
此测试用 AST 静态扫描 app/ 全部源码，把「抛了码没进表 / 状态漂移」变成测试失败。
"""

import ast
import pathlib

from app.core.errors import ERROR_CODES

APP_DIR = pathlib.Path(__file__).resolve().parent.parent / "app"


def _app_error_call_sites() -> list[tuple[pathlib.Path, ast.Call]]:
    """收集 app/ 下所有 AppError(...) 调用节点（排除 errors.py 自身定义）。"""
    sites: list[tuple[pathlib.Path, ast.Call]] = []
    for py in sorted(APP_DIR.rglob("*.py")):
        if py.name == "errors.py":
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name == "AppError":
                sites.append((py, node))
    return sites


def test_registry_covers_core_lifecycle_groups():
    """关键分组必须有码（防止注册表被误删成空表时测试仍通过）。"""
    for code in (
        "UNAUTHORIZED", "CODE_INVALID", "RATE_LIMITED", "PROJECT_NOT_FOUND",
        "PARSE_CORRUPT", "QUOTA_EXCEEDED", "NOT_IMPLEMENTED", "ORDER_STATE",
        "WORKER_TIMEOUT",
    ):
        assert code in ERROR_CODES, f"错误码 {code} 未在注册表登记"


def test_all_apperror_raise_sites_are_registered():
    """app/ 下每个 AppError("CODE", ...) 字面量调用点：码必须已登记且状态一致。"""
    assert _app_error_call_sites(), "未扫描到任何 AppError 调用点，扫描逻辑失效"
    for path, call in _app_error_call_sites():
        args = call.args
        if len(args) < 2 or not isinstance(args[1], ast.Constant):
            continue  # 动态码不在此静态守卫范围
        code = args[1].value
        assert code in ERROR_CODES, f"{path}:{call.lineno} 抛出未登记错误码 {code}"
        registered = ERROR_CODES[code]
        if isinstance(args[0], ast.Constant) and registered:
            assert args[0].value == registered, (
                f"{path}:{call.lineno} {code} 抛出状态 {args[0].value} 与注册表 {registered} 不一致"
            )


def test_worker_error_codes_never_raised_as_http():
    """worker 专用码（status=0）不允许以字面量状态通过 AppError 抛给 API 层。"""
    worker_only = {c for c, s in ERROR_CODES.items() if s == 0}
    for path, call in _app_error_call_sites():
        args = call.args
        if len(args) >= 2 and isinstance(args[1], ast.Constant):
            assert args[1].value not in worker_only, (
                f"{path}:{call.lineno} worker 码 {args[1].value} 不应作为 AppError 抛出"
            )
