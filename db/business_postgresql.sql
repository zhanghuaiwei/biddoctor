-- =============================================================================
-- smart-bid-doctor 业务数据库全量 DDL（business domain）
-- 版本 v2.0（2026-10-27）· 设计交付物（全量功能产品化版，配套 01–05 设计文档）
-- DBMS: PostgreSQL 16 · 编码 UTF8 · 单实例单库（向量域见 db/vector_pgvector.sql）
--
-- 定位与优先级
--   1) 本文件是产品全量功能（P0 清单 / P1 对照 / P2 支付·订阅·行业包 / 平台化管理
--      与运维，见 05-平台化管理与运维设计）的可执行建库脚本，
--      与《03-数据库设计》同源同内容；
--   2) 已实现表（标注 [P0·已实现]）的运行时事实来源是 smart-bid-doctor-api
--      的 app/models/ + alembic 迁移，本文件与其逐列对齐；标注 [P1]/[P2]/[平台] 的
--      表与扩展列为全量设计正式化、尚未实装——实装时走
--      models/ → alembic revision --autogenerate 落地，禁止对生产库直接执行本文件；
--   3) 执行顺序：先本文件，后 db/vector_pgvector.sql（doc_blocks 外键引用本文件
--      的 documents 表）。迁移只加不删（AGENTS.md）。
--
-- 全局约定
--   * 表/列 snake_case；主键 id BIGINT GENERATED ALWAYS AS IDENTITY；
--     对外暴露的实体另设 uuid 列（防 ID 遍历探测，gen_random_uuid() 服务端生成）；
--   * 平台管理类表以 sys_ 前缀归域（05 文档）；附件/法务/AI 治理为业务域表；
--   * 时间一律 TIMESTAMPTZ（UTC 存储）；用户可见日期（订单号等）应用层显式 +8h；
--   * 金额一律 NUMERIC + 应用层 Decimal（JSON 输出字符串）；
--   * 用户数据禁止物理删除：软删 deleted_at；硬删仅 worker purge 生命周期任务；
--     例外：配额计数类统计不含软删过滤（软删不释放当月名额，防刷）；
--   * 取值域不加 CHECK 约束：由 app/core/enums.py 与前端 src/constants/enums.ts
--     双注册表守门（03 §3），DDL 注释仅为阅读辅助；字典表（sys_dict_*）只管展示
--     层（label/排序/颜色），取值域仍以代码注册表为准；
--   * 软删查询必带 deleted_at IS NULL（部分索引同步过滤）。
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. users —— 用户 [P0·已实现 + 平台扩展列]（app/models/user.py）
--    邮箱全串 lower 归一为唯一登录标识（01·D8）；phone 为 P2 短信二通道预留列；
--    软删用户登录查询过滤 deleted_at IS NULL；
--    org_id 为平台化扩展列（05 §2）：NULL=平台直营个人用户；细粒度权限走
--    sys_user_role/sys_role（§20），users.role 保留为内置快速判定位。
-- -----------------------------------------------------------------------------
CREATE TABLE users (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uuid          UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,   -- 对外 id
    email         VARCHAR(320) NOT NULL UNIQUE,      -- 主登录标识（01·D8）
    phone         VARCHAR(20) UNIQUE,                -- 二通道：P2 待主体注册接短信后启用
    nickname      VARCHAR(64),
    role          VARCHAR(16) NOT NULL DEFAULT 'user',              -- user | admin（快速判定位，细粒度见 sys_role）
    org_id        BIGINT,                            -- [平台扩展列] 所属机构（05 §2，FK 见文末统一约束），NULL=个人用户
    status        VARCHAR(16) NOT NULL DEFAULT 'active',            -- active | banned
    invited_by    BIGINT REFERENCES users(id),       -- 邀请人（配 invite_codes，§3）
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ,
    deleted_at    TIMESTAMPTZ
);
CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_org ON users(org_id) WHERE deleted_at IS NULL;


