"""招标文件解析引擎占位——TODO(M1/B1–B4)，实现见 02-详细设计 §2。

推荐方案：
- PyMuPDF(fitz) 主路径逐页提取文本块（速度优先），pdfplumber 兜底表格页；
- 扫描页检测：单页字符数低于阈值计扫描页，累计 is_scanned_ratio；
  ENABLE_OCR 开启时 PaddleOCR 3.x 兜底（Dockerfile 独立安装层，worker 内存 <3G）；
- 输出落 doc_blocks（page/seq/type=heading|text|table/text/section），同步更新
  documents.total_pages / is_scanned_ratio / parse_status。

实现过程：
1. fitz 逐页 get_text("dict") 拆 block，按字号阈值分 heading/text；
2. 表格页用 pdfplumber extract_tables 转文本，type=table，保持页码坐标；
3. 批量 INSERT doc_blocks（分批 ~500 行）后更新文档状态机 → done；
4. 加密 → PARSE_ENCRYPTED、损坏 → PARSE_CORRUPT 显式 _fail（确定性失败不重试，B3）；
5. 金标集（20 份真实标书标注）+ make eval 评测脚本量化抽取召回（B4，02 §10）。

验收：文本 PDF 解析成功率 >95%；扫描页可出文本。
"""
