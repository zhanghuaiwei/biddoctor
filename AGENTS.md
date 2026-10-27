# AGENTS.md — smart-bid-doctor 工程约定（面向所有 AI 编码工具）

> 适用工具：WorkBuddy / Codex / opencode / zcode / qorder / Trae / Claude Code / Cursor 等任何在本仓库工作的 AI。
> 统一机制：本文件是所有 AI 编码工具的**唯一规则来源**。原生读取 AGENTS.md 的工具（WorkBuddy / Codex / opencode / zcode / qorder）直接生效；不原生读取的工具走根目录**薄转发适配文件**（Claude Code → `CLAUDE.md`、Cursor → `.cursor/rules/agents.mdc`、Trae → `.trae/rules/project_rules.md`）。适配文件只指向本文件，**禁止把规则复制进适配文件**，防止多源漂移；新工具接入同理：原生支持则无需文件，否则加一个一页转发文件并在本行登记。
> 本文件是项目工程范式的**开源精简版**；权威完整版为内部 skill `smart-bid-doctor-engineering`（含留痕映射与反哺机制，仅内部工作区装载，不入库）。
> 冲突时以设计文档（01-04）与代码现状为准，其次本文件。

## 项目一句话

smart-bid-doctor：标书废标风险 AI 自查。FastAPI + SQLAlchemy 2 + PostgreSQL 16(pgvector) 后端 + Vue3 SPA；队列用 PG SKIP LOCKED，不引入 Redis/Celery/ES。

## 入口

- 始终使用简体中文回答，必要的代码、命令和术语可用英文。
- 纯问答、只读分析、评估和状态查询**保持只读**，不改仓库。
- 修改任务自动按 §分级 定级并走 §强制闭环，**无需用户指名级别**；"继续/按方案落地/就这么改"承接当前任务范围，切换模块或功能时重新定级。
- 修改前先 `git status`：保留用户已有改动，不做无关格式化、批量重排或回滚；与用户未提交改动冲突时先停下确认。
- 仓库内容每次有更改或新增后，**主动询问用户是否推送远程**；获肯定答复后才推送（未提交的先按仓库规范提交再推送，禁 force push）。
- 普通问答只读本文件；其余按 §上下文路由 命中再读，不预加载全仓文档。

## 分级

| 级别 | 判定 | 最低验证与留痕 |
|---|---|---|
| L0 只读 | 问答、分析、评估、状态查询 | 不改动仓库 |
| L1 微改 | 文案、注释、日志、文档、无行为机械调整 | `make lint` + 交付说明 |
| L2 小修 | 模块内低风险 bugfix、兼容字段 | 针对行为变更的测试 + `make lint` |
| L3 能力 | 新端点/新表/新页面/新任务类型/新审计动作/新错误码/新枚举取值 | 新端点三件套 + 留痕断言 + 迁移 + `make lint`/`make test-int` |
| L4 高风险 | 鉴权/JWT、配额计数与扣减、金额、限流策略、迁移策略、跨模块契约、基础设施边界 | L3 全部 + 方案先确认 + 人工复核 |

- 展示文案通常 L1；行为/阈值至少 L2；状态机流转/枚举取值/错误码至少 L3；鉴权/配额/金额至少 L4。
- 体系级改造（模块边界、公共框架、跨服务协议）拆成 L3/L4 子任务，不整块硬做。

## 强制闭环

按顺序完成；**任一必需环节缺失或失败，只能报告部分完成或阻断，不得声称完成**：

1. **基线**：`git status` 确认工作区状态，锁定级别与改动范围。
2. **澄清**：阻断项未决时先问，不臆测契约——尤其错误码、枚举取值、分页与金额字段类型、配额规则。
3. **设计**（仅 L3/L4）：改动面、迁移方案、审计动作、测试计划先对齐，未确认不编码。
4. **编码**：小步实现，遵守 §代码范式；分层 `api/` 薄 → `services/` 事务边界 → `engine/` 纯函数。
5. **测试**：行为变更必须有针对性自动化测试并实际运行（见 §测试与验证），不得以"仅编译通过/人工确认"代替。
6. **留痕自检**：新审计 action 已注册并覆盖创建/状态迁移/删除/核销各点；异步走 `tasks` 状态机；集成测试断言留痕存在。
7. **交付**：按 §交付说明 输出。

## 硬性禁区

