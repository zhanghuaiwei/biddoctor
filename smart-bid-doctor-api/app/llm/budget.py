"""token 预算控制（02 §7 budget.py）：任务级上限防成本跑飞。

单 worker 进程基线：按 task_id 在进程内累计 prompt+output token，超限抛
BudgetExceeded——handler 捕获后写 tasks.error_code=CODE_BUDGET_EXCEEDED（确定性
失败不重试）。预算码为 worker 域（ERROR_CODES 注册 status=0），不经 AppError 抛给
API 层（tests/test_errors_registry.py AST 守卫）。
任务终态时 handler 须调 release() 清理，防长期运行内存缓慢增长。

进程内状态与限流器同约定：测试用模块级 reset() 清理（autouse fixture）。
多副本部署时预算为「每副本」口径（演进信号：跨副本预算需进 DB 计数，暂不预建）。
"""

CHECKLIST_BUDGET_TOKENS = 600_000
COMPARE_BUDGET_TOKENS = 1_500_000

# worker 域错误码（errors.py 注册表 status=0；handler 写 tasks.error_code 用常量）
CODE_BUDGET_EXCEEDED = "BUDGET_EXCEEDED"

# purpose → 预算映射（02 §7）：抽取链走清单预算，判定链走对照预算
_PURPOSE_BUDGET = {
    "extract": CHECKLIST_BUDGET_TOKENS,
    "retry": CHECKLIST_BUDGET_TOKENS,
    "judge": COMPARE_BUDGET_TOKENS,
    "summary": COMPARE_BUDGET_TOKENS,
}


def budget_for(purpose: str) -> int:
    """purpose 对应的任务级 token 预算；未登记 purpose（embed 等）不计预算（返回 0）。"""
    return _PURPOSE_BUDGET.get(purpose, 0)


class BudgetExceeded(Exception):
    """预算超限：handler 捕获后置任务 failed（确定性失败，不重试）。"""

    def __init__(self, used: int, budget_limit: int):
        self.used = used
        self.budget_limit = budget_limit
        super().__init__(
            f"LLM token 预算超限：已用 {used} / 上限 {budget_limit}，任务终止以控成本"
        )


class BudgetTracker:
    """进程内任务级 token 账本。"""

    def __init__(self) -> None:
        self._used: dict[int, int] = {}

    def used(self, task_id: int) -> int:
        return self._used.get(task_id, 0)

    def check(self, task_id: int, budget_limit: int) -> None:
        """发起调用前检查：预算已耗尽（含等于）即快速失败，不再发起真实调用。"""
        if budget_limit > 0 and self.used(task_id) >= budget_limit:
            raise BudgetExceeded(self.used(task_id), budget_limit)

    def add(self, task_id: int, tokens: int, budget_limit: int) -> int:
        """调用返回后累计实际用量；越过上限抛 BudgetExceeded（本次调用已发生，不退回）。"""
        if budget_limit <= 0:
            return self.used(task_id)
        used = self.used(task_id) + max(tokens, 0)
        self._used[task_id] = used
        if used > budget_limit:
            raise BudgetExceeded(used, budget_limit)
        return used

    def release(self, task_id: int) -> None:
        """任务终态清理（succeeded/failed/need_review 均应调用）。"""
        self._used.pop(task_id, None)

    def reset(self) -> None:
        self._used.clear()


budget = BudgetTracker()
