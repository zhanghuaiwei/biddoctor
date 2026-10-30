"""废标条款抽取引擎（M1/C，02 §3）：规则预筛 + GLM 结构化抽取 + 合并去重。

职责切分（Agent 能力 TODO 边界，AGENTS.md 硬性禁区 1）：
- 本模块全部实装（预筛/批次/Prompt 组装/坏输出解析/归一去重/落库）；
- 唯一 LLM 依赖点 = provider.chat()（app/llm/zhipu.py 桩），handler 编排见
  worker/handlers/extract.py——桩状态（NOT_IMPLEMENTED）下任务转 need_review，
  接入后即插即用。

流程：
1. C1 规则预筛 prescreen：内置默认规则 ∪ 规则库 active hint 条目
   （rule_svc.active_items，regex/keyword 两类），命中即候选——宁多勿漏
   （C1 验收：候选召回 ≥98%，make eval --prescreen-only 可验证）；
2. C2 GLM 重模型结构化抽取：build_batches（~20 段/批控上下文）→ build_messages
   （段落带 [P页码] 标注便于溯源）→ JSON Schema 约束输出；坏输出 parse_items
   抛 ItemFormatError 由 handler 重试（≤2 次，轻模型兜底）；
3. C3 合并去重 normalize_and_dedup：category 归一 + 原文（归一化）去重 + code
   分配（QUAL/COMP/STAR/PRICE/FMT-三位序号）→ save_items 落 check_items
   （(project_id, code) 唯一防重）。
"""

import json
import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.enums import CheckCategory
from app.models import CheckItem

# 每批候选段数（控上下文窗口；02 §3）
BATCH_SIZE = 20

# code 前缀（check_items.code，STAR-007 风格）
_CODE_PREFIX = {
    CheckCategory.QUALIFICATION: "QUAL",
    CheckCategory.COMPLIANCE: "COMP",
    CheckCategory.STAR: "STAR",
    CheckCategory.PRICE: "PRICE",
    CheckCategory.FORMAT_SEAL: "FMT",
}

# 内置默认预筛规则（规则库无 active 条目时的兜底；宁多勿漏）：
# (category, regex)。规则库 hint 条目与本表取并集。
DEFAULT_RULES: tuple[tuple[str, str], ...] = (
    ("star", r"★"),
    ("qualification", r"资格|具备|资质|营业执照|法人|授权|业绩|认证|证书"),
    ("compliance", r"不得|禁止|拒绝|否决|废标|无效|不予|视为|按废标"),
    ("price", r"报价|价格|算术|大小写|单价|总价|预算|最高限价"),
    ("format_seal", r"签章|盖章|签字|密封|骑缝|装订|份数|正本|副本"),
)

# 强制性判定词（is_mandatory 推断，star 类恒为强制）
_MANDATORY_WORDS = re.compile(r"不得|禁止|拒绝|否决|废标|无效|应|必须|应当")

# GLM 输出 JSON 契约（02 §3.1 五类条款）
OUTPUT_CONTRACT = """请从以下招标文件段落中抽取「废标相关条款」，输出 JSON：
{"items": [{"category": "qualification|compliance|star|price|format_seal",
  "requirement": "条款要求的一句话概述",
  "raw_text": "原文逐字摘录（不得改写）",
  "ref_page": 段落标注的页码数字,
  "is_mandatory": true|false,
  "confidence": 0到1的小数}]}
规则：1) raw_text 必须逐字取自给定段落；2) category 只能取上述五值；
3) 与废标无关的段落不要输出；4) 无任何条款时输出 {"items": []}。"""


class ItemFormatError(Exception):
    """GLM 输出不符合 JSON 契约（handler 捕获后重试，轻模型兜底）。"""


@dataclass
class ExtractedItem:
    """抽取候选条目（normalize 前的原始形态，字段与 GLM 输出契约对应）。"""

    category: str
    requirement: str
    raw_text: str
    ref_page: int
    is_mandatory: bool
    confidence: float = 0.8
    code: str = ""  # normalize 阶段分配


@dataclass
class PrescreenStats:
    """预筛统计（handler 记录到 task.stage / 评测脚本复用）。"""

    total_blocks: int = 0
    candidates: int = 0
    rules_used: int = 0
    hit_by: dict = field(default_factory=dict)  # rule_id/内置规则名 → 命中次数


def _compiled(rules: tuple[tuple[str, str], ...]) -> list[tuple[str, re.Pattern]]:
    out = []
    for cat, pat in rules:
        try:
            out.append((cat, re.compile(pat)))
        except re.error:  # 规则库人工录入的坏正则：跳过不炸管线
            continue
    return out


def default_compiled() -> list[tuple[str, re.Pattern]]:
    return _compiled(DEFAULT_RULES)