1. **不要实现业务引擎**：`app/engine/`（解析/抽取/对照/报告）与 `app/llm/zhipu.py` 真实调用是 M1/M2 范围，保持 501/桩/TODO，除非 issue 明确要求。
2. **不要物理删除用户数据**：只允许 `deleted_at` 软删；硬删仅限 `worker/handlers/purge.py` 生命周期任务。
3. **不要绕过统一错误体**：业务错误一律 `raise AppError(status, "UPPER_SNAKE_CODE", "中文提示")`，响应恒为 `{"error": {"code", "message"}}`。
4. **不要新增基础设施组件**（Redis/Celery/ES/独立向量库）——架构决策见 README 技术选型表；替代实现：队列=PG SKIP LOCKED、锁/计数=行锁与原子 UPDATE、限流=进程内滑窗、会话=无状态 JWT、向量=pgvector、检索=pg_trgm（完整映射与引入信号见 README「Redis 替代方案」），演进信号出现前禁止预建。

## 代码范式

| 维度 | 规则 |
|---|---|
| 分层 | `api/` 薄（校验+编排+审计，**禁直接 ORM 查询**，唯一例外 healthz）→ `services/` 事务边界 → `engine/` 纯函数；复用聚合查询单一实现 |
| 响应契约 | 所有端点必须 `response_model=` Pydantic 模型，禁止裸 dict；分页**全站统一 limit/offset**（`Query(ge=, le=)`，列表响应带 `total`） |
| 枚举 | 状态/角色/类型取值一律引用 `app/core/enums.py`（StrEnum 注册表）与前端 `src/constants/enums.ts`，禁散落字面量；新增取值先改两处注册表再同步文档（03 §3 取值域） |
| 错误码 | `raise AppError(status, "UPPER_SNAKE_CODE", "中文提示")`，code 必须登记 `app/core/errors.py::ERROR_CODES`（`tests/test_errors_registry.py` AST 守卫：未登记/状态不一致即红）；响应恒为 `{"error": {"code", "message"}}` |
| 事务 | commit 只出现在 service/api 编排层；`task_svc.create` 只 flush；失败路径 `db.rollback()` 防半提交；**计数型规则（免费配额等）必须 `WITH FOR UPDATE` 行锁**；**一次性凭据（验证码等）必须原子 UPDATE 消费 + rowcount 判定**；**前置校验先于扣减**（对照发起：双文件就绪 400 先于配额扣减 402，避免无谓扣减+回滚写放大） |
| 审计 | `audit_svc.log()` 独立事务、失败不阻断主业务；action 一律引用 `AuditAction` 常量（禁魔法字符串）；自动附带 `request_id`；**不参与业务事务** |
| 时间 | 全部 `dt.datetime.now(dt.UTC)` + `TIMESTAMPTZ`；北京时区调度用 UTC+8 固定偏移；**用户可见日期（订单号等）显式 +8h，禁止依赖容器本地时钟** |
| 金额/邮箱 | 金额 `Decimal`（Numeric 列 + ORM/Schema 注解 Decimal，JSON 输出字符串）；比例/置信度等非金额数值可用 float；email 全串 lower 归一（注册/登录同口径） |
| 软删 | 用户数据查询必带 `deleted_at.is_(None)`（报告/任务等 join 查询同样要过滤项目软删）；**例外：配额计数类统计不含软删过滤**（软删不释放当月名额，防刷） |
| 安全 | JWT 验签白名单算法；取 sub 分桶必须验签；敏感凭据比较用 `hmac.compare_digest`（验证码/`internal_token`）；INET 等强类型列写入前格式校验；**真实客户端 IP 统一走 `deps.client_ip`**（X-Forwarded-For 仅信任内网对端，prod 另开 uvicorn `--proxy-headers`）；大文件上传流式接收（SpooledTemporaryFile 边收边算 sha256/大小），禁整文件进内存 |
| 迁移 | DDL 唯一来源 `app/models/`；改模型 → `alembic revision --autogenerate`；迁移只加不删 |
| 限流 | 复用 `app/core/ratelimit.py::SlidingWindowLimiter`（分桶键与 `deps.client_ip` 同口径）；新端点默认受全局限流保护 |
| 依赖 | 后端依赖用 **uv** 管理：`pyproject.toml` 声明（精确版本 pin `==`）+ `uv.lock` 锁文件入库，环境还原 `uv sync --frozen`（生产镜像 `--no-dev`），日常命令一律 `uv run`；升级 = 改 pyproject → `uv lock` → test-int 绿 → CI 绿 → 合并；前端 UI 库按需引入（unplugin），禁全量 import；**前端一律 pnpm**（版本锁 packageManager 字段，.npmrc node-linker=hoisted），lockfile=pnpm-lock.yaml，禁混用 npm |
| 前端结构 | 请求只走 `src/api/`（client 统一错误体解析/超时/401 回跳带 redirect + 资源模块显式泛型），组件禁裸 fetch；枚举/标签映射/SKU/localStorage 键归口 `src/constants/`；可复用逻辑进 `src/composables/`（定时器必须卸载清理：usePolling/useCountdown）；跨组件共享的全局状态归口 `src/stores/`（pinia setup store），持久化经 `constants/storage.ts` 的 STORAGE_KEYS 写 localStorage，非组件模块（router/api client）仅可在函数体内 useXxxStore()，禁模块顶层调用；金额按后端 Decimal 契约以字符串展示；UI 状态映射禁内联三元硬编码；设计令牌（断点/色板/阴影/动效时长与缓动）归口 `src/styles/variables.less`，Element Plus 主题经 `global.less` `:root` CSS 变量映射品牌色（--el-color-primary 全色阶，禁默认蓝），路由过渡与卡片/进场动效用 `global.less` 的 `.page-*`/`.lift-card`/`rise-in`/`.cascade-in`/`float-drift`，禁视图内散落硬编码时长、阴影与导航色；带进度的大文件上传走 `client.ts::uploadWithProgress`（XHR，fetch 上传进度仅 Chromium）、大文件下载走 `client.ts::downloadWithProgress`（fetch 流式），均归口唯一请求入口 |

