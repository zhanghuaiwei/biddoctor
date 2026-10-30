"""compare handler（M2/E 编排）：逐条混合检索 → GLM 判定（A 层桩）→ 规则复核
→ findings/stats 落库 → 对照报告闭环。

失败语义（02 §8 / MVP-TASKS §E）：配额在对照发起时已扣（compare_svc.start_compare），
comparison 级失败不回滚次数——LLM 桩（NOT_IMPLEMENTED）/熔断/全量判定失败 →
comparison 置 need_review 人工处理（次数已消耗的语义，02 §9.4）。
成功路径：findings + stats（红黄绿）→ status=done → 内联渲染对照报告
（check_svc.generate_comparison_report，同 handler 同步步骤，非旁路异步）。
"""

import datetime as dt
import logging

from sqlalchemy.orm import Session

from app.core.enums import ComparisonStatus, ProjectStatus, TaskStatus
from app.core.errors import AppError
from app.engine import comparator
from app.llm import zhipu
from app.llm.budget import CODE_BUDGET_EXCEEDED, BudgetExceeded, budget
from app.models import CheckItem, Comparison, Project, Task
from app.services import ai_svc, audit_svc, check_svc, rule_svc
from app.worker.handlers.base import stub_done

log = logging.getLogger("worker.compare")

A = audit_svc.AuditAction


def run(task: dict, db: Session) -> None:
    cmp_ = db.get(Comparison, task["comparison_id"])
    if cmp_ is None:
        stub_done(db, task["id"], stage="compare:missing")
        return
    if cmp_.status not in (ComparisonStatus.PENDING, ComparisonStatus.NEED_REVIEW):
        # 已终态/在跑：幂等跳过（重试到达时防重复扣写）
        stub_done(db, task["id"], stage=f"compare:skip:{cmp_.status}")
        return
    project = db.get(Project, cmp_.project_id)
    if project is None:
        stub_done(db, task["id"], stage="compare:project-missing")
        return

    cmp_.status = ComparisonStatus.RUNNING
    _touch(db, task["id"], progress=5, stage="compare:open")
    db.commit()

    items = (
        db.query(CheckItem)
        .filter(CheckItem.project_id == project.id)
        .order_by(CheckItem.id.asc())
        .all()
    )
    if not items:
        # 抽取为空 → 对照无意义；次数不回滚（已消耗，02 §9.4），人工处理
        _review(db, cmp_, task["id"], "CHECKLIST_EMPTY", "项目无检查条款（抽取为空），无法对照")
        return

    provider = zhipu.ZhipuProvider()
    prompt_tpl = ai_svc.active_prompt(db, "judge")
    rules = rule_svc.active_items(db, project.industry)
    results: list[comparator.JudgeResult] = []

    for idx, item in enumerate(items):
        _touch(db, task["id"],
               progress=10 + int(75 * idx / len(items)),
               stage=f"compare:item_{idx + 1}/{len(items)}")
        db.commit()
        # query 向量化（桩 → None → 检索降级 trgm-only，工程可运行）
        qvec = _query_vector(provider, item.raw_text, task, project)
        if qvec is _BUDGET_FAIL:
            _fail(db, cmp_, task["id"], CODE_BUDGET_EXCEEDED, "LLM token 预算超限")
            return
        hits = comparator.hybrid_search(db, cmp_.bid_doc_id, item.raw_text, qvec)
        try:
            res = provider.chat(
                comparator.build_judge_messages(item, hits,
                                                prompt_tpl.template if prompt_tpl else None),
                json_mode=True, tier="heavy",
                task_id=task["id"], project_id=project.id, purpose="judge",
                prompt_template_id=prompt_tpl.id if prompt_tpl else None,
            )
        except zhipu.CircuitOpenError as exc:
            _review(db, cmp_, task["id"], zhipu.CODE_CIRCUIT_OPEN, str(exc))
            return
        except BudgetExceeded as exc:
            _fail(db, cmp_, task["id"], CODE_BUDGET_EXCEEDED, str(exc))
            return
        except AppError as exc:
            if exc.code == "NOT_IMPLEMENTED":
                _review(db, cmp_, task["id"], exc.code, exc.message)
                return
            raise  # 未知错误交 runner 退避重试
        parsed = comparator.parse_verdict(res.content)
        parsed = comparator.rule_review(item, parsed, rules)
        results.append(comparator.JudgeResult(
            check_item_id=item.id, verdict=parsed["verdict"],
            level=comparator.level_for(parsed["verdict"]), reason=parsed["reason"],
            bid_ref_page=parsed["bid_ref_page"], bid_quote=parsed["bid_quote"],
            confidence=parsed["confidence"], rule_overridden=parsed["rule_overridden"],
        ))

    # findings + stats 落库 → done → 对照报告闭环（阅后即焚仅清单链，对照原件保留）
    comparator.save_findings(db, cmp_.id, results)
    cmp_.stats = comparator.compute_stats(results)
    cmp_.status = ComparisonStatus.DONE
    cmp_.finished_at = dt.datetime.now(dt.UTC)
    rep = check_svc.generate_comparison_report(db, cmp_)
    project.status = ProjectStatus.REPORT_READY
    db.commit()
    audit_svc.log(
        db, None, A.REPORT_GENERATED, target=f"report:{rep.id}",
        detail={"project_id": project.id, "kind": "comparison",
                "comparison_id": cmp_.id,
                "stats": cmp_.stats.get("by_level")},
    )
    budget.release(task["id"])
    stub_done(db, task["id"], stage=f"compare:done:{rep.id}")


_BUDGET_FAIL = object()  # _query_vector 内部预算超限的哨兵（外层统一 _fail）


def _query_vector(provider, query_text: str, task: dict, project: Project):
    """检索 query 向量化；桩/熔断 → None（降级 trgm-only）；预算超限 → 哨兵。"""
    try:
        return provider.embed([query_text], task_id=task["id"],
                              project_id=project.id)[0]
    except zhipu.CircuitOpenError:
        return None  # 熔断降级：judge chat 随后亦会熔断转 need_review
    except AppError as exc:
        if exc.code == "NOT_IMPLEMENTED":
            return None
        if exc.code == CODE_BUDGET_EXCEEDED:
            return _BUDGET_FAIL
        raise
    except BudgetExceeded:
        return _BUDGET_FAIL


def _review(db: Session, cmp_: Comparison, task_id: int, code: str, msg: str) -> None:
    cmp_.status = ComparisonStatus.NEED_REVIEW
    db.commit()
    t = db.get(Task, task_id)
    if t is not None:
        t.status = TaskStatus.NEED_REVIEW
        t.error_code = code
        t.error_msg = msg[:500]
        t.finished_at = dt.datetime.now(dt.UTC)
        db.commit()
    budget.release(task_id)


def _fail(db: Session, cmp_: Comparison, task_id: int, code: str, msg: str) -> None:
    cmp_.status = ComparisonStatus.NEED_REVIEW  # 次数已消耗：failed 语义并入 need_review（02 §9.4）
    db.commit()
    t = db.get(Task, task_id)
    if t is not None:
        t.status = TaskStatus.FAILED
        t.error_code = code
        t.error_msg = msg[:500]
        t.finished_at = dt.datetime.now(dt.UTC)
        db.commit()
    budget.release(task_id)


def _touch(db: Session, task_id: int, *, progress: int, stage: str) -> None:
    t = db.get(Task, task_id)
    if t is not None:
        t.progress = max(t.progress or 0, progress)
        t.stage = stage
        t.heartbeat_at = dt.datetime.now(dt.UTC)
