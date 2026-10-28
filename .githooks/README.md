# Git Hooks

本目录存放项目级 Git Hook。配置一次 hooksPath 后，Git 会在本仓库提交时自动调用这里的 hook。

## 启用方式

仓库根目录执行（等价命令见根目录 `Makefile`）：

```bash
make hooks
# 即：git config core.hooksPath .githooks && chmod +x .githooks/commit-msg
```

## 提交信息规范

提交信息标题必须遵循 Conventional Commits：

```text
<type>(<scope>): <subject>
```

`scope` 可省略（`<type>: <subject>`）；冒号后空格推荐但不强制；正文与 footer 不校验。
允许的 `type`：`feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert`。
`Merge *` / `Revert *` 开头的 Git 自动生成提交豁免；破坏性变更用 `!` 标记（如 `feat(api)!:`）。

本仓 scope 惯例：`api` / `web` / `db` / `docs` / `gate`（工程门禁类）等，按改动主体选择。

## 与 AI 范式的关系

- 钩子只做提交信息格式门禁，不做内容门禁；行为变更的验证仍按根目录 `AGENTS.md`「强制闭环」与「测试与验证」执行（统一入口 `make verify`）。
- 提交拆分纪律见 `AGENTS.md`「入口」：多批次混同改动按归属拆分提交。
