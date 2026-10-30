"""M1/B4 金标集评测（02 §10）：抽取召回 ≥90% 门槛，预筛候选召回 ≥98% 门槛。

用法（cwd = smart-bid-doctor-api）：
    python scripts/eval_extract.py --prescreen-only   # 只验预筛召回（无需 LLM，随时可跑）
    python scripts/eval_extract.py                    # 完整抽取评测（需 LLM 接入，A/C 桩期退出码 2）
    make eval                                         # 同上（Makefile 入口）

金标集：eval/golden.json（blocks 与解析引擎产物同构，expect 为人工标注条款）。
指标：recall = TP/期望数、precision = TP/输出数、F2 = 5PR/(4P+R)（召回加权，
02 §10 验收口径）；匹配规则 = 同 category 且归一化原文双向 containment ≥0.8 且同页。

退出码：0 达标 · 1 未达标 · 2 依赖缺失（LLM 未接入 / 金标文件不存在）。
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 支持直接 python scripts/xxx.py

from app.engine.extractor import _norm_text as norm  # noqa: E402 与引擎同口径，避免双份实现漂移

GOLDEN_PATH = Path(__file__).resolve().parent.parent.parent / "eval" / "golden.json"
PRESCREEN_THRESHOLD = 0.98
EXTRACT_THRESHOLD = 0.90


def containment(a: str, b: str) -> float:
    """归一化后双向包含比例：短串在长串中的字符覆盖率。"""
    if not a or not b:
        return 0.0
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    hit = sum(1 for ch in shorter if ch in longer)
    return hit / max(len(shorter), 1)


def load_golden(path: Path) -> dict:
    if not path.exists():
        print(f"[eval] 金标集不存在：{path}")
        raise SystemExit(2)
    return json.loads(path.read_text(encoding="utf-8"))


# ── 预筛评测（C1 验收：候选召回 ≥98%）────────────────────────────────────────

def eval_prescreen(cases: list[dict]) -> dict:
    from app.engine import extractor

    per_case = []
    total_expect = hit = 0
    for case in cases:
        blocks = [_mk_block(b) for b in case["blocks"]]
        cands, stats = extractor.prescreen(blocks, ())
        cand_norm = "\n".join(norm(c.text) for c in cands)
        case_hit = 0
        misses = []
        for exp in case["expect"]:
            total_expect += 1
            e = norm(exp["raw_text"])
            if containment(e, cand_norm) >= 0.8 or e in cand_norm:
                case_hit += 1
                hit += 1
            else:
                misses.append(exp["raw_text"][:40])
        per_case.append({"case": case["name"], "expect": len(case["expect"]),
                         "hit": case_hit, "candidates": stats.candidates,
                         "miss": misses})
    recall = hit / total_expect if total_expect else 0.0
    return {"mode": "prescreen", "recall": round(recall, 4),
            "threshold": PRESCREEN_THRESHOLD, "pass": recall >= PRESCREEN_THRESHOLD,
            "cases": per_case}


# ── 完整抽取评测（C 验收：召回 ≥90%，需 LLM）─────────────────────────────────

def eval_full(cases: list[dict]) -> dict:
    from app.core.errors import AppError
    from app.engine import extractor
    from app.llm import zhipu

    provider = zhipu.ZhipuProvider()
    per_case = []
    total_expect = tp = 0
    all_out = 0
    for case in cases:
        blocks = [_mk_block(b) for b in case["blocks"]]
        cands, _ = extractor.prescreen(blocks, ())
        raw_items: list[extractor.ExtractedItem] = []
        for batch in extractor.build_batches(cands):
            messages = zhipu.default_messages(
                None, extractor.build_user_prompt(batch))
            try:
                res = provider.chat(messages, json_mode=True, tier="heavy", purpose="extract")
                raw_items.extend(extractor.parse_items(res.content))
            except extractor.ItemFormatError:
                continue  # 坏输出计入 loss（与线上 handler 语义一致：重试由 provider 层负责）
            except AppError as exc:
                print(f"[eval] LLM 调用失败：{exc.code} {exc.message}")
                print("[eval] 完整评测依赖 LLM 接入（Agent 能力 TODO）。"
                      "当前可跑：make eval --prescreen-only（预筛召回）")
                raise SystemExit(2) from exc
        items = extractor.normalize_and_dedup(raw_items)
        all_out += len(items)
        case_hit = 0
        misses = []
        matched = set()
        for exp in case["expect"]:
            total_expect += 1
            e = norm(exp["raw_text"])
            for idx, it in enumerate(items):
                if idx in matched or it.category != exp["category"] or it.ref_page != exp["ref_page"]:
                    continue
                if containment(e, norm(it.raw_text)) >= 0.8:
                    matched.add(idx)
                    case_hit += 1
                    tp += 1
                    break
            else:
                misses.append(exp["raw_text"][:40])
        per_case.append({"case": case["name"], "expect": len(case["expect"]),
                         "hit": case_hit, "extracted": len(items), "miss": misses})
    recall = tp / total_expect if total_expect else 0.0
    precision = tp / all_out if all_out else 0.0
    f2 = (5 * precision * recall / (4 * precision + recall)) if (precision + recall) else 0.0
    return {"mode": "full", "recall": round(recall, 4), "precision": round(precision, 4),
            "f2": round(f2, 4), "threshold": EXTRACT_THRESHOLD,
            "pass": recall >= EXTRACT_THRESHOLD, "cases": per_case}


def _mk_block(b: dict):
    from types import SimpleNamespace

    return SimpleNamespace(page=b["page"], seq=b["seq"], type=b.get("type", "text"),
                           text=b["text"], section=b.get("section"))


def _print_report(report: dict) -> None:
    print(f"\n=== eval [{report['mode']}] recall={report['recall']} "
          f"(门槛 {report['threshold']}) → {'PASS' if report['pass'] else 'FAIL'} ===")
    for c in report["cases"]:
        line = f"  {c['case']}: 期望 {c['expect']} 命中 {c['hit']}"
        if "extracted" in c:
            line += f" 抽出 {c['extracted']}"
        print(line)
        for m in c.get("miss", []):
            print(f"    ✗ 漏: {m}")
    if report["mode"] == "full":
        print(f"  precision={report['precision']} F2={report['f2']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="M1/B4 金标集评测")
    ap.add_argument("--prescreen-only", action="store_true",
                    help="只评测预筛候选召回（无需 LLM）")
    ap.add_argument("--golden", default=str(GOLDEN_PATH), help="金标集路径")
    args = ap.parse_args()

    golden = load_golden(Path(args.golden))
    report = eval_prescreen(golden["cases"]) if args.prescreen_only else eval_full(golden["cases"])
    _print_report(report)
    print(json.dumps({k: v for k, v in report.items() if k != "cases"},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
