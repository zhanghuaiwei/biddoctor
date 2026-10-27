# smart-bid-doctor 后端常用命令（骨架版）
# 与设计文档对应关系见各 target 注释

.PHONY: bootstrap test test-int lint fmt seed-admin backup restore-backup daily-report

# 初始化开发库（扩展 + alembic head）
bootstrap:
	python scripts/bootstrap.py

# 单元 + 冒烟测试（不需要数据库）
test:
	python -m pytest tests -q

# 全量测试（需要 PostgreSQL+pgvector，03 §4：集成测试走独立库）
test-int:
	FJ_TEST_DATABASE_URL=$${FJ_TEST_DATABASE_URL:-postgresql+psycopg://postgres@localhost:5433/smart-bid-doctor_test} \
		python -m pytest tests -q

lint:
	ruff check app tests scripts

fmt:
	ruff check app tests scripts --fix

# 创建/提升管理员（03 §4：make seed-admin）
seed-admin:
	python scripts/seed_admin.py --email $(EMAIL)

# 每日备份（03 §6：pg_dump -Fc，保留 14 天；crontab: 30 3 * * *）
backup:
	bash scripts/backup.sh

# 恢复演练（落到独立库，不动线上）
restore-backup:
	bash scripts/restore_backup.sh $(FILE)

# 每日业务自查报表（04 §6：crontab: 0 8 * * *）
daily-report:
	python scripts/daily_report.py