## 功能全生命周期留痕（新增功能 checklist）

每个功能的创建→执行→状态变更→销毁都要可追溯，四条链路互查：
`audit_logs`（人为操作，`detail.request_id` ↔ 响应头 `X-Request-ID`）↔ `tasks`（异步状态机+心跳+重试）↔ `llm_calls`（成本记账，M1 起）↔ 结构化日志（request_id 贯穿 api→worker）。

新增功能必须：
1. 注册新 `audit action`（lower_snake）并在创建/状态迁移/删除/核销各点写审计；
2. 异步处理落 `tasks` 表走状态机（pending→running→succeeded/failed/need_review/cancelled），禁止旁路异步；
3. 写集成测试**断言留痕存在**（留痕写入失败会被静默吞掉，测试是唯一防线，参照 `tests/test_auth_security.py`）。

## 测试与验证

```bash
cd smart-bid-doctor-api
make lint        # ruff，提交前必须全绿
make test        # 单测（无需 DB）
make test-int    # 全量（需 FJ_TEST_DATABASE_URL，见 tests/conftest.py）
```

新增端点三件套：smoke 路由断言（`tests/test_smoke.py`）+ 集成正常路径 + 越权 404/错误码路径。
带内存状态（限流/节流单例）的测试必须用 autouse fixture 清理状态。
前端：`pnpm lint` + `pnpm build`（在 `smart-bid-doctor-web/`）。

## 交付说明

最终说明只列以下六项，不写过程流水账：
**任务级别** / **实际改动**（文件级）/ **验证结果**（命令与结果）/ **未验证项** / **影响面**（API 契约、迁移、前端契约、部署）/ **风险与需人工复核项**。

## 停止或升级

出现以下情况先停下提问或拆子任务，不蛮干、不降级绕过门禁：
- 范围不清且影响公共契约、配额计数、鉴权、金额或迁移策略；
- 需求触碰硬性禁区（业务引擎、物理删除、新基础设施、绕过统一错误体）；
- 与用户未提交改动冲突，或本地无法运行必需的验证命令。

## 上下文路由

按场景命中再读，避免整仓预加载：

| 场景 | 先读 |
|---|---|
| 背景与技术选型 | `README.md` |
| 错误码/枚举 | `app/core/errors.py`、`app/core/enums.py`、前端 `src/constants/enums.ts`；守卫 `tests/test_errors_registry.py` |
| 新端点 | `app/api/` 同级现有端点 + `tests/test_smoke.py`（三件套） |
| 表/迁移 | `app/models/`（DDL 唯一来源）+ alembic 现有迁移；全量功能数据库设计（含未实装业务表/平台 sys_* 表/扩展列）见 `db/` 两份 SQL（可执行源）与 03-数据库设计 v2.0，平台化管理与运维设计见 05 文档，新表实装时从 db/ 设计落 models/ + 迁移 |
| 异步任务 | `app/worker/`（SKIP LOCKED + 状态机 + 心跳） |
| 前端改动 | `src/api/`（client 契约）、`src/constants/`、`src/composables/` |
| 测试环境 | `tests/conftest.py`（FJ_TEST_DATABASE_URL） |
| 留痕参照 | `tests/test_auth_security.py` |
| 部署 | `docker-compose.prod.yml`、`deploy/` |

## 变更反哺

修完 bug 或加完功能：检查本文件与内部 skill 的范式条目是否需要更新（新决策规则、新安全基线、新留痕要求），**与代码变更同一次提交内完成**，保持范式与实现一致。
