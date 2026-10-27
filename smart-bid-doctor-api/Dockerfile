FROM python:3.12-slim

# uv 官方镜像精确版本 pin（与本地开发 uv 版本一致）；升级 = 同步改这里与 AGENTS.md「依赖」行
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /uvx /usr/local/bin/

WORKDIR /srv
# 字节码预编译提速启动；copy 模式兼容 bind-mount 场景
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# 先只拷依赖清单充分利用层缓存（pyproject/uv.lock 不变时源码变更不触发重装）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts

# 容器内 python/uvicorn 直取 .venv（compose command 无需感知 uv）
ENV PATH="/srv/.venv/bin:$PATH"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# M1 OCR 启用时单独构建，避免基础镜像膨胀（约 +1GB）：
# RUN uv pip install paddlepaddle paddleocr
