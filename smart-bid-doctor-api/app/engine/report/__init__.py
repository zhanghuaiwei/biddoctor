"""报告渲染引擎（M1/D2–D3，02 §6）：report_data 快照 + Jinja2 HTML 落盘。

- build_checklist_data / build_comparison_data：纯函数，产出 02 §6.2 报告结构
  （stats 汇总 + 逐条原文页码溯源 + 免责声明），作为 reports.report_data 快照；
- render：Jinja2 服务端渲染（checklist/comparison 两套模板），产物写
  <upload_dir>/reports/<uuid>.html → reports.html_path；导出端点 FileResponse
  下发，浏览器打印即 PDF（不做服务端 PDF）；
- AIGC 标识合规（05 §9.2）：报告页眉/页脚与元数据显式标注「本报告由 AI 辅助生成」
  （生成时间/模型/版本），导出 HTML 含隐式水印 meta 字段。
"""

import datetime as dt
import os
import uuid as _uuid

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import get_settings

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

DISCLAIMER = (
    "本报告由 AI 辅助生成，仅作为「辅助人工复核」参考，不构成任何「保证不废标」"
    "承诺，不构成法律意见；每条结论附招标文件原文页码溯源，高危项须人工确认。"
)

_env: Environment | None = None


def _jinja_env() -> Environment:
    global _env
    if _env is None:
        _env = Environment(
            loader=FileSystemLoader(_TEMPLATE_DIR),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _env


def _meta(model: str) -> dict:
    now = dt.datetime.now(dt.UTC) + dt.timedelta(hours=8)  # 用户可见时间用北京时间
    return {
        "generated_at_bj": now.strftime("%Y-%m-%d %H:%M"),
        "model": model,
        "generator": "smart-bid-doctor",
        "ai_mark": "本报告由 AI 辅助生成",
    }


def build_checklist_data(project, document, items: list) -> dict:
    """check_items → checklist 报告快照（items 为空时仍生成完整结构）。"""
    by_category: dict[str, int] = {}
    for it in items:
        by_category[it.category] = by_category.get(it.category, 0) + 1
    return {
        "kind": "checklist",
        "project": {"id": project.id, "name": project.name, "industry": project.industry},
        "document": {"orig_name": document.orig_name, "total_pages": document.total_pages},
        "generated_at_bj": _meta("")["generated_at_bj"],
        "disclaimer": DISCLAIMER,
        "stats": {
            "total": len(items),
            "mandatory": sum(1 for i in items if i.is_mandatory),
            "by_category": by_category,
        },
        "items": [
            {
                "code": i.code, "category": i.category, "requirement": i.requirement,
                "raw_text": i.raw_text, "ref_page": i.ref_page,
                "is_mandatory": i.is_mandatory, "check_hint": i.check_hint,
            }
            for i in items
        ],
        "notes": [] if items else [
            "抽取引擎未产出条款（M1 抽取接入后自动出数），本报告仅含报告框架与免责声明。"
        ],
    }


def build_comparison_data(project, comparison, items: list, findings: list) -> dict:
    """findings → comparison 报告快照：红黄绿分级 + 逐条判定 + 证据页溯源。"""
    item_by_id = {i.id: i for i in items}
    by_level: dict[str, int] = {"red": 0, "yellow": 0, "green": 0}
    rows = []
    for f in findings:
        by_level[f.level] = by_level.get(f.level, 0) + 1
        item = item_by_id.get(f.check_item_id)
        rows.append({
            "code": item.code if item else None,
            "category": item.category if item else None,
            "requirement": item.requirement if item else None,
            "verdict": f.verdict, "level": f.level, "reason": f.reason,
            "bid_ref_page": f.bid_ref_page, "bid_quote": f.bid_quote,
            "rule_overridden": f.rule_overridden,
        })
    return {
        "kind": "comparison",
        "project": {"id": project.id, "name": project.name, "industry": project.industry},
        "comparison_id": comparison.id,
        "generated_at_bj": _meta("")["generated_at_bj"],
        "disclaimer": DISCLAIMER,
        "stats": {"total": len(findings), "by_level": by_level,
                  "red": by_level.get("red", 0), "yellow": by_level.get("yellow", 0),
                  "green": by_level.get("green", 0)},
        "items": rows,
    }


def render(kind: str, data: dict, model: str = "rule-based") -> str:
    """渲染 HTML（快照 data + AIGC 元数据注入）。"""
    env = _jinja_env()
    template = env.get_template(f"{kind}.html.j2")
    return template.render(**data, meta=_meta(model))


def save_html(html: str) -> str:
    """渲染产物落盘 → 返回 html_path（<upload_dir>/reports/<uuid>.html）。"""
    root = os.path.join(get_settings().upload_dir, "reports")
    os.makedirs(root, exist_ok=True)
    path = os.path.join(root, f"{_uuid.uuid4().hex}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path
