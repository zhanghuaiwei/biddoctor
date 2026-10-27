"""每日业务自查报表（04 §6：每日 08:00，输出昨日运营指标）。

聚合逻辑统一走 services/metrics_svc（与 /internal/metrics 共用单一实现）。
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

from app.core.db import SessionLocal
from app.services import metrics_svc


def main() -> None:
    now = dt.datetime.now(dt.UTC)
    day_start = (now - dt.timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    day_end = day_start + dt.timedelta(days=1)

    with SessionLocal() as db:
        report = metrics_svc.daily_stats(db, day_start, day_end)

    report = {"date": day_start.date().isoformat(), **report}

    out_dir = os.environ.get("FJ_REPORT_DIR", "./data/reports/daily")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{report['date']}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nsaved -> {out_path}")


if __name__ == "__main__":
    main()
