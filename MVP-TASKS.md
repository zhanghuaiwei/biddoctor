# smart-bid-doctor MVP 任务清单（P0/M1，W1–2）

> 快照：2026-10-28（平台化 v2.0 实装批次），与代码同步维护（变更反哺：功能状态变化须同次提交更新本文件）。
> 实现备注：已完成功能的**详细实现说明在各模块 docstring 与函数注释内**（AGENTS.md §上下文路由可按场景定位）；未开始功能的**TODO 已标注在桩代码内**（含推荐方案 + 实现过程 + 验收）。
> 状态图例：**[x]** 已完成且有测试 · **[~]** 底座/契约就绪、引擎未接 · **[ ]** 未开始。
> 2026-10-28 批注：除 LLM/Agent 能力（A/C/E 的模型调用部分）外的业务功能已全量实装闭环，
> 平台化管理域（05 文档 v2.0，40 表全量）见 §一 9–12；管理端前端 /admin 路由区 18 页就绪。

## 一、已完成功能

### 1. 认证与会话（02 §9.1）

| 功能 | 实现位置 | 备注/测试 |
|---|---|---|
| [x] 邮箱验证码（发码 60s 限流、5 分钟有效） | `services/auth_svc.py` `api/auth.py` | 一次性凭据原子 UPDATE 消费 + rowcount 判定 |
| [x] 登录签发 JWT（HS256 白名单、7 天） | `core/security.py` | `tests/test_auth_security.py` 全覆盖 |
| [x] 登录防爆破（IP+邮箱双桶限流、失败 5 次锁 15 分钟） | `services/auth_svc.py` + `core/ratelimit.py` | 滑动窗口限流器复用 |
| [x] dev 环境固定验证码 123456（prod 禁用） | `core/config.py` | dev_only 门控 |
| [x] 登录日志全量落库（sys_login_log，05 §5） | `services/log_svc.py` | 成功/失败/锁定原因/IP/UA；180 天留存 |
| [x] 邀测注册管控（invite_code + 原子消费，开关入 sys_config） | `services/rbac_svc.py` `api/auth.py` | signup.require_invite 开启后新注册必填 |

### 2. 项目与免费配额（02 §9.2、§7）

| 功能 | 实现位置 | 备注/测试 |
|---|---|---|
| [x] 项目 CRUD + 软删（deleted_at，不释放当月名额） | `services/project_svc.py` | 越权 404 不泄露存在性 |
| [x] 免费配额：行锁串行化（WITH FOR UPDATE），402 引导付费 | `services/quota_svc.py` | 配额计数含软删（防刷） |
| [x] 配额数运行时可调（sys_config quota.free_monthly，改值即生效） | `services/config_svc.py` | TTL 缓存 + 审计 sys_config_update |
| [x] 次数包余量查询 `/me/quota` | `services/quota_svc.py` `api/billing.py` | 金额 Decimal 契约 |

### 3. 文档上传与解析编排（02 §9.2、§8）

| 功能 | 实现位置 | 备注/测试 |
|---|---|---|
| [x] PDF 上传（流式接收、魔数/加密/页数/大小校验、sha256 去重复用） | `services/document_svc.py` | SpooledTemporaryFile 边收边算，禁整文件进内存 |
| [x] 解析进度查询 `/documents/{did}/status`（前端轮询入口） | `api/projects.py` | 进度由 parse handler 按批次推进 |
| [x] 任务创建（parse 任务入队，task_svc.create 只 flush） | `services/task_svc.py` | 与业务同事务、失败回滚不残留 |

### 4. 任务队列底座（02 §8）

| 功能 | 实现位置 | 备注/测试 |
|---|---|---|
| [x] PG SKIP LOCKED 认领（单条 UPDATE 原子置 running） | `worker/runner.py` | idx_tasks_claim 部分索引只覆盖 pending |
| [x] 心跳（30s）+ 超时回收 + 退避重试（attempt ≤3） | `worker/heartbeat.py` `runner.py` | 崩溃任务自动 recover_stale |
| [x] 五类业务 handler + purge 生命周期任务 | `worker/handlers/*` | parse/checklist 已实装；extract/embed/compare 为 LLM 桩 |

### 5. 订单与人工核销（02 §9.5）

| 功能 | 实现位置 | 备注/测试 |
|---|---|---|
| [x] 下单（order_no 唯一、PAY_HINT 收款提示、pending） | `services/billing_svc.py` | 撞号 IntegrityError 重试 ≤3；sub_* 订单走订阅分流 |
| [x] 管理员核销（订单翻转 + 发放同事务） | `billing_svc.grant` + `quota_svc.grant_pack`/`subscription_svc.activate` | 审计 ORDER_GRANTED / SUBSCRIPTION_GRANT |
| [x] 订单分页查询（用户端 + 管理端全量） | `api/billing.py` `api/admin/biz.py` | 统一 limit/offset |
| [x] 支付凭证上传（attachments order_voucher，用户端上传→管理端核销查看） | `services/attachment_svc.py` | ≤20MB 白名单魔数校验 |

