"""每日业务自查报表（04 §6：每日 08:00，输出昨日运营指标）。

产出 JSON 落盘到 FJ_REPORT_DIR（默认 ./data/reports/daily/）：
    - 昨日任务成功率 / 各状态分布
    - 昨日任务平均耗时（秒，finished_at - created_at）
    - 昨日 LLM token 成本（llm_calls 汇总；M1 接入后非零）
    - 昨日失败 top 错误码
    - 当前 pending 积压

crontab: 0 8 * * *  cd /srv && python scripts/daily_report.py
"""

import datetime as dt
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 支持直接 python scripts/xxx.py

import sqlalchemy as sa

from app.core.db import SessionLocal
from app.models import LlmCall, Task


def main() -> None:
    now = dt.datetime.now(dt.UTC)
    day_start = (now - dt.timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    day_end = day_start + dt.timedelta(days=1)

    with SessionLocal() as db:
        rows = (
            db.query(Task.status, sa.func.count(Task.id))
            .filter(Task.created_at >= day_start, Task.created_at < day_end)
            .group_by(Task.status)
            .all()
        )
        by_status = {status: int(n) for status, n in rows}
        total = sum(by_status.values())
        succeeded = by_status.get("succeeded", 0)
        # 仅统计已完结任务的平均耗时
        avg_secs = (
            db.query(
                sa.func.avg(
                    sa.extract("epoch", Task.finished_at) - sa.extract("epoch", Task.created_at)
                )
            )
            .filter(
                Task.created_at >= day_start,
                Task.created_at < day_end,
                Task.finished_at.is_not(None),
            )
            .scalar()
        )
        top_errors = (
            db.query(Task.error_code, sa.func.count(Task.id))
            .filter(
                Task.created_at >= day_start,
                Task.created_at < day_end,
                Task.status == "failed",
                Task.error_code.is_not(None),
            )
            .group_by(Task.error_code)
            .order_by(sa.func.count(Task.id).desc())
            .limit(5)
            .all()
        )
        cost = (
            db.query(sa.func.coalesce(sa.func.sum(LlmCall.cost_cny), 0))
            .filter(LlmCall.created_at >= day_start, LlmCall.created_at < day_end)
            .scalar()
        )
        backlog = (
            db.query(sa.func.count(Task.id)).filter(Task.status == "pending").scalar() or 0
        )

    report = {
        "date": day_start.date().isoformat(),
        "tasks_total": total,
        "tasks_by_status": by_status,
        "success_rate": round(succeeded / total, 4) if total else None,
        "avg_duration_secs": round(float(avg_secs), 1) if avg_secs is not None else None,
        "llm_cost_cny": float(cost),
        "top_error_codes": [{"code": code, "count": int(n)} for code, n in top_errors],
        "pending_backlog": int(backlog),
    }

    out_dir = os.environ.get("FJ_REPORT_DIR", "./data/reports/daily")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{report['date']}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nsaved -> {out_path}")


if __name__ == "__main__":
    main()
