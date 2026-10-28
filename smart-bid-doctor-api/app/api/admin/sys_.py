"""系统管理端点（05 §2 / §10 表 5）：机构 / 角色 / 菜单 / 用户 / 邀请码。

权限点：admin:sys:org | admin:sys:role | admin:sys:menu | admin:sys:user。
角色授予/撤销、用户禁用/解禁、机构变更均写审计（05 §5.2）。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_perm
from app.core.errors import AppError
from app.models import User
from app.schemas.platform import (
    AdminUserOut,
    AdminUserPage,
    InviteIssueIn,
    InviteOut,
    InvitePage,
    MenuNode,
    MenuOut,
    MenuUpdate,
    OkOut,
    OrgIn,
    OrgNode,
    OrgUpdate,
    RoleMenusIn,
    RoleOut,
    UserRolesIn,
    UserRolesOut,
)
from app.services import audit_svc, rbac_svc

router = APIRouter(tags=["admin-sys"])

A = audit_svc.AuditAction


# ── 机构 ─────────────────────────────────────────────────────────────────────


@router.get("/sys/orgs/tree", response_model=list[OrgNode])
def org_tree(_: User = Depends(require_perm("admin:sys:org")), db: Session = Depends(get_db)):
    return rbac_svc.org_tree(db)


@router.post("/sys/orgs", response_model=OrgNode, status_code=201)
def create_org(
    body: OrgIn,
    admin: User = Depends(require_perm("admin:sys:org")),
    db: Session = Depends(get_db),
):
    org = rbac_svc.create_org(
        db, name=body.name, parent_id=body.parent_id, code=body.code,
        sort=body.sort, leader=body.leader,
    )
    audit_svc.log(db, admin.id, A.SYS_ORG_UPDATE, target=f"org:{org.id}",
                  detail={"op": "create", "name": org.name})
    return OrgNode(id=org.id, parent_id=org.parent_id, name=org.name, code=org.code,
                   sort=org.sort, leader=org.leader, status=org.status, children=[])


@router.patch("/sys/orgs/{org_id}", response_model=OkOut)
def update_org(
    org_id: int, body: OrgUpdate,
    admin: User = Depends(require_perm("admin:sys:org")),
    db: Session = Depends(get_db),
):
    fields = body.model_dump(exclude_unset=True)
    rbac_svc.update_org(db, org_id, **fields)
    audit_svc.log(db, admin.id, A.SYS_ORG_UPDATE, target=f"org:{org_id}",
                  detail={"op": "update", "fields": sorted(fields)})
    return OkOut()


@router.delete("/sys/orgs/{org_id}", response_model=OkOut)
def delete_org(
    org_id: int,
    admin: User = Depends(require_perm("admin:sys:org")),
    db: Session = Depends(get_db),
):
    rbac_svc.delete_org(db, org_id)
    audit_svc.log(db, admin.id, A.SYS_ORG_UPDATE, target=f"org:{org_id}",
                  detail={"op": "delete"})
    return OkOut()


# ── 角色 ─────────────────────────────────────────────────────────────────────


@router.get("/sys/roles", response_model=list[RoleOut])
def list_roles(_: User = Depends(require_perm("admin:sys:role")), db: Session = Depends(get_db)):
    return rbac_svc.list_roles(db)


@router.get("/sys/users/{uid}/roles", response_model=UserRolesOut)
def user_roles(
    uid: int,
    _: User = Depends(require_perm("admin:sys:role")),
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.id == uid, User.deleted_at.is_(None)).first() is None:
        raise AppError(404, "USER_NOT_FOUND", "用户不存在")
    return UserRolesOut(roles=rbac_svc.list_user_roles(db, uid))


@router.put("/sys/users/{uid}/roles", response_model=OkOut)
def set_user_roles(
    uid: int, body: UserRolesIn,
    admin: User = Depends(require_perm("admin:sys:role")),
    db: Session = Depends(get_db),
):
    rbac_svc.set_user_roles(db, uid, body.role_ids)
    audit_svc.log(db, admin.id, A.SYS_ROLE_GRANT, target=f"user:{uid}",
                  detail={"role_ids": body.role_ids})
    return OkOut()


@router.put("/sys/roles/{rid}/menus", response_model=OkOut)
def set_role_menus(
    rid: int, body: RoleMenusIn,
    admin: User = Depends(require_perm("admin:sys:menu")),
    db: Session = Depends(get_db),
):
    rbac_svc.set_role_menus(db, rid, body.menu_ids)
    audit_svc.log(db, admin.id, A.SYS_MENU_UPDATE, target=f"role:{rid}",
                  detail={"menu_ids": body.menu_ids})
    return OkOut()


# ── 菜单 ─────────────────────────────────────────────────────────────────────


@router.get("/sys/menus", response_model=list[MenuOut])
def list_menus(_: User = Depends(require_perm("admin:sys:menu")), db: Session = Depends(get_db)):
    return rbac_svc.list_menus(db)


@router.get("/sys/menus/tree", response_model=list[MenuNode])
def menu_tree(_: User = Depends(require_perm("admin:sys:menu")), db: Session = Depends(get_db)):
    return rbac_svc.menu_tree(db, {"*"}, only_visible=False)


@router.patch("/sys/menus/{menu_id}", response_model=OkOut)
def update_menu(
    menu_id: int, body: MenuUpdate,
    admin: User = Depends(require_perm("admin:sys:menu")),
    db: Session = Depends(get_db),
):
    fields = body.model_dump(exclude_unset=True)
    rbac_svc.update_menu(db, menu_id, **fields)
    audit_svc.log(db, admin.id, A.SYS_MENU_UPDATE, target=f"menu:{menu_id}",
                  detail={"fields": sorted(fields)})
    return OkOut()


# ── 用户管理 ─────────────────────────────────────────────────────────────────


@router.get("/sys/users", response_model=AdminUserPage)
def list_users(
    email: str | None = None,
    status: str | None = None,
    org_id: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_perm("admin:sys:user")),
    db: Session = Depends(get_db),
):
    from app.models import SysOrg

    rows, total = rbac_svc.list_users(db, email=email, status=status, org_id=org_id,
                                      limit=limit, offset=offset)
    org_names = {}
    org_ids = {r.org_id for r in rows if r.org_id}
    if org_ids:
        org_names = {o.id: o.name for o in db.query(SysOrg).filter(SysOrg.id.in_(org_ids)).all()}
    items = [
        AdminUserOut.model_validate(u).model_copy(
            update={"org_name": org_names.get(u.org_id)}
        )
        for u in rows
    ]
    return AdminUserPage(items=items, total=total)


@router.post("/sys/users/{uid}/ban", response_model=OkOut)
def ban_user(
    uid: int,
    admin: User = Depends(require_perm("admin:sys:user")),
    db: Session = Depends(get_db),
):
    rbac_svc.set_user_status(db, admin, uid, banned=True)
    audit_svc.log(db, admin.id, A.SYS_USER_BAN, target=f"user:{uid}")
    return OkOut()


@router.post("/sys/users/{uid}/unban", response_model=OkOut)
def unban_user(
    uid: int,
    admin: User = Depends(require_perm("admin:sys:user")),
    db: Session = Depends(get_db),
):
    rbac_svc.set_user_status(db, admin, uid, banned=False)
    audit_svc.log(db, admin.id, A.SYS_USER_UNBAN, target=f"user:{uid}")
    return OkOut()


# ── 邀请码 ───────────────────────────────────────────────────────────────────


@router.post("/sys/invites", response_model=InviteOut, status_code=201)
def issue_invite(
    body: InviteIssueIn,
    admin: User = Depends(require_perm("admin:sys:user")),
    db: Session = Depends(get_db),
):
    row = rbac_svc.issue_invite_code(db, admin.id, max(1, body.max_uses), max(0, body.ttl_days))
    audit_svc.log(db, admin.id, A.SYS_INVITE_ISSUE, target=f"invite:{row.id}",
                  detail={"max_uses": row.max_uses})
    return row


@router.get("/sys/invites", response_model=InvitePage)
def list_invites(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_perm("admin:sys:user")),
    db: Session = Depends(get_db),
):
    rows, total = rbac_svc.list_invite_codes(db, limit=limit, offset=offset)
    return InvitePage(items=rows, total=total)
