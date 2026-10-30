"""对照引擎单测（M2/E，02 §4–§5）——无需数据库。

覆盖：verdict 解析守卫（白名单外/坏 JSON 一律 uncertain，绝不输出「满足」）、
红黄绿映射、规则复核（veto 推翻满足 / must 缺失判 missing / hint 不干预）、
RRF 融合、stats 聚合。混合检索 SQL 部分由集成测试覆盖（需 pg_trgm/pgvector）。
"""

from types import SimpleNamespace

from app.engine import comparator

# ── verdict 解析守卫 ─────────────────────────────────────────────────────────

def test_parse_verdict_valid():
    content = '{"verdict": "missing", "reason": "无对应证据", "bid_ref_page": null, ' \
              '"bid_quote": null, "confidence": 0.8}'
    out = comparator.parse_verdict(content)
    assert out["verdict"] == "missing" and out["confidence"] == 0.8


def test_parse_verdict_bad_json_is_uncertain():
    out = comparator.parse_verdict("满足！绝对满足！")  # LLM 幻觉非 JSON
    assert out["verdict"] == "uncertain"
    assert out["confidence"] <= 0.5


def test_parse_verdict_invalid_value_is_uncertain():
    """verdict 白名单外一律 uncertain——「满足」底线在此兜底。"""
    content = '{"verdict": "满足", "reason": "看起来不错"}'
    out = comparator.parse_verdict(content)
    assert out["verdict"] == "uncertain"


def test_parse_verdict_page_and_confidence_clamped():
    content = '{"verdict": "deviated", "reason": "r", "bid_ref_page": -3, "confidence": 9}'
    out = comparator.parse_verdict(content)
    assert out["bid_ref_page"] is None and out["confidence"] == 1.0


# ── 红黄绿映射 ───────────────────────────────────────────────────────────────

def test_level_mapping():
    assert comparator.level_for("missing") == "red"
    assert comparator.level_for("deviated") == "red"
    assert comparator.level_for("uncertain") == "yellow"
    assert comparator.level_for("satisfied") == "green"
    assert comparator.level_for("unknown") == "yellow"  # 未知值保守标黄


# ── 规则复核（02 §4.1）───────────────────────────────────────────────────────

def make_item(category="price", raw="报价不超过 500 万", req="报价要求"):
    return SimpleNamespace(category=category, raw_text=raw, requirement=req,
                           code="PRICE-001", ref_page=2)


def make_rule(kind, action, pattern, category="price"):
    return SimpleNamespace(kind=kind, action=action, pattern=pattern, category=category)


def test_rule_review_veto_overrides_satisfied():
    item = make_item()
    rules = [make_rule("keyword", "veto", "低于成本")]
    parsed = {"verdict": "satisfied", "reason": "满足", "bid_ref_page": 1,
              "bid_quote": "q", "confidence": 0.9, "rule_overridden": False}
    out = comparator.rule_review(item, parsed, rules)  # 条款原文含 veto 词？不——veto 应命中
    # 条款文本不含 veto 词 → 不推翻
    assert out["verdict"] == "satisfied" and not out["rule_overridden"]

    item2 = make_item(raw="报价不得低于成本价")
    out2 = comparator.rule_review(item2, parsed, rules)
    assert out2["verdict"] == "uncertain"  # veto 命中：满足结论被推翻标黄
    assert out2["rule_overridden"] is True


def test_rule_review_must_missing():
    item = make_item()
    rules = [make_rule("keyword", "must", "法人授权书")]
    parsed = {"verdict": "satisfied", "reason": "ok", "bid_ref_page": None,
              "bid_quote": None, "confidence": 0.9, "rule_overridden": False}
    out = comparator.rule_review(item, parsed, rules)
    assert out["verdict"] == "missing" and out["rule_overridden"] is True


def test_rule_review_hint_no_touch():
    item = make_item()
    rules = [make_rule("regex", "hint", "报价")]
    parsed = {"verdict": "satisfied", "reason": "ok", "bid_ref_page": None,
              "bid_quote": None, "confidence": 0.9, "rule_overridden": False}
    out = comparator.rule_review(item, parsed, rules)
    assert out == parsed


def test_rule_review_bad_regex_ignored():
    item = make_item()
    rules = [make_rule("regex", "veto", "([unclosed")]
    parsed = {"verdict": "satisfied", "reason": "ok", "bid_ref_page": None,
              "bid_quote": None, "confidence": 0.9, "rule_overridden": False}
    out = comparator.rule_review(item, parsed, rules)
    assert out["verdict"] == "satisfied"


# ── RRF 与 stats ─────────────────────────────────────────────────────────────

def test_rrf_score():
    # 单路 rank 1：1/(60+1)；双路 [1, 2]：1/61 + 1/62
    assert abs(comparator._rrf_score([1]) - 1 / 61) < 1e-9
    assert abs(comparator._rrf_score([1, 2]) - (1 / 61 + 1 / 62)) < 1e-9


def test_compute_stats():
    rows = [
        comparator.JudgeResult(1, "missing", "red", "r"),
        comparator.JudgeResult(2, "deviated", "red", "r"),
        comparator.JudgeResult(3, "uncertain", "yellow", "r"),
        comparator.JudgeResult(4, "satisfied", "green", "r"),
    ]
    stats = comparator.compute_stats(rows)
    assert stats["total"] == 4
    assert stats["by_level"] == {"red": 2, "yellow": 1, "green": 1}
    assert stats["by_verdict"]["missing"] == 1


def test_judge_messages_contain_item_and_evidence():
    item = make_item()
    hits = [comparator.SearchHit(block_id=9, page=4, text="投标函报价 500 万", score=0.03)]
    msgs = comparator.build_judge_messages(item, hits)
    assert msgs[0]["role"] == "system"
    user = msgs[-1]["content"]
    assert "PRICE-001" in user and "[P4]" in user and "投标函报价 500 万" in user
