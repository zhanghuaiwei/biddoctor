"""平台 RBAC（05 §2）：权限点解析 / 菜单树 / 用户角色 / 机构 / 邀请码。

权限模型：users.role == admin 为管理端快速判定位（登录链路零改动）；
细粒度权限点 perm（admin:<域>:<动作>）经 sys_user_role → sys_role → sys_role_menu
→ sys_menu(button) 解析。规则：
- role != admin：无任何管理权限（deps.require_perm 直接 404 同形响应防探测）；
- role == admin 且未绑定任何角色：视为超级管理员（向后兼容 seed_admin 提权路径）；
- role == admin 且绑定角色：权限点 = Σ(启用角色的菜单按钮 perm 集合)。
数据权限 data_scope：SaaS 仅用 all/self 两档，self 档由各查询按 owner 过滤。
"""

import datetime as dt
import secrets

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.enums import CommonStatus, MenuType, UserStatus
from app.core.errors import AppError
from app.models import (
    InviteCode,
    SysMenu,
    SysOrg,
    SysRole,
    SysRoleMenu,
    SysUserRole,
    User,
)

SUPER_ADMIN = "super_admin"


# ── 权限点解析 ────────────────────────────────────────────────────────────────


def perm_set(db: Session, user: User) -> set[str]:
    """当前用户全部权限点。无绑定角色的 admin = 全量（返回 {"*"}）。"""
    if user.role != "admin":
        return set()
    role_ids = [
        rid for (rid,) in db.execute(
            sa.select(SysUserRole.role_id).where(SysUserRole.user_id == user.id)
        ).all()
    ]
    if not role_ids:
        return {"*"}
    rows = db.execute(
        sa.select(SysMenu.perm)
        .join(SysRoleMenu, SysRoleMenu.menu_id == SysMenu.id)
        .where(
            SysRoleMenu.role_id.in_(role_ids),
            SysMenu.perm.is_not(None),
            SysMenu.status == CommonStatus.ACTIVE,
        )
    ).all()
    return {r[0] for r in rows}


def has_perm(perms: set[str], perm: str) -> bool:
    return "*" in perms or perm in perms


def require_perm(perms: set[str], perm: str) -> None:
    if not has_perm(perms, perm):
        # 404 同形响应：不泄露「资源存在但无权限」（05 §11 越权路径约定）
        raise AppError(404, "NOT_FOUND", "资源不存在")


# ── 菜单 ─────────────────────────────────────────────────────────────────────


def menu_tree(db: Session, perms: set[str], *, only_visible: bool = True) -> list[dict]:
    """菜单树（dir/menu），按权限点过滤按钮后代；按钮不单独成树节点。"""
    q = db.query(SysMenu).filter(
        SysMenu.status == CommonStatus.ACTIVE,
        SysMenu.type.in_([MenuType.DIR, MenuType.MENU]),
    )
    if only_visible:
        q = q.filter(SysMenu.visible.is_(True))
    rows = q.order_by(SysMenu.sort.asc(), SysMenu.id.asc()).all()
    if "*" not in perms:
        allowed = perms
        rows = [m for m in rows if _menu_allowed(db, m, allowed)]
    return _build_tree(rows, parent_id=None)


def _menu_allowed(db: Session, menu: SysMenu, allowed: set[str]) -> bool:
    """menu 可见当其子按钮任一 perm 在集合内，或子 menu 可见（递归一层即可）。"""
    children = (
        db.query(SysMenu)
        .filter(SysMenu.parent_id == menu.id, SysMenu.status == CommonStatus.ACTIVE)
        .all()
    )
    for c in children:
        if c.type == MenuType.BUTTON:
            if c.perm and (("*" in allowed) or (c.perm in allowed)):
                return True
        elif _menu_allowed(db, c, allowed):
            return True
    return False


def _build_tree(rows: list[SysMenu], parent_id: int | None) -> list[dict]:
    out = []
    for m in rows:
        if m.parent_id != parent_id:
            continue
        out.append({
            "id": m.id, "parent_id": m.parent_id, "name": m.name, "type": m.type,
            "path": m.path, "component": m.component, "icon": m.icon, "sort": m.sort,
            "visible": m.visible,
            "children": _build_tree(rows, m.id),
        })
    return out


def list_menus(db: Session) -> list[SysMenu]:
    return db.query(SysMenu).order_by(SysMenu.sort.asc(), SysMenu.id.asc()).all()


