# smart-bid-doctor · 标书废检 Agent

> **Give your bid a health check before opening.** 面向中国招投标场景的投标废标风险 AI 自查工具。
> An AI self-check tool that helps bidders catch disqualification (废标) risks before bid opening.
>
> 创建：2026-10-24 · 状态：MVP 骨架就绪，业务引擎 M1 接入中 · License: MIT

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/zhanghuaiwei/smart-bid-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/zhanghuaiwei/smart-bid-doctor/actions/workflows/ci.yml)
![Status](https://img.shields.io/badge/status-MVP%20skeleton-blue)
![Python](https://img.shields.io/badge/python-3.12+-informational)
![Vue](https://img.shields.io/badge/vue-3.x-42b883)

**smart-bid-doctor** 只做中立的「检」，不做「写」：上传招标文件（PDF），自动抽取资格性/符合性/★号强制/报价/签章密封五类废标相关条款，生成结构化《废标风险检查清单》，每条结论附原文页码溯源；后续版本支持招标×投标双文件逐条对照与红黄绿分级报告。

目录 `smart-bid-doctor-api` / `smart-bid-doctor-web` / `smart-bid-doctor-site` 与项目同名。

## 本次 MVP 边界（已确认）

**In（MVP 交付，对应设计分期 P0/M1，W1–2）**

| # | 能力 | 状态 |
|---|---|---|
| 1 | 邮箱验证码登录（dev 固定码；prod 接 SMTP/Resend） | 骨架就绪 |
| 2 | 检查项目 CRUD（免费 3 项目/月） | 骨架就绪 |
| 3 | 招标 PDF 上传（魔数/加密/页数≤500/大小≤100MB 校验，sha256 去重） | 骨架就绪 |
| 4 | 文档解析管线（PyMuPDF+pdfplumber 文本路径，扫描页 OCR 兜底） | 待 M1 接入（接口位 `app/engine/parser/`） |
| 5 | 废标条款抽取（规则预筛 + GLM 结构化抽取 + 合并去重） | 待 M1 接入（`app/engine/extractor/`） |
| 6 | 废标风险清单（五类条款、编号、原文引用+页码溯源、在线查看） | 待 M1 接入 |
| 7 | 任务队列与状态机（PG SKIP LOCKED，进度轮询） | 骨架就绪 |
| 8 | HTML 报告 + 浏览器打印导出 | 待 M1 接入 |

**Out（本次不做）**

- 投标文件上传与双文件对照检查（M2，W3–6；对照引擎接口位已留）
- 按次付费/订单/人工核销（M3，W7–8；配额与订单 CRUD 骨架已就绪）
- 医疗器械行业包（P2）、订阅与商户自助支付
- 短信登录（个人主体短信通道不可用，`users.phone` 已留列）
- Word/OFD 原生解析（Word 先经 LibreOffice 转 PDF）
- 评标辅助、围标串标检测（法律风险，明确 Out）

## 文档

完整设计文档（01-系统概要设计 / 02-详细设计 / 03-数据库设计 / 04-架构设计 / 市场调研）为内部资料，**不随本开源库发布**。本 README + 代码内注释 + OpenAPI 文档（`/api/docs`）已覆盖开源协作所需信息。

关键设计决策摘要：

| 项 | 选定 | 备选与切换成本 |
|---|---|---|
| 大模型 | 智谱 GLM（重/轻两档，版本进配置）；OpenAI 兼容 Provider 抽象 | DeepSeek/Qwen：改 base_url + 配置 |
| 文档解析 | PyMuPDF + pdfplumber + PaddleOCR（独立可选安装） | MinerU / TextIn：替换 Parser 实现类 |
| 后端 | Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic | — |
| 前端 | Vue 3 + Vite + TypeScript + Element Plus（SPA，pnpm + less + 响应式）＋ 静态落地页（nginx 直出） | — |
| 数据库 | PostgreSQL 16 + pgvector（1024 维）+ pg_trgm | — |
| 任务队列 | PostgreSQL `SKIP LOCKED` 任务表（不引入 Redis） | 量大后换 arq/celery |
| 部署 | 单机 Docker Compose（2C4G 起步） | 跑通后迁国内云 |
| 对象存储 | 本地磁盘 sha256 寻址 + 去重（接口已抽象） | 二期换 OSS/S3 |
| 登录认证 | 邮箱验证码（Resend/SMTP 自选），JWT 7 天 | 主体注册后加手机号二通道 |

## 代码仓库结构

```
smart-bid-doctor/
├── AGENTS.md        # AI 编码工具工程约定（分层/事务/留痕/测试范式，所有 Agent 必读）
├── smart-bid-doctor-api/     # FastAPI 后端：core(配置/枚举/错误码注册表)/models/schemas/services/api 分层
│                    #   + worker 任务执行器（SKIP LOCKED）+ alembic 迁移
│                    #   app/engine/（解析/抽取/对照/报告）与 app/llm/（Provider）为接口占位
├── smart-bid-doctor-web/     # Vue3 + Vite + Element Plus 应用 SPA（登录/项目/上传/清单/次数订单）
│                    #   src/api（统一请求层）+ components + composables + constants（枚举/SKU 归口）
├── smart-bid-doctor-site/    # 静态落地页（nginx 直出，保搜索引擎收录）
├── deploy/          # 生产 nginx 配置（静态前端 + /api 反代）
└── LICENSE          # MIT
```

已实现（非业务骨架）：邮箱验证码登录、项目 CRUD（含 status 过滤与分页）、PDF 上传校验（流式接收，边收边算 sha256/大小）、任务创建与状态查询、统一错误体（错误码注册表代码化 + AST 测试守卫）、业务枚举注册表（后端 `core/enums.py` ↔ 前端 `constants/enums.ts`）、健康检查与内部指标、结构化 JSON 日志、软删约定、越权 404 防护、反代真实客户端 IP 还原（限流/审计/防爆破同口径）。
业务桩：清单生成/报告导出端点返回 501，parse/extract/embed/checklist/compare handler 只推进任务状态，LLM Provider 为接口占位（模型名/base_url 进配置）。

## 快速上手

```bash
# 后端（首次）
cd smart-bid-doctor-api
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
docker compose up -d db                # 起 PostgreSQL(pgvector)
.venv/bin/python scripts/bootstrap.py  # 建扩展+迁移（生产同样执行本脚本）
.venv/bin/uvicorn app.main:app --reload          # API :8000，文档 /api/docs
.venv/bin/python -m app.worker.runner            # 任务执行器（另开终端）

# 测试（集成测试需要 PostgreSQL + pgvector，通过 FJ_TEST_DATABASE_URL 提供）
.venv/bin/python -m pytest tests -q
.venv/bin/ruff check app tests scripts   # lint

# 前端（pnpm，版本见 package.json packageManager；corepack enable pnpm 启用）
cd smart-bid-doctor-web && pnpm install
pnpm build        # vite build + vue-tsc 类型门禁
pnpm dev          # :5173，/api 代理到 8000
# 落地页：smart-bid-doctor-site/index.html 静态部署即可

# dev 环境登录验证码固定为 123456（FJ_ENV=dev）
```

运维（`smart-bid-doctor-api/` 下，与 03/04 设计文档对应）：

```bash
make bootstrap        # 初始化库（扩展+迁移）
make seed-admin EMAIL=ops@example.com   # 管理员账号（03 §4）
make daily-report     # 每日业务自查报表（04 §6，crontab 08:00）
make backup           # pg_dump 备份，保留 14 天（03 §6，crontab 03:30）
make restore-backup FILE=/data/backups/xxx.dump   # 恢复演练（独立库）
```

生产部署用 `docker-compose.prod.yml`（nginx + api + worker + db 完整拓扑，secrets 经 .env 注入）；
任务执行器内置每日数据生命周期清理（type=purge，03 §5）与 running 任务心跳（02 §8）。

配置经环境变量注入（前缀 `FJ_`，全键清单见 `smart-bid-doctor-api/.env.example`，与 `app/core/config.py` Settings 一一对应，如 `FJ_DATABASE_URL` / `FJ_JWT_SECRET` / `FJ_UPLOAD_DIR` / `FJ_ZHIPU_API_KEY`）；prod 环境启动强制校验强密钥与内部令牌。

## 里程碑

| 阶段 | 时间 | 交付 | 门槛 |
|---|---|---|---|
| M1 MVP | W1–2 | 招标文件→废标条款清单（免费） | 金标集抽取召回 ≥90% |
| M2 Beta | W3–6 | 双文件对照检查（邀测 10–20 家） | 对照判定与人工复核一致率 ≥85% |
| M3 付费 | W7–8 | 按次收费（人工核销） | 免费转付费 ≥5% |
| M4 垂直 | Q2 | 医疗器械偏离表专项 + 订阅 | 器械客户复购 ≥30% |

## 免责声明

smart-bid-doctor 输出为**辅助人工复核工具**，不构成任何「保证不废标」承诺；每条结论均附原文出处，高危项须人工确认。使用者应遵守所在采购项目的保密与合规要求。

## License

[MIT](LICENSE) © 2026 Zhang Huaiwei (张怀伟)
