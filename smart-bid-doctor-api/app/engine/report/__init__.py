"""报告渲染引擎占位——TODO(M1/D2–D3)，实现见 02-详细设计 §6。

推荐方案：
- 服务端 Jinja2 渲染 HTML（checklist / comparison 两套模板），产物落盘
  （reports.html_path，走 Storage 抽象）+ reports.report_data JSONB 快照（渲染源数据）；
- 红黄绿分级样式（RiskLevel），每条附原文引用与页码（溯源合规要求）；
- 导出 GET /reports/{rid}/export 直接回 HTML 文件，浏览器打印即 PDF（不做服务端 PDF）。

实现过程：
1. check_items / findings → report_data 快照（含 stats 汇总、生成时间、免责声明）；
2. Jinja2 渲染 → Storage.save 落 html_path → reports 落库；
3. export 端点 501 → 200（FileResponse），本端点只做归属校验 + 文件下发；
4. D3 阅后即焚：报告生成回调删除原件 + doc_blocks（purge 底座已有，此处业务触发，
   03 §5）；报告页脚标注报告出处与生成时间（04 §9）。
"""
