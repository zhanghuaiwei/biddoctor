"""字典管理（sys_dict_type / sys_dict_data，05 §3.2）：仅管展示层。

取值域仍以代码枚举注册表为准（app/core/enums.py + 前端 enums.ts）——
字典新增取值不代表业务可用取值，只影响标签文案/排序/颜色展示。
"""

from sqlalchemy.orm import Session

from app.core.enums import CommonStatus
from app.core.errors import AppError
from app.models import SysDictData, SysDictType


def list_types(db: Session) -> list[SysDictType]:
    return db.query(SysDictType).order_by(SysDictType.dict_type.asc()).all()


def create_type(db: Session, *, dict_type: str, name: str, remark: str | None) -> SysDictType:
    if db.query(SysDictType.id).filter(SysDictType.dict_type == dict_type).first():
        raise AppError(409, "DICT_DATA_CONFLICT", "字典类型已存在")
    row = SysDictType(dict_type=dict_type, name=name, remark=remark)
    db.add(row)
    db.commit()
    return row


def list_data(db: Session, dict_type: str) -> list[SysDictData]:
    return (
        db.query(SysDictData)
        .filter(SysDictData.dict_type == dict_type)
        .order_by(SysDictData.sort.asc(), SysDictData.id.asc())
        .all()
    )


def create_data(db: Session, *, dict_type: str, value: str, label: str,
                sort: int = 0, extra: dict | None) -> SysDictData:
    if not db.query(SysDictType.id).filter(SysDictType.dict_type == dict_type).first():
        raise AppError(404, "DICT_NOT_FOUND", "字典类型不存在")
    dup = db.query(SysDictData.id).filter(
        SysDictData.dict_type == dict_type, SysDictData.value == value
    ).first()
    if dup:
        raise AppError(409, "DICT_DATA_CONFLICT", "该取值已存在")
    row = SysDictData(
        dict_type=dict_type, value=value, label=label, sort=sort,
        extra=extra, status=CommonStatus.ACTIVE,
    )
    db.add(row)
    db.commit()
    return row


def update_data(db: Session, data_id: int, *, label: str | None, sort: int | None,
                extra: dict | None, status: str | None) -> SysDictData:
    row = db.get(SysDictData, data_id)
    if row is None:
        raise AppError(404, "DICT_NOT_FOUND", "字典项不存在")
    for field, v in (("label", label), ("sort", sort), ("extra", extra), ("status", status)):
        if v is not None:
            setattr(row, field, v)
    db.commit()
    return row


def delete_data(db: Session, data_id: int) -> None:
    row = db.get(SysDictData, data_id)
    if row is None:
        raise AppError(404, "DICT_NOT_FOUND", "字典项不存在")
    db.delete(row)
    db.commit()
