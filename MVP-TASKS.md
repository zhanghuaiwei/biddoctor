# smart-bid-doctor MVP 任务清单（P0/M1，W1–2）

> 快照：2026-10-27，与代码同步维护（变更反哺：功能状态变化须同次提交更新本文件）。
> 实现备注：已完成功能的**详细实现说明在各模块 docstring 与函数注释内**（AGENTS.md §上下文路由可按场景定位）；未开始功能的**TODO 已标注在桩代码内**（含推荐方案 + 实现过程 + 验收）。
> 状态图例：**[x]** 已完成且有测试 · **[~]** 底座/契约就绪、引擎未接 · **[ ]** 未开始。

## 一、已完成功能

### 1. 认证与会话（02 §9.1）

| 功能 | 实现位置 | 备注/测试 |
|---|---|---|
| [x] 邮箱验证码（发码 60s 限流、5 分钟有效） | `services/auth_svc.py` `api/auth.py` | 一次性凭据原子 UPDATE 消费 + rowcount 判定 |
| [x] 登录签发 JWT（HS256 白名单、7 天） | `core/security.py` | `tests/test_auth_security.py` 全覆盖 |
| [x] 登录防爆破（IP+邮箱双桶限流、失败 5 次锁 15 分钟） | `services/auth_svc.py` + `core/ratelimit.py` | 滑动窗口限流器复用 |
| [x] dev 环境固定验证码 123456（prod 禁用） | `core/config.py` | dev_only 门控 |

### 2. 项目与免费配额（02 §9.2、§7）

| 功能 | 实现位置 | 备注/测试 |
|---|---|---|
| [x] 项目 CRUD + 软删（deleted_at，不释放当月名额） | `services/project_svc.py` | 越权 404 不泄露存在性 |
| [x] 免费配额：3 个/月，行锁串行化（WITH FOR UPDATE），402 引导付费 | `services/quota_svc.py` | 配额计数含软删（防刷），软删例外已注释 |
| [x] 次数包余量查询 `/me/quota` | `services/quota_svc.py` `api/billing.py` | 金额 Decimal 契约 |

### 3. 文档上传与解析编排（02 §9.2、§8）

| 功能 | 实现位置 | 备注/测试 |
|---|---|---|
| [x] PDF 上传（流式接收、魔数/加密/页数/大小校验、sha256 去重复用） | `services/document_svc.py` | SpooledTemporaryFile 边收边算，禁整文件进内存 |
| [~] 解析进度查询 `/documents/{did}/status`（前端轮询入口） | `api/projects.py` | 进度推进依赖 M1 解析引擎（见 TODO B） |
| [x] 任务创建（parse 任务入队，task_svc.create 只 flush） | `services/task_svc.py` | 与业务同事务、失败回滚不残留 |

### 4. 任务队列底座（02 §8）

| 功能 | 实现位置 | 备注/测试 |
|---|---|---|
| [x] PG SKIP LOCKED 认领（单条 UPDATE 原子置 running） | `worker/runner.py` | idx_tasks_claim 部分索引只覆盖 pending |
| [x] 心跳（30s）+ 超时回收 + 退避重试（attempt ≤3） | `worker/heartbeat.py` `runner.py` | 崩溃任务自动 recover_stale |
| [x] 五类业务 handler 骨架 + purge 生命周期任务 | `worker/handlers/*` | 业务编排 TODO 已标注（见 §二 B/C/D） |

### 5. 订单与人工核销（02 §9.5）

| 功能 | 实现位置 | 备注/测试 |
|---|---|---|
| [x] 下单（order_no 唯一、PAY_HINT 收款提示、pending） | `services/billing_svc.py` | 撞号 IntegrityError 重试 ≤3 |
| [x] 管理员核销（订单翻转 + 发放次数包同事务） | `billing_svc.grant` + `quota_svc.grant_pack` | 审计留痕 ORDER_GRANTED |
| [x] 订单分页查询 | `api/billing.py` | 统一 limit/offset |

### 6. 平台机制（全站横切）