-- -----------------------------------------------------------------------------
-- 2. verification_codes —— 一次性验证码 [P0·已实现]（app/models/user.py）
--    Redis-free 方案直接落库；email/sms 双通道复用（P2 短信通道不换表）。
--    消费必须原子 UPDATE + rowcount 判定（禁 check-then-act）。
-- -----------------------------------------------------------------------------
CREATE TABLE verification_codes (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    channel    VARCHAR(8) NOT NULL,                -- email | sms
    target     VARCHAR(320) NOT NULL,              -- 邮箱或手机号
    code       VARCHAR(6) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_vcodes_target ON verification_codes(channel, target, created_at);


-- -----------------------------------------------------------------------------
-- 3. invite_codes —— 邀请码 [P1·邀测预留]
--    P1 邀测期注册管控；消费走原子 UPDATE used_count + rowcount 判定；
--    注册成功回写 users.invited_by。
-- -----------------------------------------------------------------------------
CREATE TABLE invite_codes (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code       VARCHAR(16) NOT NULL UNIQUE,
    max_uses   INT NOT NULL DEFAULT 1,
    used_count INT NOT NULL DEFAULT 0,
    expires_at TIMESTAMPTZ,
    created_by BIGINT REFERENCES users(id),        -- 签发管理员
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- -----------------------------------------------------------------------------
-- 4. projects —— 检查项目（一次投标 = 一个项目）[P0·已实现]（app/models/project.py）
--    status 状态机：draft → tender_parsing → checklist_ready → comparing →
--    report_ready（archived 由软删置位）；retain_until 驱动 purge 生命周期任务。
-- -----------------------------------------------------------------------------
CREATE TABLE projects (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uuid         UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    user_id      BIGINT NOT NULL REFERENCES users(id),
    name         VARCHAR(128) NOT NULL,
    industry     VARCHAR(32) NOT NULL DEFAULT 'general',   -- general | medical（P2 行业包）
    status       VARCHAR(24) NOT NULL DEFAULT 'draft',
                 -- draft | tender_parsing | checklist_ready | comparing | report_ready | archived
    retain_until TIMESTAMPTZ,          -- 数据留存截止（默认 now()+30d；"阅后即焚"=报告后即删）
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at   TIMESTAMPTZ
);
CREATE INDEX idx_projects_user ON projects(user_id, updated_at) WHERE deleted_at IS NULL;


-- -----------------------------------------------------------------------------
-- 5. documents —— 上传文件 [P0·已实现]（app/models/document.py）
--    sha256 内容寻址去重（跨项目复用解析结果）；purge 按引用计数决定删物理文件；
--    一项目一 tender 一 bid（BAD_ROLE 拒绝第三份）。
-- -----------------------------------------------------------------------------
CREATE TABLE documents (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uuid             UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    project_id       BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    role             VARCHAR(8) NOT NULL,             -- tender | bid
    orig_name        VARCHAR(256) NOT NULL,
    stored_path      VARCHAR(512) NOT NULL,           -- /data/uploads/ab/cd/<sha256>.pdf
    sha256           CHAR(64) NOT NULL,
    size_bytes       BIGINT NOT NULL,
    total_pages      INT,
    is_scanned_ratio NUMERIC(4,3),
    parse_status     VARCHAR(16) NOT NULL DEFAULT 'pending',   -- pending | running | done | failed | need_review
    parse_warnings   JSONB NOT NULL DEFAULT '[]',
    embedding_status VARCHAR(16) NOT NULL DEFAULT 'pending',   -- pending | done | skipped | failed
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at       TIMESTAMPTZ
);
CREATE INDEX idx_documents_project ON documents(project_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_documents_sha ON documents(sha256);           -- 跨项目去重复用解析结果


-- -----------------------------------------------------------------------------
-- 6. check_items —— 检查项（清单核心）[P0·已实现 + P2 扩展列]（app/models/check.py）
--    五类条款（02 §3.1）；(project_id, code) 唯一防重；
--    law_basis 为 P2 新法版本追踪扩展列（02 §13，两法 2027–2028 修订出台后启用）。
-- -----------------------------------------------------------------------------
CREATE TABLE check_items (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uuid         UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    project_id   BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_id  BIGINT NOT NULL REFERENCES documents(id),      -- 来源招标文件
    code         VARCHAR(16) NOT NULL,             -- STAR-007 / QUAL-003 / …
    category     VARCHAR(16) NOT NULL,             -- qualification | compliance | star | price | format_seal
    requirement  TEXT NOT NULL,                    -- 规范化要求陈述
    raw_text     TEXT NOT NULL,                    -- 招标原文摘录（溯源）
    ref_page     INT NOT NULL,                     -- 原文页码（溯源）
    is_mandatory BOOLEAN NOT NULL DEFAULT false,   -- ★/否决/实质性响应
    check_hint   TEXT,
    confidence   NUMERIC(3,2) NOT NULL DEFAULT 1.00,
    law_basis    TEXT,                             -- [P2 扩展列] 新法条款依据（如"招标投标法(2027修订)第37条"）
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE check_items ADD CONSTRAINT uq_check_items_code UNIQUE (project_id, code);
CREATE INDEX idx_check_items_proj_cat ON check_items(project_id, category);


-- -----------------------------------------------------------------------------
-- 7. comparisons —— 对照执行 [P0·已实现]（app/models/check.py）
--    order_id 无 FK（免费/邀测不计订单，保留人工调整余地，与 quota_accounts.source_order 同口径）。
-- -----------------------------------------------------------------------------
CREATE TABLE comparisons (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uuid          UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    project_id    BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    tender_doc_id BIGINT NOT NULL REFERENCES documents(id),
    bid_doc_id    BIGINT NOT NULL REFERENCES documents(id),
    order_id      BIGINT,                           -- 消费的订单（nullable = 免费/邀测）
    status        VARCHAR(16) NOT NULL DEFAULT 'pending',   -- pending | running | done | failed | need_review
    stats         JSONB NOT NULL DEFAULT '{}',      -- {"red":2,"yellow":5,"green":43}
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ
);


-- -----------------------------------------------------------------------------
-- 8. findings —— 逐条判定 [P0·已实现 + P2 扩展列]（app/models/check.py）
--    verdict 四值：不确定一律 uncertain 标黄，绝不输出「满足」（01·D6）；
--    feedback 三列为 P2 扩展：用户标记误报 → 回流规则库迭代（03 v1.2 §5 建议的正式化）。
-- -----------------------------------------------------------------------------
CREATE TABLE findings (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    comparison_id   BIGINT NOT NULL REFERENCES comparisons(id) ON DELETE CASCADE,
    check_item_id   BIGINT NOT NULL REFERENCES check_items(id),
    verdict         VARCHAR(12) NOT NULL,             -- satisfied | deviated | missing | uncertain
    level           VARCHAR(8) NOT NULL,              -- red | yellow | green
    reason          TEXT NOT NULL,
    bid_ref_page    INT,                              -- 投标文件证据页
    bid_quote       TEXT,                             -- 投标文件证据摘录
    confidence      NUMERIC(3,2) NOT NULL,
    rule_overridden BOOLEAN NOT NULL DEFAULT false,   -- 规则引擎推翻 LLM 时 true
    feedback        VARCHAR(8),                       -- [P2 扩展列] agree | disagree（用户认可/误报标记）
    feedback_note   TEXT,                             -- [P2 扩展列] 用户补充说明
    feedback_at     TIMESTAMPTZ,                      -- [P2 扩展列]
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_findings_cmp ON findings(comparison_id, level);
CREATE INDEX idx_findings_item ON findings(check_item_id);


-- -----------------------------------------------------------------------------
-- 9. reports —— 报告 [P0·已实现 + P2 扩展列]（app/models/check.py）
--    report_data 为 JSONB 快照（02 §6.2 报告结构），html_path 为渲染产物落盘路径；
--    disclaimer_ack 为 P2 扩展列：用户查看/导出前勾选免责声明（03 v1.2 §5 建议的正式化）。
-- -----------------------------------------------------------------------------
CREATE TABLE reports (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uuid           UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    project_id     BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    kind           VARCHAR(12) NOT NULL,             -- checklist | comparison
    comparison_id  BIGINT REFERENCES comparisons(id),
    report_data    JSONB NOT NULL,                   -- 报告结构见 02 §6.2
    html_path      VARCHAR(512),                     -- 渲染产物路径（/data/reports/…）
    disclaimer_ack BOOLEAN NOT NULL DEFAULT false,   -- [P2 扩展列] 免责声明确认
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_reports_project ON reports(project_id, created_at);


-- -----------------------------------------------------------------------------
-- 10. tasks —— 异步任务队列（PG SKIP LOCKED）[P0·已实现]（app/models/task.py）
--     idx_tasks_claim 部分索引只覆盖 pending；认领 = 单条 UPDATE ... FOR UPDATE
--     SKIP LOCKED 原子置 running；心跳 30s、超时回收、退避重试 attempt ≤3。
-- -----------------------------------------------------------------------------
CREATE TABLE tasks (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id    BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    document_id   BIGINT REFERENCES documents(id) ON DELETE CASCADE,
    comparison_id BIGINT REFERENCES comparisons(id) ON DELETE CASCADE,
    type          VARCHAR(12) NOT NULL,               -- parse | extract | embed | checklist | compare | purge
    status        VARCHAR(12) NOT NULL DEFAULT 'pending',
                  -- pending | running | succeeded | failed | need_review | cancelled
    stage         VARCHAR(32),                        -- 细粒度进度：ocr:page_120/300
    progress      SMALLINT NOT NULL DEFAULT 0,        -- 0-100
    attempt       SMALLINT NOT NULL DEFAULT 0,
    error_code    VARCHAR(32),
    error_msg     TEXT,
    heartbeat_at  TIMESTAMPTZ,
    run_after     TIMESTAMPTZ NOT NULL DEFAULT now(), -- 退避重试延时
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ
);
CREATE INDEX idx_tasks_claim ON tasks(status, run_after)
    WHERE status IN ('pending');                     -- claim 扫描入口
CREATE INDEX idx_tasks_doc ON tasks(document_id, type);

-- worker 领取（事务内，app/worker/runner.py::CLAIM_SQL）：
-- UPDATE tasks SET status='running', heartbeat_at=now(), attempt=attempt+1
-- WHERE id = (SELECT id FROM tasks WHERE status='pending' AND run_after<=now()
--             ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1)
-- RETURNING *;


-- -----------------------------------------------------------------------------
-- 11. llm_calls —— LLM 成本记账 [P0·已实现 + 平台扩展列]（app/models/task.py）
--     每次调用落一行（token 用量/成本/时延/错误）；metrics 聚合与 daily_report
--     出成本报表（04 §6）；365 天保留（purge）；
--     model_id / prompt_template_id 为平台化扩展列（05 §9）：关联模型注册与
--     prompt 版本（成本计价快照 + 评测回归锚定）。
-- -----------------------------------------------------------------------------
CREATE TABLE llm_calls (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id       BIGINT REFERENCES tasks(id) ON DELETE SET NULL,
    project_id    BIGINT REFERENCES projects(id) ON DELETE SET NULL,
    purpose       VARCHAR(24) NOT NULL,             -- extract | judge | summary | retry | embed（行业包扩展随引擎追加）
    model         VARCHAR(32) NOT NULL,             -- glm-4.6 | glm-4.5-flash | embedding-3（文本快照）
    model_id      BIGINT,                           -- [平台扩展列] 模型注册关联（05 §9，FK 见文末统一约束）
    prompt_template_id BIGINT,                      -- [平台扩展列] prompt 版本关联（05 §9，FK 见文末）
    prompt_tokens INT NOT NULL DEFAULT 0,
    output_tokens INT NOT NULL DEFAULT 0,
    cost_cny      NUMERIC(8,4) NOT NULL DEFAULT 0,  -- 按智谱价目折算（单价快照见 ai_model_config）
    latency_ms    INT,
    error         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_llm_calls_proj ON llm_calls(project_id, created_at);
CREATE INDEX idx_llm_calls_day ON llm_calls(created_at);       -- 日成本汇总
CREATE INDEX idx_llm_calls_model ON llm_calls(model_id, created_at);


-- -----------------------------------------------------------------------------
-- 12. quota_accounts —— 对照次数包 [P0·已实现 + P2 取值扩展]（app/models/billing.py）
--     免费月度配额不入此表（月度计数走项目数统计，含软删防刷）；
--     remain 扣减必须 WITH FOR UPDATE 行锁原子扣减（quota_svc.consume_compare）。
--     [P2 取值扩展] type 增补 sub_<plan>（订阅按期发放）、invite_gift、admin_grant。
-- -----------------------------------------------------------------------------
CREATE TABLE quota_accounts (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES users(id),
    type         VARCHAR(16) NOT NULL,               -- cmp_x5 | cmp_x20 | sub_basic | sub_pro | invite_gift | admin_grant
                 -- （P0 仅 cmp_x5/cmp_x20；free 月度计数不入此表）
    remain       INT NOT NULL DEFAULT 0,
    expires_at   TIMESTAMPTZ,                        -- NULL = 不过期；订阅发放行 = 当期 period_end
    source_order BIGINT,                             -- 溯源但不加 FK（保留人工调整余地）
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_quota_user ON quota_accounts(user_id, expires_at);


-- -----------------------------------------------------------------------------
-- 13. orders —— 订单（人工收款核销 P0 → 自助支付 P2 共用入口）[P0·已实现]（app/models/billing.py）
--     order_no = FJ + 北京日期 + 6 位随机，唯一（撞号 IntegrityError 重试 ≤3）；
--     状态机 pending → granted / expired / refunded；
--     P2 自助支付时由 payments 回调驱动同一翻转，orders 结构不变（03 v1.2 §2.10 预留兑现）。
-- -----------------------------------------------------------------------------
CREATE TABLE orders (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_no   VARCHAR(24) NOT NULL UNIQUE,         -- FJ+YYMMDD+6位随机，用户报单号核销
    user_id    BIGINT NOT NULL REFERENCES users(id),
    sku        VARCHAR(16) NOT NULL,                -- cmp_x5 | cmp_x20（P2 扩展：sub_basic | sub_pro）
    amount_cny NUMERIC(8,2) NOT NULL,
    status     VARCHAR(16) NOT NULL DEFAULT 'pending',   -- pending | granted | expired | refunded
    note       VARCHAR(256),                        -- 用户备注（转账人姓名等）
    granted_at TIMESTAMPTZ,
    granted_by BIGINT REFERENCES users(id),         -- 管理员（人工核销）；P2 支付回调核销置 NULL + detail 留审计
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_orders_user ON orders(user_id, created_at);


-- -----------------------------------------------------------------------------
-- 14. payments —— 支付流水 [P2·自助支付]
--     渠道下单 → 异步回调翻转；幂等：out_trade_no 唯一 + 回调处理为
--     「原子 UPDATE status + rowcount 判定」一次性凭据范式；回调翻转 orders →
--     granted 与发放次数包/订阅同事务；callback_raw 留回调原文（对账/争议凭证）。
-- -----------------------------------------------------------------------------
CREATE TABLE payments (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id     BIGINT NOT NULL REFERENCES orders(id),
    channel      VARCHAR(16) NOT NULL,               -- wechat_native | alipay_qr | wechat_h5（按接入渠道扩展）
    out_trade_no VARCHAR(64) NOT NULL UNIQUE,        -- 渠道侧唯一流水号（幂等键）
    amount_cny   NUMERIC(8,2) NOT NULL,
    status       VARCHAR(16) NOT NULL DEFAULT 'created',
                 -- created | paying | paid | failed | closed | refunded
    callback_raw JSONB,                              -- 回调原文（渠道签名验证后留存）
    paid_at      TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_payments_order ON payments(order_id);
CREATE INDEX idx_payments_status ON payments(status, created_at);   -- 待对账扫描


-- -----------------------------------------------------------------------------
-- 15. subscription_plans —— 订阅计划配置 [P2·订阅制]
--     运营可配的售卖计划；按次 SKU（cmp_x5/cmp_x20）仍走代码常量 + orders.sku，
--     订阅因需周期/自动续费元数据独立建表。
-- -----------------------------------------------------------------------------
CREATE TABLE subscription_plans (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code          VARCHAR(24) NOT NULL UNIQUE,       -- sub_basic | sub_pro
    name          VARCHAR(64) NOT NULL,
    price_cny     NUMERIC(8,2) NOT NULL,
    period_months INT NOT NULL DEFAULT 1,
    compare_quota INT NOT NULL,                      -- 每期发放对照次数（经 quota_accounts 发放）
    status        VARCHAR(16) NOT NULL DEFAULT 'active',   -- active | retired
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- -----------------------------------------------------------------------------
-- 16. subscriptions —— 用户订阅实例 [P2·订阅制]
--     下单走 orders 统一入口（sku = plan.code），支付成功（人工核销或 payments
--     回调）后激活并写入 period_start/end；每期发放一行 quota_accounts
--     (type='sub_<plan>', expires_at=period_end)，与按次包同机制消费。
-- -----------------------------------------------------------------------------
CREATE TABLE subscriptions (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES users(id),
    plan_id      BIGINT NOT NULL REFERENCES subscription_plans(id),
    order_id     BIGINT,                             -- 首购/续费订单（无 FK，与 comparisons.order_id 同口径）
    status       VARCHAR(16) NOT NULL DEFAULT 'active',   -- active | expired | cancelled
    period_start TIMESTAMPTZ NOT NULL,
    period_end   TIMESTAMPTZ NOT NULL,
    auto_renew   BOOLEAN NOT NULL DEFAULT false,
    cancelled_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_subs_user ON subscriptions(user_id, status);
CREATE INDEX idx_subs_renew ON subscriptions(status, period_end) WHERE auto_renew = true;   -- 续费扫描


-- -----------------------------------------------------------------------------
-- 17. rule_sets —— 行业包规则库版本 [P2·行业包]
--     law_version 为新法版本追踪字段（02 §13）：《招标投标法（修订草案）》2026-06
--     一审、《政府采购法（修订草案）》征求意见，预计 2027–2028 相继出台，规则库
--     按法版本切换校验口径；同法版本内迭代用 version 递增。
-- -----------------------------------------------------------------------------
CREATE TABLE rule_sets (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    industry       VARCHAR(32) NOT NULL,             -- general | medical（01 §3 Industry）
    law_version    VARCHAR(64) NOT NULL,             -- 如 tender-law-2027rev / gov-procurement-2028
    version        INT NOT NULL DEFAULT 1,           -- 同法版本内规则库迭代号
    status         VARCHAR(16) NOT NULL DEFAULT 'draft',   -- draft | active | retired
    effective_from TIMESTAMPTZ,
    notes          TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_rule_sets ON rule_sets(industry, law_version, version);


-- -----------------------------------------------------------------------------
-- 18. rule_items —— 规则条目 [P2·行业包]
--     注入 extractor 规则预筛（召回放大，宁多勿漏）与 comparator 规则复核；
--     action 语义：hint = 预筛召回；must = 强制核对项；veto = 可推翻 LLM satisfied
--     （rule_overridden=true，02 §4.1）。
-- -----------------------------------------------------------------------------
CREATE TABLE rule_items (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_set_id BIGINT NOT NULL REFERENCES rule_sets(id) ON DELETE CASCADE,
    category    VARCHAR(16) NOT NULL,                -- qualification | compliance | star | price | format_seal
    kind        VARCHAR(16) NOT NULL,                -- regex | keyword | numeric | date
    pattern     TEXT NOT NULL,                       -- 正则/关键词/数值规则表达式
    action      VARCHAR(8) NOT NULL DEFAULT 'hint',  -- hint | must | veto
    weight      NUMERIC(3,2) NOT NULL DEFAULT 1.00,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_rule_items_set ON rule_items(rule_set_id, category);


-- -----------------------------------------------------------------------------
-- 19. audit_logs —— 审计 [P0·已实现]（app/models/audit.py）
--     人为操作留痕，与业务事务解耦（独立事务、失败不阻断主业务）；INET 强类型
--     写入前格式校验（非法值归 NULL）；detail.request_id ↔ 响应头 X-Request-ID ↔
--     tasks ↔ 结构化日志四链互查。
-- -----------------------------------------------------------------------------
CREATE TABLE audit_logs (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT,                               -- 无 FK（用户硬删不留悬挂引用）
    action     VARCHAR(48) NOT NULL,     -- login | upload | compare | order_grant | payment_callback | data_purge | ...
    target     VARCHAR(64),
    detail     JSONB NOT NULL DEFAULT '{}',
    ip         INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_user ON audit_logs(user_id, created_at);
CREATE INDEX idx_audit_action ON audit_logs(action, created_at);


-- ============================================================================
-- 以下为平台化管理域（05-平台化管理与运维设计）：系统管理 / 运维 / 审计日志 /
-- 统计 / 附件 / 法务合规 / AI 治理。sys_ 前缀归域；均标注 [平台]，实装随 05 章节。
-- ============================================================================


-- -----------------------------------------------------------------------------
-- 20. sys_org —— 机构树 [平台·系统管理]（05 §2）
--     只做组织归属与权限范围，不做数据隔离（多租户仍为 Out 边界）；
--     SaaS 部署默认单根节点，私有化交付时客户自建。
-- -----------------------------------------------------------------------------
CREATE TABLE sys_org (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parent_id  BIGINT REFERENCES sys_org(id),    -- NULL = 根节点
    name       VARCHAR(64) NOT NULL,
    code       VARCHAR(32) UNIQUE,               -- 机构编码
    sort       INT NOT NULL DEFAULT 0,
    leader     VARCHAR(64),
    status     VARCHAR(16) NOT NULL DEFAULT 'active',   -- active | disabled
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);


-- -----------------------------------------------------------------------------
-- 21. sys_role —— 角色 [平台·系统管理]（05 §2）
--     data_scope 为数据权限范围（私有化预留）：SaaS 部署仅用 all/self 两档。
-- -----------------------------------------------------------------------------
CREATE TABLE sys_role (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code       VARCHAR(32) NOT NULL UNIQUE,      -- super_admin | operator | tenant_admin | ...
    name       VARCHAR(64) NOT NULL,
    data_scope VARCHAR(16) NOT NULL DEFAULT 'self',   -- all | org | self
    sort       INT NOT NULL DEFAULT 0,
    status     VARCHAR(16) NOT NULL DEFAULT 'active', -- active | disabled
    remark     VARCHAR(256),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);


-- -----------------------------------------------------------------------------
-- 22. sys_user_role —— 用户角色映射 [平台·系统管理]
-- -----------------------------------------------------------------------------
CREATE TABLE sys_user_role (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES sys_role(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);


-- -----------------------------------------------------------------------------
-- 23. sys_menu —— 菜单与按钮权限点 [平台·系统管理]（05 §2）
--     前端 SPA 静态路由 + 本表驱动导航与按钮权限过滤（不做动态 import 路由）。
-- -----------------------------------------------------------------------------
CREATE TABLE sys_menu (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parent_id  BIGINT REFERENCES sys_menu(id),
    name       VARCHAR(64) NOT NULL,
    type       VARCHAR(8) NOT NULL,               -- dir | menu | button
    path       VARCHAR(128),                      -- 前端路由路径（dir/menu）
    component  VARCHAR(128),                      -- 组件标识（menu）
    perm       VARCHAR(64),                       -- 权限点（button），如 admin:order:grant
    icon       VARCHAR(32),
    sort       INT NOT NULL DEFAULT 0,
    visible    BOOLEAN NOT NULL DEFAULT true,
    status     VARCHAR(16) NOT NULL DEFAULT 'active',   -- active | disabled
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- -----------------------------------------------------------------------------
-- 24. sys_role_menu —— 角色菜单映射 [平台·系统管理]
-- -----------------------------------------------------------------------------
CREATE TABLE sys_role_menu (
    role_id BIGINT NOT NULL REFERENCES sys_role(id) ON DELETE CASCADE,
    menu_id BIGINT NOT NULL REFERENCES sys_menu(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, menu_id)
);


-- -----------------------------------------------------------------------------
-- 25. sys_config —— 参数配置 [平台·运维管理]（05 §3）
--     运行时可调参数（免费配额数、告警阈值、留存天数等）；改值写审计。
-- -----------------------------------------------------------------------------
CREATE TABLE sys_config (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    config_key VARCHAR(64) NOT NULL UNIQUE,       -- 如 quota.free_monthly / alert.cost_per_project
    value      TEXT NOT NULL,
    value_type VARCHAR(8) NOT NULL DEFAULT 'str', -- str | int | bool | json
    name       VARCHAR(64) NOT NULL,
    remark     VARCHAR(256),
    updated_by BIGINT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- -----------------------------------------------------------------------------
-- 26/27. sys_dict_type / sys_dict_data —— 字典 [平台·运维管理]（05 §3）
--        仅管展示层（label/排序/颜色）；取值域仍以代码枚举注册表为准（03 §3）。
-- -----------------------------------------------------------------------------
CREATE TABLE sys_dict_type (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dict_type  VARCHAR(64) NOT NULL UNIQUE,       -- 如 project_status / order_status
    name       VARCHAR(64) NOT NULL,
    remark     VARCHAR(256),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sys_dict_data (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dict_type  VARCHAR(64) NOT NULL REFERENCES sys_dict_type(dict_type) ON DELETE CASCADE,
    value      VARCHAR(64) NOT NULL,              -- 取值（与代码注册表一致）
    label      VARCHAR(64) NOT NULL,              -- 展示名
    sort       INT NOT NULL DEFAULT 0,
    extra      JSONB,                             -- 附加属性（颜色/图标等）
    status     VARCHAR(16) NOT NULL DEFAULT 'active',   -- active | disabled
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_dict_data_type ON sys_dict_data(dict_type, sort);


-- -----------------------------------------------------------------------------
-- 28. sys_notice —— 公告通知 [平台·运维管理]（05 §3）
-- -----------------------------------------------------------------------------
CREATE TABLE sys_notice (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title      VARCHAR(128) NOT NULL,
    content    TEXT NOT NULL,
    type       VARCHAR(8) NOT NULL DEFAULT 'notice',    -- notice | announcement
    level      VARCHAR(8) NOT NULL DEFAULT 'info',      -- info | warn | critical
    publish_at TIMESTAMPTZ,
    status     VARCHAR(16) NOT NULL DEFAULT 'draft',    -- draft | published | offline
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);


-- -----------------------------------------------------------------------------
-- 29/30. sys_job / sys_job_log —— 定时任务管理与运行记录 [平台·运维管理]（05 §3）
--        调度元数据入 sys_job；执行触发仍复用 tasks 队列（如 INSERT type=purge），
--        运行结果写 sys_job_log——不破坏任务队列范式（02 §8）。
-- -----------------------------------------------------------------------------
CREATE TABLE sys_job (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_key    VARCHAR(32) NOT NULL UNIQUE,       -- purge | daily_report | reconcile | stats_rollup
    name       VARCHAR(64) NOT NULL,
    cron_expr  VARCHAR(32) NOT NULL,
    handler    VARCHAR(64) NOT NULL,              -- worker handler 标识
    enabled    BOOLEAN NOT NULL DEFAULT true,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    remark     VARCHAR(256),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sys_job_log (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id     BIGINT REFERENCES sys_job(id) ON DELETE SET NULL,
    job_key    VARCHAR(32) NOT NULL,
    status     VARCHAR(8) NOT NULL,               -- ok | fail
    cost_ms    INT,
    result     JSONB,                             -- 运行摘要（如清理行数）
    error      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_job_log_key ON sys_job_log(job_key, created_at);


-- -----------------------------------------------------------------------------
-- 31. sys_login_log —— 登录日志 [平台·审计日志]（05 §5）
--     与 audit_logs 分工：本表记录每次登录尝试（含失败），audit_logs 记关键业务动作。
-- -----------------------------------------------------------------------------
CREATE TABLE sys_login_log (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     BIGINT,
    email       VARCHAR(320),
    result      VARCHAR(8) NOT NULL,              -- success | fail
    fail_reason VARCHAR(32),                      -- code_invalid | locked | banned | ...
    ip          INET,
    user_agent  VARCHAR(256),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_login_log_user ON sys_login_log(user_id, created_at);
CREATE INDEX idx_login_log_time ON sys_login_log(created_at);


-- -----------------------------------------------------------------------------
-- 32. sys_oper_log —— 管理端操作日志 [平台·审计日志]（05 §5）
--     管理端 HTTP 请求级日志（含失败请求）；与 audit_logs（关键动作、四链互查）互补。
-- -----------------------------------------------------------------------------
CREATE TABLE sys_oper_log (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     BIGINT,
    module      VARCHAR(32) NOT NULL,             -- admin_user | admin_order | admin_task | admin_rule ...
    action      VARCHAR(48) NOT NULL,             -- 与 audit action 对应
    method      VARCHAR(8),                       -- HTTP method
    path        VARCHAR(128),
    status_code INT,
    cost_ms     INT,
    request     JSONB,                            -- 请求摘要（敏感字段脱敏后）
    result      JSONB,                            -- 响应摘要（截断）
    ip          INET,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_oper_log_user ON sys_oper_log(user_id, created_at);
CREATE INDEX idx_oper_log_module ON sys_oper_log(module, created_at);


-- -----------------------------------------------------------------------------
-- 33. sys_stats_daily —— 每日统计汇总（T+1）[平台·统计]（05 §6）
--     明细实时聚合不建表；本表由 stats_rollup 定时任务每日汇总，供报表页与趋势图。
-- -----------------------------------------------------------------------------
CREATE TABLE sys_stats_daily (
    id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stat_date DATE NOT NULL,
    dim       VARCHAR(32) NOT NULL,               -- user | business | commerce | cost | quality | system
    metric    VARCHAR(64) NOT NULL,               -- 如 registered_users / compare_count / token_cost_cny
    value_num NUMERIC(16,4) NOT NULL DEFAULT 0,
    dims      JSONB,                              -- 细分维度（model/purpose/industry 等）
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE sys_stats_daily ADD CONSTRAINT uq_stats_daily UNIQUE (stat_date, dim, metric);
CREATE INDEX idx_stats_daily_date ON sys_stats_daily(stat_date, dim);


-- -----------------------------------------------------------------------------
-- 34. sys_alert_log —— 告警记录 [平台·运维监控]（05 §4）
--     告警规则入 sys_config（alert.* 键）；触发即落本表，支持确认（ack）闭环。
-- -----------------------------------------------------------------------------
CREATE TABLE sys_alert_log (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_key   VARCHAR(64) NOT NULL,              -- 对应 sys_config 的告警规则键
    level      VARCHAR(8) NOT NULL,               -- info | warn | critical
    title      VARCHAR(128) NOT NULL,
    content    TEXT,
    metric     JSONB,                             -- 触发时的指标快照
    acked_by   BIGINT,
    acked_at   TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_alert_log_rule ON sys_alert_log(rule_key, created_at);
CREATE INDEX idx_alert_log_ack ON sys_alert_log(acked_at) WHERE acked_at IS NULL;


-- -----------------------------------------------------------------------------
-- 35. attachments —— 常规附件 [平台·附件管理]（05 §7）
--     通用附件（弱关联无 FK，模块自解释）；documents（标书原件）保持独立不迁移。
-- -----------------------------------------------------------------------------
CREATE TABLE attachments (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uuid         UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    module       VARCHAR(32) NOT NULL,            -- order_voucher | appeal | import | profile ...
    business_id  BIGINT,                          -- 关联业务主键（弱关联）
    orig_name    VARCHAR(256) NOT NULL,
    stored_path  VARCHAR(512) NOT NULL,           -- /data/attachments/<ym>/<sha256><ext>
    sha256       CHAR(64) NOT NULL,
    content_type VARCHAR(64),
    size_bytes   BIGINT NOT NULL,
    uploaded_by  BIGINT REFERENCES users(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at   TIMESTAMPTZ
);
CREATE INDEX idx_attachments_biz ON attachments(module, business_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_attachments_sha ON attachments(sha256);


-- -----------------------------------------------------------------------------
-- 36/37. legal_documents / user_agreements —— 法律声明版本化与签署记录
--         [平台·法务合规]（05 §8）
-- -----------------------------------------------------------------------------
CREATE TABLE legal_documents (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_type     VARCHAR(16) NOT NULL,            -- user_agreement | privacy_policy | disclaimer
    version      VARCHAR(16) NOT NULL,            -- 如 v1.2
    title        VARCHAR(128) NOT NULL,
    content      TEXT NOT NULL,                   -- Markdown 全文
    effective_at TIMESTAMPTZ NOT NULL,
    status       VARCHAR(16) NOT NULL DEFAULT 'draft',  -- draft | effective | retired
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_legal_doc ON legal_documents(doc_type, version);

CREATE TABLE user_agreements (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES users(id),
    legal_doc_id BIGINT NOT NULL REFERENCES legal_documents(id),
    ip           INET,
    signed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_user_agreements_user ON user_agreements(user_id, signed_at);


-- -----------------------------------------------------------------------------
-- 38/39. ai_model_config / prompt_templates —— AI 治理 [平台·AI]（05 §9）
--        模型注册（用途映射/计价快照/限流/开关）+ prompt 版本管理（评测回归锚定）。
-- -----------------------------------------------------------------------------
CREATE TABLE ai_model_config (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_code   VARCHAR(32) NOT NULL UNIQUE,     -- glm-4.6 | glm-4.5-flash | embedding-3
    provider     VARCHAR(16) NOT NULL,            -- zhipu | ...
    purpose      VARCHAR(24) NOT NULL,            -- heavy | light | embed（用途映射，02 §7）
    input_price  NUMERIC(10,4) NOT NULL DEFAULT 0,   -- 元/百万 token（计价快照）
    output_price NUMERIC(10,4) NOT NULL DEFAULT 0,
    rpm_limit    INT,                             -- 限流（NULL=不限）
    enabled      BOOLEAN NOT NULL DEFAULT true,
    remark       VARCHAR(256),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE prompt_templates (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        VARCHAR(64) NOT NULL,             -- extract_v3 | judge_v2 ...
    purpose     VARCHAR(24) NOT NULL,             -- extract | judge | summary | retry
    version     INT NOT NULL,
    template    TEXT NOT NULL,                    -- 模板全文（占位符）
    variables   JSONB,                            -- 模板变量说明
    is_active   BOOLEAN NOT NULL DEFAULT false,   -- 同 (purpose, name) 仅一个 active
    eval_score  JSONB,                            -- 最近一次金标评测指标（回归锚定）
    updated_by  BIGINT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_prompt_version ON prompt_templates(name, version);
CREATE INDEX idx_prompt_active ON prompt_templates(purpose) WHERE is_active = true;


-- -----------------------------------------------------------------------------
-- 40. 跨域外键补齐（被引用表建表在后的场景统一在此追加，保持各域 DDL 独立可读）
-- -----------------------------------------------------------------------------
ALTER TABLE users ADD FOREIGN KEY (org_id) REFERENCES sys_org(id);
ALTER TABLE llm_calls ADD FOREIGN KEY (model_id) REFERENCES ai_model_config(id);
ALTER TABLE llm_calls ADD FOREIGN KEY (prompt_template_id) REFERENCES prompt_templates(id);
