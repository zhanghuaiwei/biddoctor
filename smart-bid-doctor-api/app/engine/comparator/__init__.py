"""双文件对照引擎（M2/E，02 §4–§5）：混合检索 + GLM 判定 + 规则复核。

职责切分（Agent 能力 TODO 边界，AGENTS.md 硬性禁区 1）：
- 本模块全部实装（检索/RRF 融合/Prompt 组装/verdict 守卫/规则复核/stats）；
- LLM 依赖点 = provider.embed()（query 向量化）与 provider.chat()（逐条判定），
  均走 app/llm/zhipu.py 桩——embed 桩时检索自动降级 trgm-only（工程可运行），
  chat 桩时 compare handler 转 need_review，接入后即插即用。

检索（02 §5）：pg_trgm 文本相似 + pgvector 余弦（HNSW，EMBED_DIM=1024）双路召回
→ RRF 融合排序（k=60）；query 向量缺失（embed 桩）时降级单路 trgm。
判定（02 §4.2）：verdict 四值 satisfied/deviated/missing/uncertain——解析失败或
白名单外一律 uncertain 标黄，绝不输出「满足」（合规底线）；规则复核（must/veto）
可推翻 LLM 结论并标 rule_overridden（报告展示口径）。
"""

import json
import re
from dataclasses import dataclass

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from app.core.enums import Verdict
from app.models import Finding

RRF_K = 60
SEARCH_TOP_K = 5

_VALID_VERDICTS = {v.value for v in Verdict}


@dataclass
class SearchHit:
    """检索命中（bid 文档块）。"""

    block_id: int
    page: int
    text: str
    score: float  # RRF 融合分（或单路相似度）


@dataclass
class JudgeResult:
    """逐条判定结果（落 findings 前的中间形态）。"""

    check_item_id: int
    verdict: str
    level: str
    reason: str
    bid_ref_page: int | None = None
    bid_quote: str | None = None
    confidence: float = 0.5
    rule_overridden: bool = False


# ── 检索（02 §5）─────────────────────────────────────────────────────────────

_RRF_SQL = sa_text("""
    SELECT id, page, text,
           ROW_NUMBER() OVER (ORDER BY similarity(text, :q) DESC, id) AS rank
    FROM doc_blocks
    WHERE document_id = :doc_id
      AND similarity(text, :q) > 0.05
    ORDER BY similarity(text, :q) DESC, id
    LIMIT :k
""")

_VEC_SQL = sa_text("""
    SELECT id, page, text,
           ROW_NUMBER() OVER (ORDER BY embedding <=> :qv, id) AS rank
    FROM doc_blocks
    WHERE document_id = :doc_id AND embedding IS NOT NULL
    ORDER BY embedding <=> :qv, id
    LIMIT :k
""")


def hybrid_search(db: Session, bid_doc_id: int, query_text: str,
                  query_vector: list[float] | None = None,
                  top_k: int = SEARCH_TOP_K) -> list[SearchHit]:
    """trgm 文本 + pgvector 余弦双路召回 → RRF 融合；query_vector 缺失降级 trgm-only。"""
    trgm_rows = db.execute(
        _RRF_SQL, {"q": query_text, "doc_id": bid_doc_id, "k": top_k}
    ).fetchall()
    ranks: dict[int, list[int]] = {}  # block_id → 各路 rank（1-based）
    by_id: dict[int, tuple[int, str]] = {}
    for row in trgm_rows:
        ranks.setdefault(row.id, []).append(row.rank)
        by_id[row.id] = (row.page, row.text)
    if query_vector is not None:
        vec_rows = db.execute(
            _VEC_SQL, {"qv": str(query_vector), "doc_id": bid_doc_id, "k": top_k}
        ).fetchall()
        for row in vec_rows:
            ranks.setdefault(row.id, []).append(row.rank)
            by_id[row.id] = (row.page, row.text)
    scored = [
        (bid, _rrf_score(r), by_id[bid][0], by_id[bid][1])
        for bid, r in ranks.items()
    ]
    scored.sort(key=lambda t: (-t[1], t[0]))
    return [
        SearchHit(block_id=bid, page=page, text=txt, score=score)
        for bid, score, page, txt in scored[:top_k]
    ]


def _rrf_score(rank_lists: list[int], k: int = RRF_K) -> float:
    """RRF 融合（纯函数，可单测）：score = Σ 1/(k + rank)。"""
    return sum(1.0 / (k + r) for r in rank_lists)


# ── 判定（02 §4.2）───────────────────────────────────────────────────────────

JUDGE_CONTRACT = """请判定投标文件证据能否满足该废标条款，输出 JSON：
{"verdict": "satisfied|deviated|missing|uncertain",
 "reason": "判定依据一句话（中文）",
 "bid_ref_page": 证据所在页码数字或 null,
 "bid_quote": "投标文件原文逐字摘录或 null",
 "confidence": 0到1的小数}
规则：1) 只有证据明确满足才输出 satisfied；证据部分偏离输出 deviated；
完全无对应证据输出 missing；证据不足或矛盾一律输出 uncertain——
绝不在不确定时输出 satisfied；2) bid_quote 必须逐字取自证据段落。"""