| 功能 | 实现位置 | 备注/测试 |
|---|---|---|
| [x] 统一错误体 `{"error":{code,message}}` + 错误码注册表 | `core/errors.py` | AST 守卫 `tests/test_errors_registry.py` |
| [x] 枚举 StrEnum 注册表（状态机/角色/类型） | `core/enums.py` + 前端 `src/constants/enums.ts` | 两处同步（03 §3 取值域） |
| [x] 审计留痕（独立事务、request_id 贯穿、INET 校验） | `services/audit_svc.py` `models/audit.py` | 四链互查（audit↔tasks↔llm_calls↔日志） |
| [x] 滑动窗口限流（client_ip 分桶、全端点默认保护） | `core/ratelimit.py` `core/deps.py` | X-Forwarded-For 仅信内网对端 |
| [x] llm_calls 成本记账模型 + 运营指标聚合 | `models/task.py` `services/metrics_svc.py` | A3 接入即出报表 |

### 7. 运维底座（04）

| 功能 | 实现位置 | 备注/测试 |
|---|---|---|
| [x] healthz（DB 连通 + 磁盘余量）/ internal metrics（内部令牌双通道） | `api/internal.py` | hmac.compare_digest 常量时间比较 |
| [x] purge 生命周期任务（retain_until 到期软删 + 引用计数删文件） | `worker/handlers/purge.py` | 硬删唯一入口 |
| [x] 每日备份脚本 + daily_report（含 LLM 成本报表） | `deploy/` | Cron 占位，E2 接入 |
| [x] CI（lint/test/int）+ docker-compose.prod + deploy 脚本 | `.github/workflows/` `deploy/` | 迁移只加不删 |

### 8. 前端产品化结构（02 §9）

| 功能 | 实现位置 | 备注 |
|---|---|---|
| [x] 登录（发码倒计时/回跳 redirect）、路由守卫、401 统一处理 | `views/LoginView.vue` `api/client.ts` `composables/useAuth.ts` | 定时器卸载清理 |
| [x] 项目列表/工作台/次数页 + 上传槽/配额徽标组件 | `views/*` `components/*` | 轮询 usePolling 终态自动停 |
| [x] 枚举/SKU/localStorage 键归口 constants，请求只走 src/api | `src/constants/*` `src/api/*` | 组件禁裸 fetch |

## 二、未开始功能（TODO 已标注在代码，含推荐方案）

### A. LLM 接入层 [ ] —— TODO(M1/A1–A3) @ `llm/zhipu.py`

- **推荐方案**：httpx 直连 OpenAI 兼容 `/chat/completions`；429/5xx 指数退避 ≤3 次；连续 5 次失败熔断 5 分钟（进程内状态）；每次调用落 `llm_calls` 记账（token 单价表进配置，Decimal 计价）。
- **实现过程**：① `chat()` 组装 messages，json_mode 带 `response_format`；② 接 `llm/budget.py` 任务级 token 上限，超限抛专用错误码（同步 ERROR_CODES 注册表 + AST 守卫）；③ 熔断器挂 chat 入口，熔断期快速失败不耗配额；④ 成功/失败均写 llm_calls，metrics/daily_report 自动出成本报表。
- **验收**：重试/熔断 mock 单测；配置注入后可真实调用返回结构化文本。

### B. 解析管线 [~] —— TODO(M1/B1–B4) @ `engine/parser/__init__.py` + `handlers/parse.py`

- **推荐方案**：PyMuPDF 主路径逐页提取 + pdfplumber 兜底表格页；扫描页检测（字符阈值）累计 `is_scanned_ratio`，`ENABLE_OCR` 时 PaddleOCR 兜底；产物落 `doc_blocks`，同步文档状态机。
- **实现过程**：① fitz 逐页拆 block，字号阈值分 heading/text；② 表格页 extract_tables 转 type=table；③ 分批 INSERT（~500 行/批）→ done；④ 加密/损坏 → PARSE_ENCRYPTED/PARSE_CORRUPT 显式 _fail（不重试）；⑤ 金标集 20 份 + `make eval` 量化召回。
- **验收**：文本 PDF 解析成功率 >95%；扫描页可出文本；抽取召回 ≥90%（与 C 合计门槛）。

