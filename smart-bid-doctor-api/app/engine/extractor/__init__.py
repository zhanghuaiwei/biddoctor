"""废标条款抽取引擎占位——TODO(M1/C1–C3)，MVP 核心难点，实现见 02-详细设计 §3。

推荐方案（规则预筛 + GLM 结构化抽取 + 合并去重，压 LLM 成本）：
- C1 规则预筛：关键词/正则（★、资格、具备、不得、拒绝、否决、签章、盖章、密封、
  报价/算术错误…）圈定候选段落，宁多勿漏（候选召回 ≥98%）；
- C2 GLM 重模型（llm_model_heavy）结构化抽取五类条款（qualification/compliance/
  star/price/format_seal），JSON Schema 约束输出（编号 code + 原文 quote + 页码 page
  + is_mandatory），坏输出自动重试（≤2 次，轻模型兜底 purpose=retry）；
- C3 合并去重（code 归一 + 原文相似度）→ check_items 落库（(project_id, code) 唯一
  约束防重）→ checklist handler 收尾状态迁移。

实现过程：
1. 预筛器产出候选 doc_blocks 集合，按页序拼 prompt（段落带页码标注，便于溯源）；
2. 分批调用（每批 ~20 段控上下文），每次调用记 llm_calls（purpose=extract，成本记账）；
3. JSON 解析失败 → 调整 temperature 重试 → 仍失败标 need_review，不静默丢弃；
4. 落库后 project.status=checklist_ready 并建 checklist 任务（任务链 02 §8）；
5. make eval 金标集评测：抽取召回 ≥90%（M1 门槛，02 §10）。
"""