### 6. 平台机制（全站横切）

| 功能 | 实现位置 | 备注/测试 |
|---|---|---|
| [x] 统一错误体 `{"error":{code,message}}` + 错误码注册表 | `core/errors.py` | AST 守卫 `tests/test_errors_registry.py` |
| [x] 枚举 StrEnum 注册表（状态机/角色/类型） | `core/enums.py` + 前端 `src/constants/enums.ts` | 两处同步（03 §3 取值域），v2.0 平台域枚举已双端登记 |
| [x] 审计留痕（独立事务、request_id 贯穿、INET 校验） | `services/audit_svc.py` `models/audit.py` | 四链互查；平台域 20+ 新 action 已注册打点 |
| [x] 滑动窗口限流（client_ip 分桶、全端点默认保护） | `core/ratelimit.py` `core/deps.py` | X-Forwarded-For 仅信内网对端 |
| [x] llm_calls 成本记账模型 + 运营指标聚合 | `models/task.py` `services/metrics_svc.py` | 含 model_id/prompt_template_id 平台扩展列 |

### 7. 运维底座（04）

| 功能 | 实现位置 | 备注/测试 |
|---|---|---|
| [x] healthz（DB 连通 + 磁盘余量）/ internal metrics（内部令牌双通道） | `api/internal.py` | hmac.compare_digest 常量时间比较 |
| [x] purge 生命周期任务（retain_until 到期软删 + 引用计数删文件） | `worker/handlers/purge.py` | 硬删唯一入口；v2.0 扩展附件回收 + sys 日志 180 天清理 |
| [x] 每日备份脚本 + daily_report（含 LLM 成本报表） | `deploy/` `worker/jobs.py` | daily_report 已并入 sys_job 调度 |
| [x] CI（lint/test/int）+ docker-compose.prod + deploy 脚本 | `.github/workflows/` `deploy/` | 迁移只加不删 |

### 8. 前端产品化结构（02 §9）

| 功能 | 实现位置 | 备注 |
|---|---|---|
| [x] 登录（发码倒计时/回跳 redirect/邀请码）、路由守卫、401 统一处理 | `views/LoginView.vue` `api/client.ts` `composables/useAuth.ts` | 定时器卸载清理 |
| [x] 项目列表/工作台/次数页 + 上传槽/配额徽标组件 | `views/*` `components/*` | 轮询 usePolling 终态自动停 |
| [x] 枚举/SKU/localStorage 键归口 constants，请求只走 src/api | `src/constants/*` `src/api/*` | 组件禁裸 fetch |
| [x] 报告详情页（结构化渲染 + 免责确认 + 导出打印） | `views/ReportDetailView.vue` | 清单/对照两形态 |

### 9. 解析引擎非 LLM 部分（M1/B1–B3 实装）

| 功能 | 实现位置 | 备注/测试 |
|---|---|---|
| [x] PyMuPDF 主路径逐页提取（字号众数阈值分 heading/text + section 归属） | `engine/parser/__init__.py` | 全文档众数字号定正文基准，标题占比高不失准 |
| [x] pdfplumber 表格页兜底（窄行多文本页候选，≤60 页预算） | `engine/parser/_page_tables` | 失败不阻断主解析 |
| [x] 扫描页检测（is_scanned_ratio 累计；≥60% 转 need_review 不静默） | `worker/handlers/parse.py` | OCR 为可选安装层（PaddleOCR 未启用仅告警） |
| [x] doc_blocks 分批落库（500 行/批随进度推进）+ 任务链续接 | `worker/handlers/parse.py` | 加密/损坏显式 _fail 不重试 |
| [ ] B4 金标集评测（`make eval` 召回 ≥90%） | — | F1/F2 验收项，依赖 C 抽取引擎 |

### 10. 清单报告闭环非 LLM 部分（M1/D 实装）

| 功能 | 实现位置 | 备注/测试 |
|---|---|---|
| [x] report_data JSONB 快照（stats/免责声明/逐条页码溯源） | `engine/report/__init__.py` `services/check_svc.py` | items 为空仍生成完整框架 |
| [x] Jinja2 服务端渲染 HTML 落盘 + reports 落库 | `engine/report/templates/*.html.j2` | checklist/comparison 两套模板 |
| [x] `POST /projects/{pid}/checklist-report` 202 建任务（400 前置先于入队） | `api/check.py` | 前端轮询终态后拉报告 |
| [x] `GET /reports/{rid}/export` FileResponse（打印即 PDF；清理后 410 REPORT_FILE_GONE） | `api/check.py` | 导出/免责确认写审计 |
| [x] 阅后即焚：报告生成同事务软删原件（物理回收走 purge） | `services/check_svc.py` | 集成测试断言文档列表清空 |
| [x] AIGC 标识合规（页眉横幅 + meta 元数据 + 隐式水印注释，05 §9.2） | 报告模板 | 集成测试断言导出含 AI 标识 |
| [x] findings 质量回流（agree/disagree + 备注，P2 列启用） | `api/check.py` `check_svc.set_finding_feedback` | 归属校验 404 |

