# smart-bid-doctor 后端常用命令（uv 工作流：uv run 自动按 uv.lock 同步环境）
# 与设计文档对应关系见各 target 注释

.PHONY: bootstrap test test-int lint fmt seed-admin backup restore-backup daily-report eval load-test

# 初始化开发库（扩展 + alembic head）
bootstrap:
	uv run python scripts/bootstrap.py

# 单元 + 冒烟测试（不需要数据库）
test:
	uv run pytest tests -q

# 全量测试（需要 PostgreSQL+pgvector，03 §4：集成测试走独立库）
test-int:
	FJ_TEST_DATABASE_URL=$${FJ_TEST_DATABASE_URL:-postgresql+psycopg://postgres@localhost:5433/smart-bid-doctor_test} \
		uv run pytest tests -q

lint:
	uv run ruff check app tests scripts

fmt:
	uv run ruff check app tests scripts --fix

# 创建/提升管理员（03 §4：make seed-admin）
seed-admin:
	uv run python scripts/seed_admin.py --email $(EMAIL)

# 每日备份（03 §6：pg_dump -Fc，保留 14 天；crontab: 30 3 * * *）
backup:
	bash scripts/backup.sh

# 恢复演练（落到独立库，不动线上）
restore-backup:
	bash scripts/restore_backup.sh $(FILE)

# 每日业务自查报表（04 §6：crontab: 0 8 * * *）
daily-report:
	uv run python scripts/daily_report.py

# 金标集评测（M1/B4，02 §10）：--prescreen-only 只验预筛召回 ≥98%（无需 LLM）；
# 完整抽取评测召回 ≥90% 需 LLM 接入（桩期退出码 2 并提示）。make eval ARGS="--prescreen-only"
eval:
	uv run python scripts/eval_extract.py $(ARGS)

# E1 压测（04 §7：50 并发上传 + 100 并发查询；EMAIL=压测账号，dev 环境固定验证码）
load-test:
	uv run python scripts/load_test.py --base-url $(BASE) --email $(EMAIL)
