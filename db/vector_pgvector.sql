-- =============================================================================
-- smart-bid-doctor 向量数据库全量 DDL（vector domain · pgvector）
-- 版本 v2.0（2026-10-27）· 设计交付物（全量功能产品化版，配套 01–05 设计文档）
-- DBMS: PostgreSQL 16 + pgvector 扩展 · 编码 UTF8
--
-- 定位与优先级
--   1) 架构决策（01·D4）：向量检索使用同实例 PostgreSQL + pgvector 扩展，
--      不引入独立向量库（ES/Milvus/Faiss 等，AGENTS.md 硬性禁区）——本文件即
--      "向量数据库"的全部内容：扩展 + 向量域核心表 doc_blocks + 检索索引 + 维护策略；
--   2) doc_blocks 外键引用 business 域 documents 表——务必先执行
--      db/business_postgresql.sql，再执行本文件；
--   3) [P0·已实现]：doc_blocks 已随 alembic 0001 迁移实装（app/models/document.py::DocBlock），
--      本文件与其逐列对齐；EMBED_DIM 改动必须同步 app/models/base.py、alembic 迁移
--      与本文件三处（03 §2.4）。
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 0. 扩展初始化
--    vector : 向量列与 HNSW 索引（镜像 pgvector/pgvector:pg16 自带）
--    pg_trgm: 关键词粗筛的 trigram 索引（混合检索关键词分）
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;


-- -----------------------------------------------------------------------------
-- 1. doc_blocks —— 解析块（向量域核心表，检索数据源，最大表）
--    [P0·已实现]（app/models/document.py::DocBlock）
--
--    职责：M1 解析引擎产物落库（页码/顺序/类型/文本/章节路径）；
--    M2 对照引擎的混合检索数据源——向量余弦（语义）+ pg_trgm（关键词）双通道，
--    RRF/加权融合后取 top-k（02 §5.2）。
-- -----------------------------------------------------------------------------
CREATE TABLE doc_blocks (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page        INT NOT NULL,                     -- 1-based 页码（报告溯源用）
    seq         INT NOT NULL,                     -- 页内顺序
    type        VARCHAR(8) NOT NULL,              -- heading | text | table
    text        TEXT NOT NULL,                    -- 表格序列化为 Markdown 管道表
    section     VARCHAR(256),                     -- 重建的章节路径，如 "第三章·技术规格"
    embedding   VECTOR(1024),                     -- 智谱 embedding-3 dimensions=1024
                -- 该 API 仅 256/512/1024/2048 档（无 1536）；取 1024 与备选 BGE-M3
                -- 对齐，Provider 切换不改 DDL；EMBED_DIM 为配置常量
                -- （app/models/base.py），DDL 与 API 参数必须一致
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 顺序读索引：按文档取块（解析落库、报告溯源）
CREATE INDEX idx_blocks_doc ON doc_blocks(document_id, page, seq);

-- HNSW 而非 ivfflat：ivfflat 需先灌数据再建索引（空表建索引是经典坑），
-- HNSW 可随时建且召回更好；单机数据量 <100 万块足够（04 §4 扩容触发线 500 万行）
CREATE INDEX idx_blocks_vec ON doc_blocks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- 关键词粗筛：trigram GIN 索引（中文短词召回可接受；M2 评测后决定是否上 zhparser）
CREATE INDEX idx_blocks_text_trgm ON doc_blocks USING gin (text gin_trgm_ops);


-- -----------------------------------------------------------------------------
-- 2. 混合检索范式（对照引擎查询模板，02 §5.2）
-- -----------------------------------------------------------------------------
-- 向量粗排 24 → 混合分（0.6·向量 + 0.4·关键词）取 top-5 候选块：
--
--     SELECT id, page, text,
--            0.6 * (1 - (embedding <=> :qvec)) + 0.4 * keyword_score(text, :terms) AS score
--     FROM doc_blocks
--     WHERE document_id = :bid_doc_id
--     ORDER BY embedding <=> :qvec
--     LIMIT 24;
--
-- 关键词分：M0-P1 先用「ILIKE 命中数/词数」简化版（走 idx_blocks_text_trgm），
-- M2 评测决定是否引入 zhparser 中文分词 + ts_rank。


-- -----------------------------------------------------------------------------
-- 3. 容量与维护
-- -----------------------------------------------------------------------------
-- 行数估算：300 页 ≈ 3,000–6,000 块/文档；单文档含向量约 30–60MB。
-- 生命周期（03 §5）：与项目同周期级联删（DELETE ... CASCADE）；
--   "阅后即焚"= 报告生成后即删 doc_blocks（保留 reports，仅引用页码）。
--
-- 批量写入：解析引擎分批 INSERT（~500 行/批），单事务过大将拖长文档状态翻转。
--
-- 索引维护：
--   * 数据恢复后执行 ANALYZE doc_blocks（HNSW/GIN 索引随 pg_dump 恢复，无需重建）；
--   * 大批量删除（purge/阅后即焚）后视膨胀情况 REINDEX（GIN 索引膨胀优先关注）；
--   * HNSW 参数：m=16 / ef_construction=64 为召回-写入平衡的通用起点；
--     查询端 ef_search 默认 40，召回不足时按评测调优（不落 DDL，会话级 SET hnsw.ef_search）。
--
-- 备份与恢复（03 §6）：向量数据随库 pg_dump -Fc 一并转储；
-- 独立向量库（Milvus 等）不在本产品架构内（04 §4 触发线 doc_blocks > 500 万行时再评估）。