def prescreen(blocks: list, rule_items: list = ()) -> tuple[list, PrescreenStats]:
    """C1 规则预筛：内置默认规则 ∪ 规则库 hint 条目，任一命中即候选。

    rule_items 为 rule_svc.active_items() 的 RuleItem（kind=regex 用 pattern 编译，
    kind=keyword 按子串包含；其他 kind（numeric/date）预筛阶段忽略，供 M2 判定复核）。
    返回 (候选 blocks（按 page,seq 序）, 统计)。
    """
    compiled = default_compiled()
    stats = PrescreenStats(total_blocks=len(blocks))
    for it in rule_items:
        if getattr(it, "action", "hint") not in ("hint", None):
            continue  # must/veto 是判定复核语义，不参与预筛
        if getattr(it, "kind", "") == "regex":
            compiled.extend(_compiled([(getattr(it, "category", "compliance"), it.pattern)]))
        elif getattr(it, "kind", "") == "keyword":
            compiled.append((getattr(it, "category", "compliance"), re.compile(re.escape(it.pattern))))
    stats.rules_used = len(compiled)

    seen: set[int] = set()
    cands: list = []
    for b in blocks:
        text = b.text or ""
        if not text.strip():
            continue
        for _cat, pat in compiled:
            if pat.search(text):
                if id(b) not in seen:
                    seen.add(id(b))
                    cands.append(b)
                stats.hit_by[pat.pattern] = stats.hit_by.get(pat.pattern, 0) + 1
                break  # 一段只记一次候选（类别由 GLM 判）
    stats.candidates = len(cands)
    return cands, stats


def build_batches(cands: list, size: int = BATCH_SIZE) -> list[list]:
    return [cands[i:i + size] for i in range(0, len(cands), size)]


def render_blocks(batch: list) -> str:
    """候选段落渲染为带页码标注的文本（GLM 溯源锚点）。"""
    lines = []
    for b in batch:
        tag = f"[P{b.page}]" + (f"[{b.section}] " if getattr(b, "section", None) else " ")
        lines.append(f"{tag}{b.text}")
    return "\n".join(lines)


def build_user_prompt(batch: list, template: str | None = None) -> str:
    """user 消息：管理端 active 模板（占位符 {blocks_text}）优先，坏模板回退内置契约。"""
    body = render_blocks(batch)
    if template and "{blocks_text}" in template:
        try:
            return template.format(blocks_text=body)
        except (KeyError, IndexError, ValueError):
            pass
    return f"{OUTPUT_CONTRACT}\n\n招标文件段落：\n{body}"


def parse_items(content: str) -> list[ExtractedItem]:
    """GLM JSON 输出 → ExtractedItem 列表。

    整体解析失败 / items 非列表 → ItemFormatError（可重试）；
    单条字段非法（category 白名单外/raw_text 空/ref_page 非法）→ 跳过该条不整批作废。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ItemFormatError(f"JSON 解析失败: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ItemFormatError("输出结构不符：缺少 items 列表")
    valid_cats = {c.value for c in CheckCategory}
    out: list[ExtractedItem] = []
    for raw in data["items"]:
        if not isinstance(raw, dict):
            continue
        cat = raw.get("category")
        text = (raw.get("raw_text") or "").strip()
        if cat not in valid_cats or not text:
            continue
        try:
            page = int(raw.get("ref_page") or 0)
        except (TypeError, ValueError):
            continue
        if page <= 0:
            continue
        conf = raw.get("confidence")
        try:
            conf = min(1.0, max(0.0, float(conf))) if conf is not None else 0.8
        except (TypeError, ValueError):
            conf = 0.8
        out.append(ExtractedItem(
            category=cat, requirement=(raw.get("requirement") or text)[:500],
            raw_text=text[:2000], ref_page=page,
            is_mandatory=bool(raw.get("is_mandatory")) or cat == CheckCategory.STAR,
            confidence=conf,
        ))
    return out


def _norm_text(text: str) -> str:
    """归一化：NFKC 全半角折叠 + 去所有空白（原文去重口径）。"""
    return "".join(unicodedata.normalize("NFKC", text).split())


def normalize_and_dedup(raw: list[ExtractedItem]) -> list[ExtractedItem]:
    """C3 归一去重：同 category 下原文归一化相同视为重复（保留 confidence 高者）；
    按 (category, ref_page) 排序后逐类分配 code（QUAL-001…）。"""
    by_cat: dict[str, dict[str, ExtractedItem]] = {}
    for it in raw:
        bucket = by_cat.setdefault(it.category, {})
        key = _norm_text(it.raw_text)
        prev = bucket.get(key)
        if prev is None or it.confidence > prev.confidence:
            bucket[key] = it

    merged: list[ExtractedItem] = []
    for cat in sorted(by_cat):
        prefix = _CODE_PREFIX.get(cat, "CHK")
        items = sorted(by_cat[cat].values(), key=lambda i: (i.ref_page, i.requirement))
        for idx, it in enumerate(items, start=1):
            it.code = f"{prefix}-{idx:03d}"
            if cat == CheckCategory.COMPLIANCE and not it.is_mandatory:
                it.is_mandatory = bool(_MANDATORY_WORDS.search(it.requirement + it.raw_text))
            merged.append(it)
    return merged


def save_items(db: Session, project_id: int, document_id: int,
               items: list[ExtractedItem]) -> int:
    """落 check_items；(project_id, code) 冲突（重跑/并发）跳过不炸。返回新增数。"""
    existing = {
        c for (c,) in db.query(CheckItem.code).filter(CheckItem.project_id == project_id).all()
    }
    added = 0
    for it in items:
        if it.code in existing:
            continue
        db.add(CheckItem(
            project_id=project_id, document_id=document_id, code=it.code,
            category=it.category, requirement=it.requirement, raw_text=it.raw_text,
            ref_page=it.ref_page, is_mandatory=it.is_mandatory,
            confidence=it.confidence,
        ))
        existing.add(it.code)
        added += 1
    db.flush()
    return added