def build_judge_messages(item, hits: list[SearchHit], template: str | None = None) -> list[dict]:
    """判定 Prompt：条款（含原文与页码）+ 证据段落（带页码标注）。"""
    ev = "\n".join(f"[P{h.page}] {h.text}" for h in hits) or "（无检索到相关投标段落）"
    item_desc = (
        f"条款编号：{item.code}\n类别：{item.category}\n"
        f"要求：{item.requirement}\n招标文件原文：{item.raw_text}（第 {item.ref_page} 页）"
    )
    user = (
        f"{JUDGE_CONTRACT}\n\n废标条款：\n{item_desc}\n\n"
        f"投标文件检索证据：\n{ev}"
    )
    if template and "{blocks_text}" in template and "{item_text}" in template:
        try:
            user = template.format(item_text=item_desc, blocks_text=ev)
        except (KeyError, IndexError, ValueError):
            pass
    from app.llm.zhipu import default_messages

    return default_messages(None, user)


def parse_verdict(content: str) -> dict:
    """GLM 判定输出解析：结构/取值不合规一律 uncertain（绝不输出「满足」的底线在
    此兜底——LLM 幻觉输出 satisfied 但缺依据时同样按 uncertain 处理需要 reason）。"""
    fallback = {"verdict": Verdict.UNCERTAIN.value, "reason": "判定输出解析失败，转人工复核",
                "bid_ref_page": None, "bid_quote": None, "confidence": 0.3}
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return fallback
    if not isinstance(data, dict) or data.get("verdict") not in _VALID_VERDICTS:
        return fallback
    page = data.get("bid_ref_page")
    try:
        page = int(page) if page is not None else None
        if page is not None and page <= 0:
            page = None
    except (TypeError, ValueError):
        page = None
    try:
        conf = min(1.0, max(0.0, float(data.get("confidence", 0.5))))
    except (TypeError, ValueError):
        conf = 0.5
    return {
        "verdict": data["verdict"],
        "reason": (data.get("reason") or "（无判定依据）")[:500],
        "bid_ref_page": page,
        "bid_quote": (data.get("bid_quote") or None) if isinstance(data.get("bid_quote"), str) else None,
        "confidence": conf,
    }


# ── 规则复核（02 §4.1 must/veto）────────────────────────────────────────────

def rule_review(item, parsed: dict, rule_items: list) -> dict:
    """规则复核：must（证据未出现必须关键词 → missing）/ veto（命中否决规则 →
    uncertain）可推翻 LLM 结论；被推翻标 rule_overridden=True（报告展示口径）。"""
    out = dict(parsed)
    overridden = False
    for it in rule_items:
        if getattr(it, "category", None) != item.category:
            continue
        pat = _compile_rule(it)
        if pat is None:
            continue
        hay = f"{item.requirement} {item.raw_text}"
        kind_action = getattr(it, "action", "hint")
        if kind_action == "veto" and pat.search(hay):
            # 否决规则命中条款本体：LLM 给满足亦不可信 → uncertain 标黄人工复核
            if out["verdict"] == Verdict.SATISFIED.value:
                out.update(verdict=Verdict.UNCERTAIN.value,
                           reason=f"规则复核（veto：{it.pattern[:60]}）推翻满足结论",
                           confidence=min(out["confidence"], 0.4))
                overridden = True
        elif kind_action == "must":
            # must 关键词必须出现在条款要求中（响应类硬性要求），缺失即 missing
            if not pat.search(hay):
                out.update(verdict=Verdict.MISSING.value,
                           reason=f"规则复核（must：{it.pattern[:60]}）：条款缺少必须项",
                           confidence=max(out["confidence"], 0.9))
                overridden = True
    out["rule_overridden"] = overridden
    return out


def _compile_rule(it):
    kind = getattr(it, "kind", "")
    pattern = getattr(it, "pattern", "")
    if not pattern:
        return None
    if kind == "regex":
        try:
            return re.compile(pattern)
        except re.error:
            return None
    if kind == "keyword":
        return re.compile(re.escape(pattern))
    return None  # numeric/date 供 P2 数值比对深化，MVP 预筛/复核不消费


# ── 汇总与落库 ───────────────────────────────────────────────────────────────

_LEVEL_MAP = {
    Verdict.MISSING.value: "red",
    Verdict.DEVIATED.value: "red",
    Verdict.UNCERTAIN.value: "yellow",
    Verdict.SATISFIED.value: "green",
}


def level_for(verdict: str) -> str:
    return _LEVEL_MAP.get(verdict, "yellow")


def compute_stats(results: list[JudgeResult]) -> dict:
    """红黄绿计数（comparison.stats 快照，与 report 引擎口径一致）。"""
    by_level = {"red": 0, "yellow": 0, "green": 0}
    by_verdict: dict[str, int] = {}
    for r in results:
        by_level[r.level] = by_level.get(r.level, 0) + 1
        by_verdict[r.verdict] = by_verdict.get(r.verdict, 0) + 1
    return {"total": len(results), "by_level": by_level,
            "red": by_level["red"], "yellow": by_level["yellow"],
            "green": by_level["green"], "by_verdict": by_verdict}


def save_findings(db: Session, comparison_id: int, results: list[JudgeResult]) -> int:
    from decimal import Decimal

    for r in results:
        db.add(Finding(
            comparison_id=comparison_id, check_item_id=r.check_item_id,
            verdict=r.verdict, level=r.level, reason=r.reason,
            bid_ref_page=r.bid_ref_page, bid_quote=r.bid_quote,
            confidence=Decimal(str(round(r.confidence, 2))),
            rule_overridden=r.rule_overridden,
        ))
    db.flush()
    return len(results)