### 11. 平台化管理域（05 v2.0 全量实装）

| 功能 | 实现位置 | 备注/测试 |
|---|---|---|
| [x] 26 张平台表 models + 幂等迁移 0002（全库 40 表） | `models/platform.py` `models/attachment.py` `models/ai.py` `models/commerce.py` | DDL 单一来源，迁移只加不删 |
| [x] RBAC：sys_role/sys_user_role/sys_menu 权限点（admin:<域>:<动作>）+ 404 同形越权 | `services/rbac_svc.py` `core/deps.require_perm` | 无绑定角色的 admin=全量（seed_admin 兼容）；集成测试覆盖 |
| [x] 内置角色/菜单/参数/定时任务/法务 v1/AI 模型注册种子（幂等） | `services/seed_svc.py` `scripts/bootstrap.py` | bootstrap 含种子步骤 |
| [x] 机构树 CRUD（软删，有子节点/在职用户拒绝） | `api/admin/sys_.py` | 写审计 sys_org_update |
| [x] 用户管理（禁用/解禁/角色授予/邀请码签发） | `api/admin/sys_.py` | 写审计 sys_user_ban 等 |
| [x] 参数配置（改值即生效 TTL 缓存）+ 字典管理（仅展示层） | `services/config_svc.py` `dict_svc.py` | sys_config_update 审计集成断言 |
| [x] 公告通知（draft→published→offline，用户端横幅分级展示） | `services/notice_svc.py` `components/NoticeBanner.vue` | 集成断言发布后用户端可见 |
| [x] 定时任务管理（sys_job 调度 tick + 启停/手动触发/运行历史） | `services/job_svc.py` `worker/jobs.py` | croniter 计算 next_run；原子认领防并发 |
| [x] 内置 job：stats_rollup（T+1+订阅清扫）/ alert_scan（4 类阈值）/ reconcile / daily_report | `worker/jobs.py` | 结果写 sys_job_log |
| [x] 告警闭环（阈值入 sys_config alert.*，触发落表去抖，人工 ack 写审计） | `services/alert_svc.py` | 管理端红点（未确认常驻） |
| [x] 日志三表分页 + CSV 导出（sys_oper_log 中间件逐请求落 /api/admin/*） | `services/log_svc.py` `main.py` | 导出写审计 log_export；不记请求体防凭据泄露 |
| [x] 统计报表（六维 T+1 汇总 + 即席查询 + CSV + 手动补算） | `services/stats_svc.py` `api/admin/stats.py` | 覆盖式写入幂等 |
| [x] 监控大盘（任务/LLM/容量水位聚合 + 存储分类统计） | `services/monitor_svc.py` | usage_ratio 支撑磁盘告警 |
| [x] 附件管理（白名单魔数/20MB/年月目录 sha 寻址/软删引用计数回收） | `services/attachment_svc.py` | 归属校验 404；集成测试覆盖 |
| [x] 法务版本化与签署（draft→effective→retired 同类唯一生效 + PIPL 留痕） | `services/legal_svc.py` `components/AgreementGate.vue` | 登录后未签署强制弹层；审计 agreement_signed |
| [x] AI 治理（模型注册计价快照/开关 + Prompt 版本 eval_score 锚定激活） | `services/ai_svc.py` `views/admin/AdminAiView.vue` | 激活须 eval_score 非空；审计 ai_prompt_switch |
| [x] 订阅闭环（计划管理 → sub_* 订单 → 核销激活/续期 + 按期发放次数包） | `services/subscription_svc.py` | billing_svc.grant 按 sku 前缀分流 |
| [x] 规则库版本（draft→active→retired + 条目 CRUD，M2 引擎读取） | `services/rule_svc.py` | 同 (industry, law_version) 唯一 active |
| [x] 支付流水表/管理端只读视图（P2 预留，对账 job 空转） | `models/commerce.py` `api/admin/biz.py` | 回调接入后自动出数 |
| [x] 管理端前端 /admin 路由区 18 页（菜单驱动导航 + 按钮权限过滤） | `layouts/AdminLayout.vue` `views/admin/*` | permission store 驱动；404 同形拦截 |

### 12. 用户端平台功能

| 功能 | 实现位置 | 备注 |
|---|---|---|
| [x] 公告横幅（published 分级样式可关闭） | `components/NoticeBanner.vue` | 公开端点 |
| [x] 协议签署门禁（未签署生效版强制弹层，Tab 切换阅读） | `components/AgreementGate.vue` | 不同意即退出登录 |
| [x] 管理控制台入口（有权限才渲染） | `layouts/MainLayout.vue` | permission store |
| [x] 报告列表/详情/导出/免责确认 | `views/ReportDetailView.vue` `ProjectDetailView.vue` | 任务轮询自动跳转 |
| [x] 支付凭证上传（订单页直传，管理端核销联动） | `views/QuotaView.vue` | 订阅计划展示与下单 |

## 二、未开始功能（TODO 已标注在代码，含推荐方案）

### A. LLM 接入层 [ ] —— TODO(M1/A1–A3) @ `llm/zhipu.py`

- **推荐方案**：httpx 直连 OpenAI 兼容 `/chat/completions`；429/5xx 指数退避 ≤3 次；连续 5 次失败熔断 5 分钟（阈值入 sys_config `llm.circuit_break_threshold`）；每次调用落 `llm_calls` 记账（**计价快照读 ai_model_config 注册表**，05 §9.3 实装就绪，锚定 model_id/prompt_template_id）。
- **实现过程**：① `chat()` 组装 messages，json_mode 带 `response_format`；② 接 `llm/budget.py` 任务级 token 上限；③ 熔断器挂 chat 入口，熔断期快速失败不耗配额；④ 成功/失败均写 llm_calls；⑤ Prompt 模板从 prompt_templates 读 active 版。
- **验收**：重试/熔断 mock 单测；配置注入后可真实调用返回结构化文本。

### C. 废标条款抽取 [ ] —— TODO(M1/C1–C3) @ `engine/extractor/__init__.py` + `handlers/extract.py`（MVP 核心难点）

- **推荐方案**：规则预筛（**读 rule_sets/rule_items active 版本，rule_svc.active_items 已就绪**）→ GLM 重模型 JSON Schema 结构化抽取五类条款 → 合并去重落 `check_items`。坏输出重试 ≤2 次、轻模型兜底，仍失败标 need_review 不静默丢弃。
- **实现过程**：① 预筛产出候选 doc_blocks（解析引擎已产出 blocks）；② 分批调用（~20 段/批），llm_calls 记账（purpose=extract）；③ 解析失败重试链；④ 落库后 `checklist_ready` + 建后续任务链（checklist handler 已就绪）；⑤ `make eval` 金标评测。
- **验收**：抽取召回 ≥90%（M1 门槛，02 §10）。

### E. 对照与判定（M2）[ ] —— TODO(M2) @ `engine/comparator/__init__.py` + `handlers/compare.py` + `handlers/embed.py`

- **推荐方案**：pg_trgm 文本 + pgvector 余弦（HNSW，EMBED_DIM=1024）混合检索（RRF 融合）→ GLM 重模型逐条 verdict（不确定绝不输出「满足」）→ 规则复核（rule_items veto 可推翻 LLM）→ findings + stats 汇总 → **check_svc.generate_comparison_report 报告封装已就绪**。
- **实现过程**：① embed handler 先行（bid 文档块向量）；② 逐条检索 top-k → 判定；③ findings 落库 + stats → 建对照报告任务；④ 配额发起时已扣，失败不回滚走 need_review。
- **验收**：判定与人工复核一致率 ≥85%（README 里程碑表）。

### F. 生产上线与验收 [ ]

| 项 | 内容 | 备注 |
|---|---|---|
| [ ] E1 压测 | 50 并发上传 + 100 并发查询，worker 吞吐达标 | 04 §7 |
| [ ] E2 Cron 接线 | sys_job 调度已内置于 worker 主循环（15s tick），部署验证 | 05 §3.4 |
| [ ] E3 上线 | prod 迁移（bootstrap 含种子）+ 冒烟 + 备份演练 | compose 已备 |
| [ ] F1/F2 金标评测 | `make eval` 抽取召回 ≥90% | 02 §10，依赖 C |

## 三、关键路径（串行依赖）

A（LLM 层）→ C（抽取）→ D（清单报告✅ 已实装）→ F（验收）；E（对照 M2）依赖 B✅/D✅ + embed。
平台机制与解析/报告/平台域已就绪：LLM 层接入即插即用（handler 编排职责、错误码、记账、留痕、
计价注册、prompt 版本、管理端 AI 治理页面均已预置）。

## 四、明确不做（MVP 外）

多租户与团队协作 · 在线支付自动核销（表与对账 job 预留）· 短信通道 · 分布式队列（Redis/Celery）·
全文搜索引擎 · OCR 离线包默认内置 · 报告服务端转 PDF · 移动端适配。
完整清单见 README「非目标」。
