# smart-bid-doctor · 标书废检 Agent

> **Give your bid a health check before opening.** 面向中国招投标场景的投标废标风险 AI 自查工具。
> An AI self-check tool that helps bidders catch disqualification (废标) risks before bid opening.
>
> 创建：2026-10-24 · 状态：业务功能全量闭环（LLM 引擎接入中）· 平台化管理域 v2.0 就绪 · License: MIT

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/zhanghuaiwei/smart-bid-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/zhanghuaiwei/smart-bid-doctor/actions/workflows/ci.yml)
![Status](https://img.shields.io/badge/status-platform%20v2.0-blue)
![Python](https://img.shields.io/badge/python-3.12%2B-informational)
![Vue](https://img.shields.io/badge/vue-3.x-42b883)

## 一、项目简介

**smart-bid-doctor** 只做中立的「检」，不做「写」：上传招标文件（PDF），自动抽取**资格性 / 符合性 / ★号强制 / 报价 / 签章密封**五类废标相关条款，生成结构化《废标风险检查清单》，每条结论附原文页码溯源；后续版本支持招标×投标双文件逐条对照与红黄绿分级报告。

- 已完成与未开始功能的完整盘点（含实现方案）见 [MVP-TASKS.md](MVP-TASKS.md)
- AI 编码工具的工程约定（分层/事务/留痕/测试范式）见 [AGENTS.md](AGENTS.md)

## 二、技术选型

| 项 | 选定 | 备选与切换成本 |
|---|---|---|
| 大模型 | 智谱 GLM（重/轻两档，版本进配置）；OpenAI 兼容 Provider 抽象 | DeepSeek/Qwen：改 base_url + 配置 |
| 文档解析 | PyMuPDF + pdfplumber + PaddleOCR（独立可选安装） | MinerU / TextIn：替换 Parser 实现类 |
| 后端 | Python 3.12+ · FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 | — |
| 前端 | Vue 3 + Vite 5 + TypeScript + Element Plus（SPA，pnpm + less）＋ 静态落地页（nginx 直出） | — |
| 数据库 | PostgreSQL 16 + pgvector（1024 维）+ pg_trgm | — |
| 任务队列 | PostgreSQL `SKIP LOCKED` 任务表（不引入 Redis/Celery） | 量大后换 arq/celery |
| 部署 | 单机 Docker Compose（2C4G 起步） | 跑通后迁国内云 |
| 对象存储 | 本地磁盘 sha256 寻址 + 去重（接口已抽象） | 二期换 OSS/S3 |
| 登录认证 | 邮箱验证码（Resend/SMTP 自选），JWT 7 天 | 主体注册后加手机号二通道 |

依赖版本策略：后端用 **uv** 管理（`pyproject.toml` 声明 + `uv.lock` 锁文件入库，精确 pin `==`），升级 = 改 pyproject → `uv lock` → 集成测试全绿 → CI 绿 → 合并；前端版本锁在 `package.json` 的 `packageManager` 字段，lockfile 为 `pnpm-lock.yaml`。

## 三、架构选型

**单机单库一体化**：队列（SKIP LOCKED）、向量检索（pgvector HNSW）、模糊文本检索（pg_trgm）、审计与账本全部落在 PostgreSQL 一个实例内，不引入 Redis / Celery / ES / 独立向量库——以最小运维面支撑 MVP，各组件均为接口抽象，量大可平滑替换。

**Redis 替代方案**（硬性约定：MVP 不引入 Redis，其传统职责由 PG/进程内承接）：

| Redis 典型职责 | 本项目实现 | 位置 |
|---|---|---|
| 任务队列 | `tasks` 表 + `FOR UPDATE SKIP LOCKED` 认领 + 状态机/心跳/退避重试 | `app/worker/runner.py` |
| 分布式锁 / 计数扣减 | `WITH FOR UPDATE` 行锁（配额）；一次性凭据原子 UPDATE + rowcount | services 层（事务范式） |
| 限流 | 进程内滑动窗口单例（dict+deque，单实例部署下天然准确） | `app/core/ratelimit.py` |
| 会话 / 登录态 | 无状态 JWT（7 天过期），登出仅本地清除，无黑名单需求 | `app/core/security.py` |
| 向量检索 | pgvector（HNSW 索引） | PG 扩展 |
| 模糊文本检索 | pg_trgm + GIN 索引 | PG 扩展 |
| 缓存 | 不做——MVP 无热点读场景，过早缓存引入失效一致性负担 | — |
| Pub/Sub（预留） | PG `LISTEN/NOTIFY` 可替代轮询唤醒 worker（当前轮询间隔 3s 已够） | 未启用 |

**引入 Redis 的演进信号**（出现其一再评估，禁止提前预建）：

1. api 多实例部署且需要准确的分布式限流/锁——内存滑窗各实例独立计数会失准
2. 热点读达到千级 QPS（如报告被大量并发查看）——届时加缓存层
3. 任务吞吐到万级/天，或需要延迟队列/优先级队列——SKIP LOCKED 轮询间隔成为瓶颈
4. 需要毫秒级 Pub/Sub 扇出大量客户端

```
请求链路（同步）：
浏览器 ──HTTPS──▶ nginx（静态 SPA/落地页 + /api 反代，透传真实 IP）
                    │
                    ▼
          FastAPI api 层（薄：参数校验 + 编排 + 审计，禁直接 ORM）
                    ▼
          services 层（事务边界：commit/rollback/行锁都在这里）
                    ▼
          engine 层（纯函数，M1/M2 接入）      PostgreSQL 16（40 张表）

任务链路（异步）：
api 建任务（与业务同事务，只 flush）──▶ worker runner
   SKIP LOCKED 认领（原子置 running）→ handler 执行 → 心跳 30s
   失败退避重试（≤3）→ 超时回收 → 状态机 pending→running→succeeded/failed/need_review/cancelled
```

横切机制（全站生效，实现见代码内 docstring）：统一错误体 `{"error":{code,message}}` + 错误码 AST 守卫、枚举双端注册表、滑动窗口限流（真实客户端 IP 分桶）、审计留痕独立事务、`request_id` 贯穿 api→worker 四链互查（audit_logs ↔ tasks ↔ llm_calls ↔ 结构化日志）、软删约定与越权 404 防护。

## 四、目录结构

```
smart-bid-doctor/
├── AGENTS.md                  # AI 编码工具工程约定（唯一规则源，所有 AI/人必读）
├── MVP-TASKS.md               # 功能盘点：已完成/未开始 + 实现方案与验收门槛
├── CLAUDE.md · .cursor/ · .trae/   # 各 AI 工具薄转发入口（一律指向 AGENTS.md，不复制规则）
├── docker-compose.prod.yml    # 生产编排：nginx + api + worker + db
├── deploy/
│   └── nginx.conf             # 生产 nginx：静态前端 + /api 反代 + 真实 IP 还原
│
├── smart-bid-doctor-api/      # ── FastAPI 后端 ──
│   ├── app/
│   │   ├── main.py            # 应用装配：路由/中间件/统一异常/启动校验
│   │   ├── core/              # 横切底座
│   │   │   ├── config.py      #   Settings（FJ_ 前缀；prod fail-fast 校验强密钥）
│   │   │   ├── enums.py       #   枚举注册表（状态机/角色/类型，与前端 enums.ts 同步）
│   │   │   ├── errors.py      #   统一错误体 + 错误码注册表（AST 测试守卫）
│   │   │   ├── security.py    #   JWT 签发/验签（HS256 白名单，防 alg 混淆）
│   │   │   ├── deps.py        #   依赖注入：鉴权/分页/client_ip/限流
│   │   │   ├── ratelimit.py   #   滑动窗口限流器
│   │   │   ├── db.py          #   引擎/会话（pool_pre_ping）
│   │   │   └── logging.py     #   结构化 JSON 日志（request_id 贯穿）
│   │   ├── models/            # ORM 模型（DDL 唯一来源，40 张表 → alembic 迁移）
│   │   ├── schemas/           # Pydantic 请求/响应契约（全端点 response_model）
│   │   ├── api/               # 路由层（薄；禁直接 ORM，唯一例外 healthz）
│   │   │   ├── auth.py        #   验证码/登录（防爆破锁定）
│   │   │   ├── projects.py    #   项目 CRUD / PDF 上传 / 解析进度
│   │   │   ├── check.py       #   清单/对照/报告（报告生成与导出为 501 桩）
│   │   │   ├── billing.py     #   配额查询 / 订单 / 管理员核销
│   │   │   ├── tasks.py       #   任务查询（前端轮询兜底）
│   │   │   └── internal.py    #   healthz / 运营 metrics（内部令牌双通道）
│   │   ├── services/          # 业务层（事务边界；11 个 service）
│   │   │   ├── auth_svc.py    #   验证码（原子消费）/ 登录 / 防爆破
│   │   │   ├── project_svc.py / document_svc.py   # 项目与文档（上传校验/去重）
│   │   │   ├── check_svc.py / compare_svc.py      # 清单/对照/报告查询与发起
│   │   │   ├── quota_svc.py / billing_svc.py      # 免费配额（行锁）/ 订单核销
│   │   │   ├── task_svc.py / audit_svc.py / metrics_svc.py / storage.py
│   │   ├── engine/            # 业务引擎占位（M1/M2 接入；TODO 含推荐方案+实现过程）
│   │   │   ├── parser/        #   PDF 解析管线（TODO M1/B1–B4）
│   │   │   ├── extractor/     #   废标条款抽取（TODO M1/C1–C3，MVP 核心难点）
│   │   │   ├── comparator/    #   双文件对照（TODO M2）
│   │   │   └── report/        #   报告渲染（TODO M1/D2–D3）
│   │   ├── llm/               # Provider 抽象 + 智谱实现（M1 接入）+ token 预算
│   │   └── worker/            # 任务执行器
│   │       ├── runner.py      #   SKIP LOCKED 认领 / 退避重试 / 超时回收
│   │       ├── heartbeat.py   #   running 任务心跳（30s）
│   │       └── handlers/      #   parse/extract/embed/checklist/compare + purge（硬删唯一入口）
│   ├── alembic/               # 数据库迁移（只加不删）
│   ├── scripts/               # bootstrap / seed_admin / backup / restore_backup / daily_report
│   ├── tests/                 # 单测（无需 DB）+ 集成测试（FJ_TEST_DATABASE_URL）
│   ├── docker-compose.yml     # dev 编排（通常只起 db：pgvector/pgvector:pg16）
│   └── Makefile               # 常用命令（见 §七）
│
├── smart-bid-doctor-web/      # ── Vue3 SPA（pnpm）──
│   └── src/
│       ├── api/               # 统一请求层：client（错误体解析/超时/401 回跳带 redirect）+ 资源模块
│       ├── components/        # QuotaBadge（配额徽标）/ UploadSlot（上传槽）
│       ├── composables/       # useAuth / usePolling（终态自停）/ useCountdown（卸载清理）
│       ├── constants/         # enums.ts / skus.ts / storage.ts（枚举/SKU/键归口）
│       ├── utils/             # format.ts（金额按 Decimal 契约以字符串展示）
│       └── views/             # Login / Projects / ProjectDetail（工作台）/ Quota
│
├── smart-bid-doctor-site/     # 静态落地页（nginx 直出，保搜索引擎收录）
└── LICENSE                    # MIT
```

## 五、版本要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | **3.12+** | 依赖由 uv 管理：`pyproject.toml` 声明 + `uv.lock` 锁定 |
| uv | **0.12+** | `brew install uv`（或 `curl -LsSf https://astral.sh/uv/install.sh \| sh`） |
| PostgreSQL | **16**（含 pgvector、pg_trgm 扩展） | dev 镜像 `pgvector/pgvector:pg16` |
| Node.js | **≥ 18** | Vite 5 要求 |
| pnpm | **10.34.9**（`packageManager` 锁定） | `corepack enable pnpm` 启用；禁混用 npm |
| Docker | Docker Engine + Compose v2 | dev 起 db；prod 全栈 |

## 六、快速启动（开发环境）

```bash
# ── 后端（首次）──
cd smart-bid-doctor-api
uv sync                                # 按 uv.lock 精确还原环境（含 dev 组；替代 venv+pip）
# 创建 .env.development 并按需修改（dev 默认值即可跑；个人覆盖用 .env.development.local）
# 键清单见下方「八、配置说明」；env 文件一律不入库
docker compose up -d db                   # 起 PostgreSQL(pgvector)
uv run python scripts/bootstrap.py        # 建扩展 + 迁移（生产同样执行本脚本）
uv run uvicorn app.main:app --reload      # API :8000，OpenAPI 文档 /api/docs
uv run python -m app.worker.runner        # 任务执行器（另开终端）

# ── 前端 ──
cd smart-bid-doctor-web
corepack enable pnpm                  # 首次
pnpm install
pnpm dev                              # :5173，/api 代理到 8000

# ── 落地页 ──
# smart-bid-doctor-site/index.html 静态部署即可

# dev 环境登录验证码固定为 123456（FJ_ENV=dev）
```

## 七、常用命令

后端（`smart-bid-doctor-api/` 下）：

| 命令 | 作用 |
|---|---|
| `make bootstrap` | 初始化库（扩展 + alembic head） |
| `make test` | 单测 + 冒烟（不需要数据库） |
| `make test-int` | 全量测试（需 `FJ_TEST_DATABASE_URL` 指向独立测试库） |
| `make lint` / `make fmt` | ruff 检查 / 自动修复（提交前必须全绿） |
| `make seed-admin EMAIL=x@y.com` | 创建/提升管理员 |
| `make backup` | pg_dump 备份，保留 14 天（crontab 03:30） |
| `make restore-backup FILE=xxx.dump` | 恢复演练（落独立库，不动线上） |
| `make daily-report` | 每日业务自查报表（crontab 08:00） |

前端（`smart-bid-doctor-web/` 下）：`pnpm dev`（开发）· `pnpm build`（vite build + vue-tsc 类型门禁）· `pnpm typecheck`。

## 八、配置说明

配置经环境变量注入，前缀 `FJ_`，全部键与 `app/core/config.py` Settings 一一对应（全清单见下表）。

**多环境文件体系**（前后端同名对齐，env 文件一律不入库）：

```
加载栈（后者优先级高，OS 环境变量始终最高）：
.env → .env.development | .env.production | .env.test → .env.{...}.local
```

- 后端：文件栈由 `FJ_ENV`（OS 环境变量，缺省 dev）选择——`dev→development`、`prod→production`、`test→test`；`.env.development.local` 为个人本机覆盖；`.env.test` 由 `tests/conftest.py` 读取（如 `FJ_TEST_DATABASE_URL`）
- 前端：Vite 原生语义，仅 `VITE_` 前缀变量暴露给客户端（**严禁放密钥**）；dev 代理地址 `VITE_API_PROXY_TARGET` 可在 `.env.development.local` 按本机端口覆盖
- 生产：容器内通常无任何 env 文件，全部经 `docker-compose.prod.yml` 的 `environment` 段以真实环境变量注入（与文件栈语义兼容）

| 键 | 默认/示例 | 说明 |
|---|---|---|
| `FJ_ENV` | `dev` \| `prod` | prod 启动强制校验强密钥与内部令牌（fail-fast） |
| `FJ_DATABASE_URL` | `postgresql+psycopg://...` | 主库连接串 |
| `FJ_JWT_SECRET` / `FJ_JWT_EXPIRE_DAYS` | — / `7` | prod：≥32 字符强随机 |
| `FJ_INTERNAL_TOKEN` | 空 | prod 必填；空则 `/internal/*` 回退管理员 Bearer |
| `FJ_UPLOAD_DIR` / `FJ_MAX_UPLOAD_MB` / `FJ_MAX_PAGES` | `./data/uploads` / `100` / `500` | 上传目录与限制 |
| `FJ_FREE_PROJECTS_PER_MONTH` | `3` | 每账号每月免费项目数 |
| `FJ_CORS_ORIGINS` | `http://localhost:5173` | 逗号分隔；prod 禁止 `*` |
| `FJ_RATE_LIMIT_PER_MIN` | `120` | 每账号+IP 每分钟，0=关闭 |
| `FJ_DEV_FIXED_CODE` | `123456` | 仅 dev 生效的固定验证码 |
| `FJ_SKU_CATALOG` | JSON | 商品价目（订单 SKU 取值域由此驱动） |
| `FJ_ZHIPU_API_KEY` / `FJ_ZHIPU_BASE_URL` | — / 智谱 v4 | M1 接入 LLM 时配置（OpenAI 兼容） |
| `FJ_LLM_MODEL_HEAVY` / `FJ_LLM_MODEL_LIGHT` | `glm-4.6` / `glm-4.5-flash` | 重任务（抽取/判定）/ 轻任务（分类/兜底） |
| `FJ_TEST_DATABASE_URL` | — | 集成测试独立库（仅本地/CI 用，读自 `.env.test` / OS 环境变量） |

前端构建期变量（`smart-bid-doctor-web/`，仅 `VITE_` 前缀暴露给客户端，严禁放密钥）：

| 键 | 默认/示例 | 说明 |
|---|---|---|
| `VITE_API_PROXY_TARGET` | `http://localhost:8000` | dev 代理后端地址（`.env.development.local` 可按本机端口覆盖） |

## 九、生产部署

```bash
# 根目录 docker-compose.prod.yml：nginx + api + worker + db 完整拓扑，secrets 经 .env 注入
docker compose -f docker-compose.prod.yml up -d
```

nginx 配置见 [`deploy/nginx.conf`](deploy/nginx.conf)（静态前端 + `/api` 反代 + 真实客户端 IP 透传，uvicorn 另开 `--proxy-headers`）。任务执行器内置每日数据生命周期清理（type=purge）与 running 任务心跳。

## 十、项目说明

- **工程约定**：[AGENTS.md](AGENTS.md) 是所有 AI 编码工具（WorkBuddy / Codex / opencode / Trae / Claude Code / Cursor 等）的唯一规则源——分层、事务、审计留痕、错误码、软删、安全基线均在其中代码化，并有测试守卫。
- **设计文档**：01-系统概要设计 / 02-详细设计 / 03-数据库设计 / 04-架构设计为内部资料，**不随本开源库发布**；本 README + 代码内注释 + OpenAPI（`/api/docs`）已覆盖开源协作所需信息。代码内详细实现说明见各模块 docstring，未开始功能的实现方案见桩内 TODO 块。
- **里程碑**：

| 阶段 | 时间 | 交付 | 门槛 |
|---|---|---|---|
| M1 MVP | W1–2 | 招标文件→废标条款清单（免费） | 金标集抽取召回 ≥90% |
| M2 Beta | W3–6 | 双文件对照检查（邀测 10–20 家） | 对照判定与人工复核一致率 ≥85% |
| M3 付费 | W7–8 | 按次收费（人工核销） | 免费转付费 ≥5% |
| M4 垂直 | Q2 | 医疗器械偏离表专项 + 订阅 | 器械客户复购 ≥30% |

- **当前 MVP 边界**：已完成（登录/项目/上传/队列/订单/平台机制）与未开始（解析/抽取/清单报告/对照/上线）逐项盘点见 [MVP-TASKS.md](MVP-TASKS.md)。明确不做：评标辅助与围标串标检测（法律风险）、多租户、在线支付自动核销、短信登录（列已留）、Word/OFD 原生解析（经 LibreOffice 转 PDF）。

## 十一、声明

**免责声明**：smart-bid-doctor 输出为**辅助人工复核工具**，不构成任何「保证不废标」承诺；每条结论均附原文出处，高危项须人工确认。使用者应遵守所在采购项目的保密与合规要求，不得将本工具用于评标辅助、围标串标等违法违规用途。

**隐私与数据**：上传文件仅用于本次检查；原件与解析产物按留存策略（默认 30 天）自动清理，报告支持阅后即焚。

## License

[MIT](LICENSE) © 2026 Zhang Huaiwei (张怀伟)
