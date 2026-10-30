"""抽取引擎单测（M1/C1/C3，02 §3）——无需数据库。

覆盖：规则预筛（内置规则/规则库 hint 注入/must-veto 不参与）、JSON 输出解析
（契约校验/坏输出/单条跳过）、归一去重与 code 分配、批次切分、Prompt 组装。
"""

from types import SimpleNamespace

import pytest

from app.engine import extractor
from app.engine.extractor import ItemFormatError


def block(text, page=1, seq=1, type_="text", section=None):
    return SimpleNamespace(page=page, seq=seq, type=type_, text=text, section=section)


# ── C1 预筛 ─────────────────────────────────────────────────────────────────

def test_prescreen_default_rules_hit():
    blocks = [
        block("★1. 投标货物必须原厂全新。", page=1, seq=1),
        block("投标人不得存在下列情形之一。", page=1, seq=2),
        block("投标文件应当密封并加盖公章。", page=1, seq=3),
        block("投标报价不得超过最高限价。", page=2, seq=1),
        block("本节为一般性说明内容，无特殊要求。", page=2, seq=2),
    ]
    cands, stats = extractor.prescreen(blocks, ())
    texts = [c.text for c in cands]
    assert blocks[0].text in texts      # star
    assert blocks[1].text in texts      # 不得
    assert blocks[2].text in texts      # 签章/密封
    assert blocks[3].text in texts      # 报价/限价
    assert blocks[4].text not in texts  # 无关段落不命中
    assert stats.total_blocks == 5 and stats.candidates == 4


def test_prescreen_rule_hint_injection():
    rule = SimpleNamespace(kind="keyword", pattern="独角兽", category="star",
                           action="hint")
    blocks = [block("本项目接受独角兽企业投标。")]
    cands, stats = extractor.prescreen(blocks, [rule])
    assert len(cands) == 1
    assert stats.rules_used > len(extractor.DEFAULT_RULES)


def test_prescreen_ignores_must_veto_rules():
    """must/veto 是判定复核语义，不参与预筛（02 §4.1）。"""
    rules = [SimpleNamespace(kind="regex", pattern="xyz", category="compliance",
                             action="veto")]
    blocks = [block("普通文本 xyz 不会因 veto 规则成为候选。")]
    cands, _ = extractor.prescreen(blocks, rules)
    assert cands == []


def test_prescreen_bad_regex_skipped():
    rules = [SimpleNamespace(kind="regex", pattern="([unclosed", category="compliance",
                             action="hint"),
             SimpleNamespace(kind="regex", pattern="正常规则", category="compliance",
                             action="hint")]
    blocks = [block("含正常规则的段落")]
    cands, _ = extractor.prescreen(blocks, rules)
    assert len(cands) == 1  # 坏正则跳过不炸管线


def test_build_batches():
    cands = [block(f"t{i}", seq=i) for i in range(45)]
    batches = extractor.build_batches(cands, size=20)
    assert [len(b) for b in batches] == [20, 20, 5]


# ── C2 输出解析 ──────────────────────────────────────────────────────────────

def test_parse_items_valid():
    content = '{"items": [{"category": "star", "requirement": "原厂全新", ' \
              '"raw_text": "★1. 必须原厂全新", "ref_page": 3, ' \
              '"is_mandatory": true, "confidence": 0.9}]}'
    items = extractor.parse_items(content)
    assert len(items) == 1
    assert items[0].category == "star" and items[0].ref_page == 3
    assert items[0].is_mandatory is True and items[0].confidence == 0.9


def test_parse_items_bad_json_raises():
    with pytest.raises(ItemFormatError):
        extractor.parse_items("这不是 JSON")
    with pytest.raises(ItemFormatError):
        extractor.parse_items('{"no_items": 1}')


def test_parse_items_skips_invalid_entries():
    content = '{"items": [' \
              '{"category": "unknown", "raw_text": "x", "ref_page": 1},' \
              '{"category": "price", "raw_text": "", "ref_page": 1},' \
              '{"category": "price", "raw_text": "报价条款", "ref_page": 0},' \
              '{"category": "price", "raw_text": "有效条款", "ref_page": 2}]}'
    items = extractor.parse_items(content)
    assert len(items) == 1 and items[0].raw_text == "有效条款"


def test_parse_items_star_forces_mandatory():
    content = '{"items": [{"category": "star", "raw_text": "★条款", "ref_page": 1, ' \
              '"is_mandatory": false}]}'
    assert extractor.parse_items(content)[0].is_mandatory is True


# ── C3 归一去重与 code ───────────────────────────────────────────────────────

def test_normalize_dedup_and_codes():
    raw = [
        extractor.ExtractedItem("qualification", "法人资格", "投标人须具备独立法人资格", 1, True, 0.9),
        extractor.ExtractedItem("qualification", "法人资格重复", "投标人须具备独立法人资格", 1, True, 0.7),
        extractor.ExtractedItem("star", "星号条款", "★1. 原厂全新", 2, True, 0.95),
        extractor.ExtractedItem("star", "星号条款二", "★2. 三年内无重大违法", 3, True, 0.95),
        extractor.ExtractedItem("compliance", "不得转包", "投标不得转包", 2, False, 0.8),
    ]
    items = extractor.normalize_and_dedup(raw)
    codes = [i.code for i in items]
    assert codes == ["COMP-001", "QUAL-001", "STAR-001", "STAR-002"]
    qual = [i for i in items if i.category == "qualification"]
    assert len(qual) == 1 and qual[0].confidence == 0.9  # 重复保留 confidence 高者
    comp = [i for i in items if i.category == "compliance"]
    assert comp[0].is_mandatory is True  # "不得" 强制词推断


def test_normalize_fullwidth_dup_collapsed():
    """全半角/空白差异视为同一条（归一化去重口径）。"""
    raw = [
        extractor.ExtractedItem("star", "a", "★1 必须原厂", 1, True, 0.8),
        extractor.ExtractedItem("star", "b", "★１  必须原厂 ", 1, True, 0.9),
    ]
    assert len(extractor.normalize_and_dedup(raw)) == 1


# ── Prompt 组装 ──────────────────────────────────────────────────────────────

def test_build_user_prompt_default_contract():
    user = extractor.build_user_prompt([block("★条款内容", page=7)])
    assert "[P7]" in user
    assert "★条款内容" in user
    assert '{"items":' in user  # 内置 JSON 契约


def test_build_user_prompt_admin_template():
    tpl = "自定义契约 {blocks_text} 结束"
    user = extractor.build_user_prompt([block("内容")], template=tpl)
    assert user.startswith("自定义契约") and "内容" in user


def test_build_user_prompt_bad_template_falls_back():
    tpl = "缺占位符模板 {unknown_var}"
    user = extractor.build_user_prompt([block("内容")], template=tpl)
    assert '{"items":' in user  # 坏模板回退内置契约
