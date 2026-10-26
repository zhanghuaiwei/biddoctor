#!/usr/bin/env bash
# 恢复演练（03 §6：make restore-backup FILE=… 一键验证）
# 用法: ./scripts/restore_backup.sh /data/backups/feijian-20261026-033000.dump [目标库名]
set -euo pipefail

FILE="${1:?用法: restore_backup.sh <dump文件> [目标库名(默认 feijian_restore)]}"
TARGET="${2:-feijian_restore}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-feijian}"

echo "[$(date -Is)] restoring ${FILE} -> database ${TARGET}"
# 恢复演练落在独立库，不动线上库；演练后自行 drop
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -c "SELECT 1 FROM pg_database WHERE datname='${TARGET}'" | grep -q 1 \
  || psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -c "CREATE DATABASE ${TARGET}"
pg_restore -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$TARGET" --no-owner --if-exists "$FILE"
echo "[$(date -Is)] restore OK -> ${TARGET}"
echo "验证提示: psql -d ${TARGET} -c '\\dt' 后执行 ANALYZE doc_blocks;（03 §6，HNSW 索引随库恢复无需重建）"
