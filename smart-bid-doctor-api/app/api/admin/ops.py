"""运维管理端点（05 §3 / §10）：参数配置 / 字典 / 公告 / 定时任务。

权限点：admin:sys:config（参数+字典）| admin:sys:notice | admin:sys:job。
配置改值、公告发布/下线、任务启停/手动触发均写审计（05 §5.2）。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_perm
from app.models import User
from app.schemas.platform import (
    ConfigOut,
    ConfigUpdateIn,
    DictDataIn,
    DictDataOut,
    DictDataUpdate,
    DictTypeIn,
    DictTypeOut,
    JobLogPage,
    JobOut,
    NoticeIn,
    NoticeOut,
    NoticePage,
    OkOut,
)
from app.services import audit_svc, config_svc, dict_svc, job_svc, notice_svc

router = APIRouter(tags=["admin-ops"])

A = audit_svc.AuditAction


# ── 参数配置 ─────────────────────────────────────────────────────────────────


@router.get("/sys/configs", response_model=list[ConfigOut])
def list_configs(_: User = Depends(require_perm("admin:sys:config")), db: Session = Depends(get_db)):
    return config_svc.list_all(db)


@router.put("/sys/configs/{key}", response_model=ConfigOut)
def update_config(
    key: str, body: ConfigUpdateIn,
    admin: User = Depends(require_perm("admin:sys:config")),
    db: Session = Depends(get_db),
):
    row = config_svc.update(db, key=key, value=body.value, admin_id=admin.id)
    audit_svc.log(db, admin.id, A.SYS_CONFIG_UPDATE, target=f"config:{key}",
                  detail={"old": row.value, "new": body.value})
    return row


# ── 字典 ─────────────────────────────────────────────────────────────────────


@router.get("/sys/dicts", response_model=list[DictTypeOut])
def list_dict_types(_: User = Depends(require_perm("admin:sys:config")), db: Session = Depends(get_db)):
    return dict_svc.list_types(db)


@router.post("/sys/dicts", response_model=DictTypeOut, status_code=201)
def create_dict_type(
    body: DictTypeIn,
    admin: User = Depends(require_perm("admin:sys:config")),
    db: Session = Depends(get_db),
):
    row = dict_svc.create_type(db, dict_type=body.dict_type, name=body.name, remark=body.remark)
    audit_svc.log(db, admin.id, A.SYS_DICT_UPDATE, target=f"dict:{row.dict_type}",
                  detail={"op": "create_type"})
    return row


@router.get("/sys/dicts/{dict_type}/data", response_model=list[DictDataOut])
def list_dict_data(
    dict_type: str,
    _: User = Depends(require_perm("admin:sys:config")),
    db: Session = Depends(get_db),
):
    return dict_svc.list_data(db, dict_type)


@router.post("/sys/dicts/{dict_type}/data", response_model=DictDataOut, status_code=201)
def create_dict_data(
    dict_type: str, body: DictDataIn,
    admin: User = Depends(require_perm("admin:sys:config")),
    db: Session = Depends(get_db),
):
    row = dict_svc.create_data(
        db, dict_type=dict_type, value=body.value, label=body.label,
        sort=body.sort, extra=body.extra,
    )
    audit_svc.log(db, admin.id, A.SYS_DICT_UPDATE, target=f"dict:{dict_type}",
                  detail={"op": "create_data", "value": body.value})
    return row


@router.patch("/sys/dicts/data/{data_id}", response_model=DictDataOut)
def update_dict_data(
    data_id: int, body: DictDataUpdate,
    admin: User = Depends(require_perm("admin:sys:config")),
    db: Session = Depends(get_db),
):
    row = dict_svc.update_data(
        db, data_id, label=body.label, sort=body.sort, extra=body.extra, status=body.status,
    )
    audit_svc.log(db, admin.id, A.SYS_DICT_UPDATE, target=f"dict:{row.dict_type}",
                  detail={"op": "update_data", "id": data_id})
    return row


@router.delete("/sys/dicts/data/{data_id}", response_model=OkOut)
def delete_dict_data(
    data_id: int,
    admin: User = Depends(require_perm("admin:sys:config")),
    db: Session = Depends(get_db),
):
    dict_svc.delete_data(db, data_id)
    audit_svc.log(db, admin.id, A.SYS_DICT_UPDATE, target=f"dict:data:{data_id}",
                  detail={"op": "delete_data"})
    return OkOut()


# ── 公告 ─────────────────────────────────────────────────────────────────────


@router.get("/sys/notices", response_model=NoticePage)
def admin_notices(
    status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_perm("admin:sys:notice")),
    db: Session = Depends(get_db),
):
    rows, total = notice_svc.list_all(db, status=status, limit=limit, offset=offset)
    return NoticePage(items=[NoticeOut.model_validate(n) for n in rows], total=total)


@router.post("/sys/notices", response_model=NoticeOut, status_code=201)
def create_notice(
    body: NoticeIn,
    admin: User = Depends(require_perm("admin:sys:notice")),
    db: Session = Depends(get_db),
):
    row = notice_svc.create(
        db, title=body.title, content=body.content, type_=body.type,
        level=body.level, publish_at=body.publish_at, admin_id=admin.id,
    )
    return row


@router.post("/sys/notices/{nid}/publish", response_model=NoticeOut)
def publish_notice(
    nid: int,
    admin: User = Depends(require_perm("admin:sys:notice")),
    db: Session = Depends(get_db),
):
    row = notice_svc.publish(db, nid)
    audit_svc.log(db, admin.id, A.SYS_NOTICE_PUBLISH, target=f"notice:{nid}",
                  detail={"title": row.title})
    return row


@router.post("/sys/notices/{nid}/offline", response_model=NoticeOut)
def offline_notice(
    nid: int,
    admin: User = Depends(require_perm("admin:sys:notice")),
    db: Session = Depends(get_db),
):
    row = notice_svc.offline(db, nid)
    audit_svc.log(db, admin.id, A.SYS_NOTICE_OFFLINE, target=f"notice:{nid}")
    return row


@router.delete("/sys/notices/{nid}", response_model=OkOut)
def delete_notice(
    nid: int,
    admin: User = Depends(require_perm("admin:sys:notice")),
    db: Session = Depends(get_db),
):
    notice_svc.soft_delete(db, nid)
    return OkOut()


# ── 定时任务 ─────────────────────────────────────────────────────────────────


@router.get("/sys/jobs", response_model=list[JobOut])
def list_jobs(_: User = Depends(require_perm("admin:sys:job")), db: Session = Depends(get_db)):
    return job_svc.list_jobs(db)


@router.post("/sys/jobs/{job_id}/enable", response_model=JobOut)
def enable_job(
    job_id: int,
    admin: User = Depends(require_perm("admin:sys:job")),
    db: Session = Depends(get_db),
):
    row = job_svc.set_enabled(db, job_id, True)
    audit_svc.log(db, admin.id, A.SYS_JOB_TOGGLE, target=f"job:{row.job_key}",
                  detail={"enabled": True})
    return row


@router.post("/sys/jobs/{job_id}/disable", response_model=JobOut)
def disable_job(
    job_id: int,
    admin: User = Depends(require_perm("admin:sys:job")),
    db: Session = Depends(get_db),
):
    row = job_svc.set_enabled(db, job_id, False)
    audit_svc.log(db, admin.id, A.SYS_JOB_TOGGLE, target=f"job:{row.job_key}",
                  detail={"enabled": False})
    return row


@router.post("/sys/jobs/{job_id}/run", response_model=JobOut)
def run_job(
    job_id: int,
    admin: User = Depends(require_perm("admin:sys:job")),
    db: Session = Depends(get_db),
):
    """手动触发：next_run_at 拉到现在，worker 主循环数秒内领取执行。"""
    row = job_svc.trigger(db, job_id)
    audit_svc.log(db, admin.id, A.SYS_JOB_TRIGGER, target=f"job:{row.job_key}")
    return row


@router.get("/sys/jobs/{job_key}/logs", response_model=JobLogPage)
def job_logs(
    job_key: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_perm("admin:sys:job")),
    db: Session = Depends(get_db),
):
    rows, total = job_svc.list_logs(db, job_key, limit=limit, offset=offset)
    return JobLogPage(items=rows, total=total)
