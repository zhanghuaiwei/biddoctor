"""E1 压测脚本（04 §7）：50 并发上传 + 100 并发查询，零新增依赖（httpx 既有）。

用法（cwd 任意，目标为已启动的 api 服务，dev 环境固定验证码 123456）：
    python scripts/load_test.py --base-url http://localhost:8000 --email ben@x.com
    python scripts/load_test.py --base-url http://localhost:8000 --email ben@x.com \
        --upload-concurrency 50 --query-concurrency 100

流程：登录拿 token（dev 发码+固定验证码）→ 建 1 个压测项目 →
  场景一 upload：并发上传互异 PDF（页数递增防 sha 去重复用同一路径）；
  场景二 query：并发 GET /api/projects。
输出：请求数 / 错误率 / RPS / P50 / P95 / P99（秒）。
注意：压测会产生真实上传文件与解析任务，压完在压测环境执行 purge/清理。
"""

import argparse
import asyncio
import io
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def make_pdf(pages: int) -> bytes:
    """pypdf 生成页数互异的合法 PDF（防 sha256 去重，同时覆盖解析链路输入形态）。"""
    from pypdf import PdfWriter

    buf = io.BytesIO()
    writer = PdfWriter()
    for _ in range(max(pages, 1)):
        writer.add_blank_page(width=612, height=792)
    writer.write(buf)
    return buf.getvalue()


def pct(values: list[float], p: float) -> float:
    """分位数（纯函数可单测）：最近秩法，与常用监控口径一致。"""
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(round(p / 100 * len(s) + 0.5)) - 1))
    return s[idx]


async def _timed(coro_factory, latencies: list[float], errors: list[str], sem: asyncio.Semaphore):
    async with sem:
        start = time.monotonic()
        try:
            resp = await coro_factory()
            if resp.status_code >= 400:
                errors.append(f"HTTP {resp.status_code}: {resp.text[:120]}")
        except Exception as exc:  # noqa: BLE001 压测统计一切异常
            errors.append(f"{type(exc).__name__}: {exc}")
            raise
        finally:
            latencies.append(time.monotonic() - start)


async def login(client: httpx.AsyncClient, base: str, email: str) -> str:
    r = await client.post(f"{base}/api/auth/email-code", json={"email": email})
    if r.status_code >= 400:
        raise SystemExit(f"发码失败 {r.status_code}: {r.text[:200]}")
    r = await client.post(f"{base}/api/auth/login", json={"email": email, "code": "123456"})
    if r.status_code >= 400:
        raise SystemExit(f"登录失败 {r.status_code}: {r.text[:200]}（prod 环境无固定验证码，压测需 dev）")
    return r.json()["token"]


async def run_upload(client, base, headers, pid, concurrency, latencies, errors):
    sem = asyncio.Semaphore(concurrency)

    async def one(i: int):
        files = {"file": (f"load-{i}.pdf", io.BytesIO(make_pdf(i % 50 + 1)), "application/pdf")}
        await _timed(
            lambda: client.post(f"{base}/api/projects/{pid}/documents",
                                headers=headers, files=files, data={"role": "tender"}),
            latencies, errors, sem)

    await asyncio.gather(*(one(i) for i in range(concurrency)))


async def run_query(client, base, headers, concurrency, latencies, errors):
    sem = asyncio.Semaphore(concurrency)

    async def one(i: int):
        await _timed(
            lambda: client.get(f"{base}/api/projects", headers=headers,
                               params={"limit": 20, "offset": i % 5}),
            latencies, errors, sem)

    await asyncio.gather(*(one(i) for i in range(concurrency)))


def report(name: str, latencies: list[float], errors: list[str], wall: float) -> None:
    total = len(latencies)
    err_rate = len(errors) / total if total else 0.0
    print(f"\n[{name}] 请求数 {total} · 错误 {len(errors)} ({err_rate:.1%}) · "
          f"RPS {total / wall:.1f} · P50 {pct(latencies, 50):.3f}s · "
          f"P95 {pct(latencies, 95):.3f}s · P99 {pct(latencies, 99):.3f}s")
    for e in errors[:5]:
        print(f"  err: {e}")


async def main_async(args) -> None:
    async with httpx.AsyncClient(timeout=120) as client:
        token = await login(client, args.base_url, args.email)
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.post(f"{args.base_url}/api/projects", headers=headers,
                              json={"name": f"压测-{int(time.time())}", "industry": "general"})
        if r.status_code != 201:
            raise SystemExit(f"建项目失败 {r.status_code}: {r.text[:200]}")
        pid = r.json()["id"]
        print(f"[setup] 项目 {pid} · 目标 {args.base_url}")

        lat: list[float] = []
        errs: list[str] = []
        t0 = time.monotonic()
        await run_upload(client, args.base_url, headers, pid,
                         args.upload_concurrency, lat, errs)
        report("upload 50 并发", lat, errs, time.monotonic() - t0)

        lat2: list[float] = []
        errs2: list[str] = []
        t1 = time.monotonic()
        await run_query(client, args.base_url, headers,
                        args.query_concurrency, lat2, errs2)
        report("query 100 并发", lat2, errs2, time.monotonic() - t1)

    print("\n达标口径（04 §7）：上传 P95 < 3s 且错误率 0；查询 P95 < 500ms 且错误率 0。"
          "压测产物清理：压测环境跑 make restore-backup 或 purge 生命周期任务。")


def main() -> None:
    ap = argparse.ArgumentParser(description="E1 压测（50 上传 + 100 查询）")
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--email", required=True, help="压测账号（dev 环境）")
    ap.add_argument("--upload-concurrency", type=int, default=50)
    ap.add_argument("--query-concurrency", type=int, default=100)
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
