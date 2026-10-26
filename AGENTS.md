# AGENTS.md — BidDoctor 工程约定（面向所有 AI 编码工具）

> 适用工具：Claude Code / Codex / Cursor / WorkBuddy 等任何在本仓库工作的 AI。
> 本文件是项目工程范式的**开源精简版**；权威完整版为内部 skill `biddoctor-engineering`（含留痕映射与反哺机制）。
> 冲突时以设计文档（01-04）与代码现状为准，其次本文件。

## 项目一句话

BidDoctor（代号 feijian）：标书废标风险 AI 自查。FastAPI + SQLAlchemy 2 + PostgreSQL 16(pgvector) 后端 + Vue3 SPA；队列用 PG SKIP LOCKED，不引入 Redis/Celery/ES。

## 硬性禁区

1. **不要实现业务引擎**：`app/engine/`（解析/抽取/对照/报告）与 `app/llm/zhipu.py` 真实调用是 M1/M2 范围，保持 501/桩/TODO，除非 issue 明确要求。
2. **不要物理删除用户数据**：只允许 `deleted_at` 软删；硬删仅限 `worker/handlers/purge.py` 生命周期任务。
3. **不要绕过统一错误体**：业务错误一律 `raise AppError(status, "UPPER_SNAKE_CODE", "中文提示")`，响应恒为 `{"error": {"code", "message"}}`。
4. **不要新增基础设施组件**（Redis/Celery/ES/独立向量库）——架构决策见 README 技术选型表。

## 代码范式

| 维度 | 规则 |
|---|---|
| 分层 | `api/` 薄（校验+编排+审计，**禁直接 ORM 查询**，唯一例外 healthz）→ `services/` 事务边界 → `engine/` 纯函数；复用聚合查询单一实现 |
| 响应契约 | 所有端点必须 `response_model=` Pydantic 模型，禁止裸 dict；分页参数用 `Query(ge=, le=)` |
| 事务 | commit 只出现在 service/api 编排层；`task_svc.create` 只 flush；失败路径 `db.rollback()` 防半提交；**计数型规则（免费配额等）必须 `WITH FOR UPDATE` 行锁**；**一次性凭据（验证码等）必须原子 UPDATE 消费 + rowcount 判定** |
| 审计 | `audit_svc.log()` 独立事务、失败不阻断主业务；action 一律引用 `AuditAction` 常量（禁魔法字符串）；自动附带 `request_id`；**不参与业务事务** |
| 时间 | 全部 `dt.datetime.now(dt.UTC)` + `TIMESTAMPTZ`；北京时区调度用 UTC+8 固定偏移；**用户可见日期（订单号等）显式 +8h，禁止依赖容器本地时钟** |
| 金额/邮箱 | 金额 `Decimal`（Numeric 列），schema 禁 float；email 全串 lower 归一（注册/登录同口径） |
| 软删 | 用户数据查询必带 `deleted_at.is_(None)`；**例外：配额计数类统计不含软删过滤**（软删不释放当月名额，防刷） |
| 安全 | JWT 验签白名单算法；取 sub 分桶必须验签；敏感凭据比较用 `hmac.compare_digest`（验证码/`internal_token`）；INET 等强类型列写入前格式校验；错误码注册表见 `app/core/errors.py` docstring |
| 迁移 | DDL 唯一来源 `app/models/`；改模型 → `alembic revision --autogenerate`；迁移只加不删 |
| 限流 | 复用 `app/core/ratelimit.py::SlidingWindowLimiter`；新端点默认受全局限流保护 |
| 依赖 | requirements 精确版本 pin（`==`），升级 = 改版本 → test-int 绿 → CI 绿 → 合并；前端 UI 库按需引入（unplugin），禁全量 import |

## 功能全生命周期留痕（新增功能 checklist）

每个功能的创建→执行→状态变更→销毁都要可追溯，四条链路互查：
`audit_logs`（人为操作，`detail.request_id` ↔ 响应头 `X-Request-ID`）↔ `tasks`（异步状态机+心跳+重试）↔ `llm_calls`（成本记账，M1 起）↔ 结构化日志（request_id 贯穿 api→worker）。

新增功能必须：
1. 注册新 `audit action`（lower_snake）并在创建/状态迁移/删除/核销各点写审计；
2. 异步处理落 `tasks` 表走状态机（pending→running→succeeded/failed/need_review/cancelled），禁止旁路异步；
3. 写集成测试**断言留痕存在**（留痕写入失败会被静默吞掉，测试是唯一防线，参照 `tests/test_auth_security.py`）。

## 测试与验证

```bash
cd feijian-api
make lint        # ruff，提交前必须全绿
make test        # 单测（无需 DB）
make test-int    # 全量（需 FJ_TEST_DATABASE_URL，见 tests/conftest.py）
```

新增端点三件套：smoke 路由断言（`tests/test_smoke.py`）+ 集成正常路径 + 越权 404/错误码路径。
带内存状态（限流/节流单例）的测试必须用 autouse fixture 清理状态。

## 变更反哺

修完 bug 或加完功能：检查本文件与内部 skill 的范式条目是否需要更新（新决策规则、新安全基线、新留痕要求），**与代码变更同一次提交内完成**，保持范式与实现一致。
