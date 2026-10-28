# 仓库级统一入口：AI 门禁与人工交付共用（细则见 AGENTS.md「测试与验证」）。
# 后端依赖 uv、前端依赖 pnpm；集成测试需 FJ_TEST_DATABASE_URL
# （本机无 DB 时自动 skip，CI 全量跑，见 .github/workflows/ci.yml）。

.PHONY: verify hooks

verify: ## 全量门禁：后端 lint+单测 + 前端 lint+build
	$(MAKE) -C smart-bid-doctor-api lint
	$(MAKE) -C smart-bid-doctor-api test
	cd smart-bid-doctor-web && pnpm lint
	cd smart-bid-doctor-web && pnpm build

hooks: ## 启用项目级 Git 钩子（commit-msg 提交信息校验，规范见 .githooks/README.md）
	git config core.hooksPath .githooks
	chmod +x .githooks/commit-msg
