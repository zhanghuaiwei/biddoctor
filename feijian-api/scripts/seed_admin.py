"""创建/提升管理员账号（03 §4：make seed-admin）。

用法：
    python scripts/seed_admin.py --email ops@example.com        # 不存在则创建，存在则提权
    python scripts/seed_admin.py --email ops@example.com --nickname 运营
操作写 audit_logs（action='admin_seeded'）。MVP 人工收款核销依赖 /admin/* 接口。
"""

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 支持直接 python scripts/xxx.py

from app.core.db import SessionLocal
from app.models import User
from app.services import audit_svc


def main() -> None:
    parser = argparse.ArgumentParser(description="创建或提升管理员账号")
    parser.add_argument("--email", required=True)
    parser.add_argument("--nickname", default=None)
    args = parser.parse_args()

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == args.email).first()
        if user is None:
            user = User(
                email=args.email,
                nickname=args.nickname or f"admin-{uuid.uuid4().hex[:4]}",
                role="admin",
            )
            db.add(user)
            action = "admin_created"
        elif user.role != "admin":
            user.role = "admin"
            action = "admin_promoted"
        else:
            print(f"{args.email} 已是管理员，无需变更")
            return
        db.commit()
        audit_svc.log(db, user.id, action, target=args.email)
        print(f"OK: {args.email} -> role=admin ({action}), user_id={user.id}")


if __name__ == "__main__":
    main()