def update_menu(db: Session, menu_id: int, **fields) -> SysMenu:
    menu = db.get(SysMenu, menu_id)
    if menu is None:
        raise AppError(404, "MENU_NOT_FOUND", "菜单不存在")
    for k, v in fields.items():
        if v is not None:
            setattr(menu, k, v)
    db.commit()
    return menu


# ── 用户管理 ─────────────────────────────────────────────────────────────────


def list_users(
    db: Session, *, email: str | None = None, status: str | None = None,
    org_id: int | None = None, limit: int = 20, offset: int = 0,
) -> tuple[list[User], int]:
    q = db.query(User).filter(User.deleted_at.is_(None))
    if email:
        q = q.filter(User.email.ilike(f"%{email.lower()}%"))
    if status:
        q = q.filter(User.status == status)
    if org_id is not None:
        q = q.filter(User.org_id == org_id)
    total = q.count()
    return q.order_by(User.id.desc()).offset(offset).limit(min(limit, 100)).all(), total


def set_user_status(db: Session, operator: User, user_id: int, banned: bool) -> User:
    """禁用/解禁：不可操作自己与超管自身安全位（防自锁平台）。"""
    user = db.query(User).filter(
        User.id == user_id, User.deleted_at.is_(None)
    ).first()
    if user is None:
        raise AppError(404, "USER_NOT_FOUND", "用户不存在")
    if user.id == operator.id:
        raise AppError(409, "USER_STATE", "不能对自己执行禁用/解禁")
    user.status = UserStatus.BANNED if banned else UserStatus.ACTIVE
    db.commit()
    return user


def list_user_roles(db: Session, user_id: int) -> list[SysRole]:
    return (
        db.query(SysRole)
        .join(SysUserRole, SysUserRole.role_id == SysRole.id)
        .filter(SysUserRole.user_id == user_id)
        .order_by(SysRole.sort.asc())
        .all()
    )


def set_user_roles(db: Session, user_id: int, role_ids: list[int]) -> None:
    """全量覆写用户角色（PUT 语义）。同事务删旧插新，半失败回滚。"""
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if user is None:
        raise AppError(404, "USER_NOT_FOUND", "用户不存在")
    roles = db.query(SysRole).filter(
        SysRole.id.in_(role_ids), SysRole.status == CommonStatus.ACTIVE,
        SysRole.deleted_at.is_(None),
    ).all()
    if len(roles) != len(set(role_ids)):
        raise AppError(404, "ROLE_NOT_FOUND", "包含不存在或已停用的角色")
    db.query(SysUserRole).filter(SysUserRole.user_id == user_id).delete()
    for rid in role_ids:
        db.add(SysUserRole(user_id=user_id, role_id=rid))
    db.commit()


# ── 角色 ─────────────────────────────────────────────────────────────────────


def list_roles(db: Session) -> list[SysRole]:
    return (
        db.query(SysRole)
        .filter(SysRole.deleted_at.is_(None))
        .order_by(SysRole.sort.asc(), SysRole.id.asc())
        .all()
    )


def set_role_menus(db: Session, role_id: int, menu_ids: list[int]) -> None:
    """全量覆写角色菜单（PUT 语义）：仅允许勾选实际存在的菜单节点。"""
    role = db.query(SysRole).filter(
        SysRole.id == role_id, SysRole.deleted_at.is_(None)
    ).first()
    if role is None:
        raise AppError(404, "ROLE_NOT_FOUND", "角色不存在")
    valid = {
        mid for (mid,) in db.execute(sa.select(SysMenu.id)).all()
    }
    if not set(menu_ids) <= valid:
        raise AppError(404, "MENU_NOT_FOUND", "包含不存在的菜单")
    db.query(SysRoleMenu).filter(SysRoleMenu.role_id == role_id).delete()
    for mid in set(menu_ids):
        db.add(SysRoleMenu(role_id=role_id, menu_id=mid))
    db.commit()


# ── 机构 ─────────────────────────────────────────────────────────────────────


def org_tree(db: Session) -> list[dict]:
    rows = (
        db.query(SysOrg)
        .filter(SysOrg.deleted_at.is_(None))
        .order_by(SysOrg.sort.asc(), SysOrg.id.asc())
        .all()
    )
    return _build_org_tree(rows, None)


