"""extract handler（M1/C 编排）：预筛 → GLM 抽取（A 层桩）→ 归一落库 → 任务链。

失败语义（02 §8 / MVP-TASKS §C）：
- LLM 桩（NOT_IMPLEMENTED）/ 熔断期（LLM_CIRCUIT_OPEN）→ 任务 need_review
  （Agent 能力未接入是持久状态，重试无意义；错误码落 tasks.error_code 供前端展示）；
- budget 超限（BUDGET_EXCEEDED）→ 确定性失败 _fail，不走 runner 重试；
- 单批坏输出 → 提高温度 + 轻模型兜底重试 ≤2 次，仍失败丢弃该批；全部批失败
  → need_review 不静默丢弃；
- parse 未完成（need_review/failed/running）→ need_review（文本不可靠不硬抽）。
成功路径：check_items 落库 → project.status=checklist_ready → 入队 embed（对照前置）。
"""

import datetime as dt
import logging

from sqlalchemy.orm import Session

from app.core.enums import EmbeddingStatus, ParseStatus, ProjectStatus, TaskStatus
from app.core.errors import AppError
from app.engine import extractor
from app.llm import zhipu
from app.llm.budget import CODE_BUDGET_EXCEEDED, BudgetExceeded, budget
from app.models import DocBlock, Document, Project, Task
from app.services import ai_svc, rule_svc
from app.worker.handlers.base import stub_done

log = logging.getLogger("worker.extract")

_FORMAT_RETRY = 2  # 单批坏输出重试上限（第 2 次轻模型兜底，02 §3）


def run(task: dict, db: Session) -> None:
    doc = db.get(Document, task["document_id"])
    if doc is None:
        stub_done(db, task["id"], stage="extract:doc-missing")
        return
    project = db.get(Project, doc.project_id)
    if project is None:
        stub_done(db, task["id"], stage="extract:project-missing")
        return

    # 1) 前置：解析必须 done（need_review=扫描占比高文本不可靠，不硬抽）
    if doc.parse_status != ParseStatus.DONE:
        _review(db, task["id"], "DOC_NOT_READY",
                f"招标文件解析状态为 {doc.parse_status}，无法抽取条款")
        return
    project.status = ProjectStatus.TENDER_PARSING
    _touch(db, task["id"], progress=5, stage="extract:prescreen")
    db.commit()

    # 2) C1 规则预筛（内置规则 ∪ 规则库 active hint）
    blocks = (
        db.query(DocBlock)
        .filter(DocBlock.document_id == doc.id)
        .order_by(DocBlock.page.asc(), DocBlock.seq.asc())
        .all()
    )
    rules = rule_svc.active_items(db, project.industry)
    cands, _stats = extractor.prescreen(blocks, rules)
    if not cands:
        _finish(db, project, doc, task, added=0)
        return

    # 3) C2 分批抽取（LLM 调用经 A 层桩，NOT_IMPLEMENTED → need_review）
    provider = zhipu.ZhipuProvider()
    prompt_tpl = ai_svc.active_prompt(db, "extract")
    batches = extractor.build_batches(cands)
    raw_items: list[extractor.ExtractedItem] = []
    failed_batches = 0
    for i, batch in enumerate(batches):
        _touch(db, task["id"],
               progress=10 + int(70 * i / max(len(batches), 1)),
               stage=f"extract:batch_{i + 1}/{len(batches)}")
        db.commit()
        try:
            items = _extract_batch(provider, batch, prompt_tpl, task, project)
        except zhipu.CircuitOpenError as exc:
            _review(db, task["id"], zhipu.CODE_CIRCUIT_OPEN, str(exc))
            return
        except BudgetExceeded as exc:
            _fail(db, task["id"], CODE_BUDGET_EXCEEDED, str(exc))
            return
        except AppError as exc:
            if exc.code == "NOT_IMPLEMENTED":
                _review(db, task["id"], exc.code, exc.message)
                return
            raise  # 未知错误交 runner 退避重试（attempt ≤3）
        if items is None:
            failed_batches += 1  # 重试后仍坏输出：丢弃该批
            continue
        raw_items.extend(items)

    if not raw_items and failed_batches:
        _review(db, task["id"], "EXTRACT_FORMAT",
                f"{failed_batches}/{len(batches)} 批抽取输出均不符合契约，已转人工复核")
        return

    # 4) C3 归一去重落库 + 状态推进 + embed 任务链
    items = extractor.normalize_and_dedup(raw_items)
    added = extractor.save_items(db, project.id, doc.id, items)
    _finish(db, project, doc, task, added=added)


def _extract_batch(provider, batch, prompt_tpl, task, project):
    """单批抽取；坏输出重试 ≤2（末次轻模型兜底）。全部失败返回 None（调用方计失败批）。"""
    user_text = extractor.build_user_prompt(
        batch, prompt_tpl.template if prompt_tpl else None)
    messages = zhipu.default_messages(
        None, user_text)  # 管理端模板走 user 正文；system 用内置默认
    for attempt in range(_FORMAT_RETRY + 1):
        last = attempt == _FORMAT_RETRY
        try:
            res = provider.chat(
                messages, json_mode=True,
                tier="light" if last else "heavy",
                temperature=0.1 + 0.3 * attempt,
                task_id=task["id"], project_id=project.id, purpose="extract",
                prompt_template_id=prompt_tpl.id if prompt_tpl else None,
            )
            return extractor.parse_items(res.content)
        except extractor.ItemFormatError:
            if last:
                log.warning("project=%s 批抽取 %s 次输出均不符契约", project.id, attempt + 1)
                return None
            messages = zhipu.default_messages(None, user_text + "\n\n上一次输出不符合 JSON 契约，请严格只输出 JSON。")
    return None  # pragma: no cover


def _finish(db: Session, project: Project, doc: Document, task: dict, *, added: int) -> None:
    """抽取收尾（含 0 条目场景）：checklist_ready → 入队 embed → 任务 succeeded。"""
    project.status = ProjectStatus.CHECKLIST_READY
    doc.embedding_status = EmbeddingStatus.PENDING
    db.add(Task(type="embed", project_id=project.id, document_id=doc.id))
    db.commit()
    budget.release(task["id"])
    stub_done(db, task["id"], stage=f"extract:done:{added}")


def _review(db: Session, task_id: int, code: str, msg: str) -> None:
    """持久性失败 → need_review（LLM 桩/熔断/解析未就绪/全批坏输出）。"""
    t = db.get(Task, task_id)
    if t is None:
        return
    t.status = TaskStatus.NEED_REVIEW
    t.error_code = code
    t.error_msg = msg[:500]
    t.finished_at = dt.datetime.now(dt.UTC)
    db.commit()
    budget.release(task_id)


def _fail(db: Session, task_id: int, code: str, msg: str) -> None:
    """确定性失败（budget 超限）→ failed，不走 runner 重试。"""
    t = db.get(Task, task_id)
    if t is None:
        return
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