### C. 废标条款抽取 [ ] —— TODO(M1/C1–C3) @ `engine/extractor/__init__.py` + `handlers/extract.py`（MVP 核心难点）

- **推荐方案**：规则预筛（关键词/正则圈候选，宁多勿漏）→ GLM 重模型 JSON Schema 结构化抽取五类条款（code/quote/page/is_mandatory）→ 合并去重落 `check_items`。坏输出重试 ≤2 次、轻模型兜底，仍失败标 need_review 不静默丢弃。
- **实现过程**：① 预筛产出候选 doc_blocks，按页序拼 prompt（带页码溯源）；② 分批调用（~20 段/批控上下文），llm_calls 记账（purpose=extract）；③ 解析失败重试链；④ 落库后 `checklist_ready` + 建后续任务链；⑤ `make eval` 金标评测。
- **验收**：抽取召回 ≥90%（M1 门槛，02 §10）。

### D. 清单与报告 [~] —— TODO(M1/D1–D3) @ `engine/report/__init__.py` + `handlers/checklist.py` + `api/check.py` 两个 501 端点

- **推荐方案**：Jinja2 服务端渲染 HTML（checklist/comparison 两套模板）落盘 + `report_data` JSONB 快照；红黄绿分级 + 原文页码溯源；导出走 FileResponse（浏览器打印即 PDF，不做服务端 PDF）；D3 阅后即焚：报告生成后删原件 + doc_blocks。
- **实现过程**：① 汇总 → report_data 快照（含 stats/免责声明）；② 渲染 → Storage.save → reports 落库；③ `POST .../reports` 501→202（建 checklist 任务）、`GET /reports/{rid}/export` 501→200；④ 报告页脚标注出处与生成时间（04 §9）。
- **验收**：清单页可直接查看；导出可打印；阅后即焚生效（03 §5）。

### E. 对照与判定（M2）[ ] —— TODO(M2) @ `engine/comparator/__init__.py` + `handlers/compare.py` + `handlers/embed.py`

- **推荐方案**：pg_trgm 文本 + pgvector 余弦（HNSW，EMBED_DIM=1024）混合检索（RRF 融合）→ GLM 重模型逐条 verdict（satisfied/deviated/missing/uncertain，不确定绝不输出「满足」）→ 规则复核（报价数值/日期/签章规则可推翻 LLM，rule_overridden=true）→ findings + stats 汇总。
- **实现过程**：① embed handler 先行（bid 文档块向量）；② 逐条检索 top-k → 判定 prompt（purpose=judge 记账）；③ findings 落库 + stats → 建对照报告任务；④ 配额发起时已扣，失败不回滚走 need_review。
- **验收**：判定与人工复核一致率 ≥85%（README 里程碑表）。

### F. 生产上线与验收 [ ]

| 项 | 内容 | 备注 |
|---|---|---|
| [ ] E1 压测 | 50 并发上传 + 100 并发查询，worker 吞吐达标 | 04 §7 |
| [ ] E2 Cron 接线 | purge / daily_report 定时器上线 | deploy/ 脚本已备 |
| [ ] E3 上线 | prod 迁移 + 冒烟 + 备份演练 | compose 已备 |
| [ ] F1/F2 金标评测 | `make eval` 抽取召回 ≥90% | 02 §10 |

## 三、关键路径（串行依赖）

A（LLM 层）→ B（解析）→ C（抽取）→ D（清单报告）→ F（验收）；E（对照 M2）依赖 B/D + embed。
平台机制（§一 6/7）已就绪，引擎接入即插即用：handler 编排职责、错误码、记账、留痕均已预置。

## 四、明确不做（MVP 外）

多租户与团队协作 · 在线支付自动核销 · 短信通道 · 分布式队列（Redis/Celery）·
全文搜索引擎 · OCR 离线包默认内置 · 报告服务端转 PDF · 移动端适配。
完整清单见 README「非目标」。
