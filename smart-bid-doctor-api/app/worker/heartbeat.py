"""running 任务心跳（02 §8：每 30s 更新 heartbeat_at）。

设计基线：worker 常驻 1 进程（04 §1），因此全局刷新 running 任务心跳是安全的；
若未来横向扩 worker 实例，需改为仅刷新本实例持有的任务（实例注册表）。
"""

import logging
import threading
import time

import sqlalchemy as sa

from app.core.db import SessionLocal

log = logging.getLogger("worker")

HEARTBEAT_INTERVAL = 30.0


def beat_once() -> int:
    """把所有 running 任务心跳推到当前时间，返回受影响行数。"""
    with SessionLocal() as db:
        res = db.execute(
            sa.text("UPDATE tasks SET heartbeat_at = now() WHERE status = 'running'")
        )
        db.commit()
        return res.rowcount or 0


def start_heartbeat_thread(interval: float = HEARTBEAT_INTERVAL) -> threading.Thread:
    def loop() -> None:
        while True:
            try:
                n = beat_once()
                if n:
                    log.debug("heartbeat refreshed %s running task(s)", n)
            except Exception:
                log.exception("heartbeat failed")
            time.sleep(interval)

    t = threading.Thread(target=loop, name="task-heartbeat", daemon=True)
    t.start()
    log.info("heartbeat thread started (every %ss)", interval)
    return t
