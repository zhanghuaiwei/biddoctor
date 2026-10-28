"""招标文件解析引擎（M1/B1–B3，02 §2）：PyMuPDF 主路径 + pdfplumber 表格兜底。

流程（纯函数，无 IO 副作用，落库由 handler 负责）：
1. fitz 打开校验（加密/损坏 → 专用错误，确定性失败不重试）；
2. 逐页 get_text("dict") 拆 block：字号阈值分 heading/text，维护 section 归属；
3. 扫描页检测：单页文本 < 字符阈值计扫描页，累计 is_scanned_ratio（OCR 预留，
   PaddleOCR 为可选安装层，见 pyproject 注释——未启用时扫描页仅计数告警）；
4. 表格页兜底：对候选表格页（行多且短）用 pdfplumber extract_tables 转 type=table；
5. 输出 (blocks, stats)：blocks 按 (page, seq) 序，stats 含 total_pages/scanned_ratio。
"""

import datetime as dt

import fitz  # PyMuPDF

from app.core.errors import AppError

# heading 判定：span 字号 ≥ 页内中位字号 × 比例，且 ≥ 绝对下限
_HEADING_RATIO = 1.35
_HEADING_MIN_SIZE = 13.0
# 扫描页判定：单页可提取字符数低于该值
_SCANNED_CHARS = 24
# 表格页候选：文本行数 ≥ 该值且平均行长 ≤ 该值（窄而多行 ≈ 表格形态）
_TABLE_MIN_LINES = 6
_TABLE_MAX_LINE_WIDTH = 36
_TABLE_PAGE_BUDGET = 60  # pdfplumber 较慢，单文档最多兜底的表格页数


class ParsedBlock:
    """doc_blocks 行载体（与 models.DocBlock 字段一一对应）。"""

    __slots__ = ("page", "seq", "type", "text", "section")

    def __init__(self, page: int, seq: int, type_: str, text: str, section: str | None):
        self.page = page
        self.seq = seq
        self.type = type_
        self.text = text
        self.section = section


def parse_pdf(path: str) -> tuple[list[ParsedBlock], dict]:
    """解析 PDF → (blocks, stats)。加密/损坏抛 PARSE_ENCRYPTED / PARSE_CORRUPT。"""
    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise AppError(400, "PARSE_CORRUPT", "PDF 无法解析，文件可能已损坏") from exc
    try:
        if doc.needs_pass:
            raise AppError(400, "PARSE_ENCRYPTED", "文件已加密，请上传解密后的 PDF")
        total_pages = doc.page_count
        blocks: list[ParsedBlock] = []
        scanned_pages = 0
        seq = 0
        table_candidates: list[int] = []

        # 两遍扫描：先收齐全页 span，以「众数字号 = 正文字号」（正文行占绝对多数）
        # 计算标题阈值——中位数会被标题占比高的文档拉偏
        pages_spans: list[list[tuple[float, str]]] = []
        all_sizes: list[float] = []
        for pno in range(total_pages):
            spans = _page_spans(doc[pno])
            pages_spans.append(spans)
            all_sizes.extend(s for s, _ in spans)
        body_size = _body_size(all_sizes)
        threshold = max(_HEADING_MIN_SIZE, body_size * _HEADING_RATIO)

        for pno, spans in enumerate(pages_spans):
            chars = sum(len(t) for _, t in spans)
            if chars < _SCANNED_CHARS:
                scanned_pages += 1
                continue
            page_blocks, page_lines, avg_line = _classify(spans, threshold)
            for b in page_blocks:
                blocks.append(ParsedBlock(pno + 1, seq, b[0], b[1], b[2]))
                seq += 1
            if page_lines >= _TABLE_MIN_LINES and avg_line <= _TABLE_MAX_LINE_WIDTH:
                table_candidates.append(pno)

        # 表格页兜底（有预算上限，防大文档拖垮 worker）
        for pno in table_candidates[:_TABLE_PAGE_BUDGET]:
            for text in _page_tables(path, pno):
                blocks.append(ParsedBlock(pno + 1, seq, "table", text, None))

        blocks.sort(key=lambda b: (b.page, b.seq))
        for i, b in enumerate(blocks):  # 表格兜底块后补，seq 全局重排保证单调
            b.seq = i
        return blocks, {
            "total_pages": total_pages,
            "scanned_pages": scanned_pages,
            "is_scanned_ratio": round(scanned_pages / total_pages, 3) if total_pages else 0,
            "blocks": len(blocks),
            "parsed_at": dt.datetime.now(dt.UTC).isoformat(),
        }
    finally:
        doc.close()


def _body_size(all_sizes: list[float]) -> float:
    """正文字号 = 最高频字号（同频取更小者——正文通常小于标题）。"""
    if not all_sizes:
        return _HEADING_MIN_SIZE
    from collections import Counter

    counts = Counter(round(s) for s in all_sizes)
    return float(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0])


def _page_spans(page) -> list[tuple[float, str]]:
    """单页 → [(字号, 文本)]，拼接 block 内 span 为行文本。"""
    raw = page.get_text("dict")
    spans_out: list[tuple[float, str]] = []
    for block in raw.get("blocks", []):
        if block.get("type") != 0:  # 0=text，图片块跳过
            continue
        lines: list[list[tuple[float, str]]] = []
        for line in block.get("lines", []):
            spans = [
                (float(span.get("size", 0)), span.get("text", "").strip())
                for span in line.get("spans", [])
            ]
            spans = [(s, t) for s, t in spans if t]
            if spans:
                lines.append(spans)
        # 同一 block 的行合并为一段（字号取段内最大）
        for spans in lines:
            text = " ".join(t for _, t in spans).strip()
            if text:
                spans_out.append((max(s for s, _ in spans), text))
    return spans_out


def _classify(spans, threshold: float) -> tuple[list[tuple[str, str, str | None]], int, float]:
    """span 列表 → ([(type, text, section)], lines, avg_line_len)，heading 归属追踪。"""
    out: list[tuple[str, str, str | None]] = []
    section: str | None = None
    lines = 0
    line_lens: list[int] = []
    for size, text in spans:
        lines += text.count("\n") + 1
        line_lens.extend(len(seg) for seg in text.split("\n"))
        if size >= threshold:
            section = text[:256]  # heading 作为后续 block 的 section 归属
            out.append(("heading", text, None))
        else:
            out.append(("text", text, section))
    avg_line = (sum(line_lens) / len(line_lens)) if line_lens else 0.0
    return out, lines, avg_line


def _page_tables(path: str, pno: int) -> list[str]:
    """pdfplumber 表格兜底：单页 extract_tables → 管道分隔文本。"""
    import pdfplumber

    out: list[str] = []
    try:
        with pdfplumber.open(path) as pdf:
            if pno >= len(pdf.pages):
                return out
            for table in pdf.pages[pno].extract_tables():
                rows = [
                    [(_c or "").strip().replace("\n", " ") for _c in row]
                    for row in table
                    if row
                ]
                if rows:
                    out.append("\n".join(" | ".join(r) for r in rows))
    except Exception:  # 表格兜底失败不阻断主解析（文本块已可用）
        pass
    return out