def _build_org_tree(rows: list[SysOrg], parent_id: int | None) -> list[dict]:
    out = []
    for o in rows:
        if o.parent_id != parent_id:
            continue
        out.append({
            "id": o.id, "parent_id": o.parent_id, "name": o.name, "code": o.code,
            "sort": o.sort, "leader": o.leader, "status": o.status,
            "children": _build_org_tree(rows, o.id),
        })
    return out


def create_org(db: Session, *, name: str, parent_id: int | None, code: str | None,
               sort: int = 0, leader: str | None) -> SysOrg:
    if parent_id is not None:
        parent = db.query(SysOrg).filter(
            SysOrg.id == parent_id, SysOrg.deleted_at.is_(None)
        ).first()
        if parent is None:
            raise AppError(404, "ORG_NOT_FOUND", "上级机构不存在")
    org = SysOrg(name=name, parent_id=parent_id, code=code, sort=sort, leader=leader)
    db.add(org)
    db.commit()  # code 唯一约束冲突 → IntegrityError 500（管理端低频，可接受）
    return org


def update_org(db: Session, org_id: int, **fields) -> SysOrg:
    org = db.query(SysOrg).filter(SysOrg.id == org_id, SysOrg.deleted_at.is_(None)).first()
    if org is None:
        raise AppError(404, "ORG_NOT_FOUND", "机构不存在")
    if "parent_id" in fields and fields["parent_id"] is not None:
        if fields["parent_id"] == org.id:
            raise AppError(409, "ORG_STATE", "上级机构不能是自身")
        parent = db.query(SysOrg).filter(
            SysOrg.id == fields["parent_id"], SysOrg.deleted_at.is_(None)
        ).first()
        if parent is None:
            raise AppError(404, "ORG_NOT_FOUND", "上级机构不存在")
    for k, v in fields.items():
        if v is not None:
            setattr(org, k, v)
    db.commit()
    return org


def delete_org(db: Session, org_id: int) -> None:
    """机构软删：有子节点或在职用户挂靠时拒绝（05 §2.4）。"""
    org = db.query(SysOrg).filter(SysOrg.id == org_id, SysOrg.deleted_at.is_(None)).first()
    if org is None:
        raise AppError(404, "ORG_NOT_FOUND", "机构不存在")
    has_child = db.query(SysOrg.id).filter(
        SysOrg.parent_id == org_id, SysOrg.deleted_at.is_(None)
    ).first() is not None
    if has_child:
        raise AppError(409, "ORG_HAS_CHILDREN", "存在下级机构，先删除下级")
    has_user = db.query(User.id).filter(
        User.org_id == org_id, User.deleted_at.is_(None)
    ).first() is not None
    if has_user:
        raise AppError(409, "ORG_HAS_USERS", "仍有用户挂靠该机构，先移出用户")
    org.deleted_at = dt.datetime.now(dt.UTC)
    db.commit()


# ── 邀请码（P1 邀测预留）────────────────────────────────────────────────────


def issue_invite_code(db: Session, admin_id: int, max_uses: int, ttl_days: int) -> InviteCode:
    code = secrets.token_hex(4).upper()  # 8 位大写十六进制
    row = InviteCode(
        code=code, max_uses=max_uses,
        expires_at=(dt.datetime.now(dt.UTC) + dt.timedelta(days=ttl_days))
        if ttl_days > 0 else None,
        created_by=admin_id,
    )
    db.add(row)
    db.commit()
    return row


def list_invite_codes(db: Session, *, limit: int = 20, offset: int = 0) -> tuple[list[InviteCode], int]:
    q = db.query(InviteCode)
    total = q.count()
    return q.order_by(InviteCode.id.desc()).offset(offset).limit(min(limit, 100)).all(), total


def consume_invite_code(db: Session, code: str) -> bool:
    """邀测注册管控：原子 UPDATE used_count（used_count<max_uses 且未过期）+ rowcount 判定。"""
    now = dt.datetime.now(dt.UTC)
    res = db.execute(
        sa.update(InviteCode)
        .where(
            InviteCode.code == code.strip().upper(),
            sa.or_(InviteCode.expires_at.is_(None), InviteCode.expires_at > now),
            InviteCode.used_count < InviteCode.max_uses,
        )
        .values(used_count=InviteCode.used_count + 1)
    )
    return res.rowcount > 0
