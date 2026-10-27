"""双文件对照引擎占位——TODO(M2)，实现见 02-详细设计 §4–§5。

推荐方案（混合检索 + GLM 判定 + 规则复核）：
- 检索：pg_trgm 文本相似 + pgvector 余弦（HNSW 索引，EMBED_DIM=1024）混合召回
  投标文件中与 check_item 对应的段落（RRF 融合排序，接口位已留）；
- 判定：GLM 重模型逐条 verdict（satisfied/deviated/missing/uncertain，见 Verdict
  枚举），不确定一律 uncertain 标黄，绝不输出「满足」（合规底线）；
- 规则复核：报价类数值比对（±阈值）、日期/签章关键词规则可推翻 LLM 结论
  （findings.rule_overridden=true）；
- 汇总：findings（level 红黄绿）→ comparison.stats → 对照报告。

实现过程：
1. 前置：bid 文档块向量就绪（embed handler）；每条 check_item 混合检索 top-k 投标段；
2. 逐条（或按类分批）构造判定 prompt，llm_calls 记账（purpose=judge）；
3. findings 落库 + stats 聚合（红/黄/绿计数）→ comparison.status=done → 建报告任务；
4. 规则复核层对 LLM 结论做二次裁决并标记 rule_overridden。

验收：对照判定与人工复核一致率 ≥85%（M2 门槛，README 里程碑表）。
"""
