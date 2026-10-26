#!/usr/bin/env bash
# 每日备份（03 §6：pg_dump -Fc → /data/backups/，保留 14 天）
# crontab: 30 3 * * *  /srv/scripts/backup.sh
set -euo pipefail

BACKUP_DIR="${FJ_BACKUP_DIR:-/data/backups}"
KEEP_DAYS="${FJ_BACKUP_KEEP_DAYS:-14}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-feijian}"
PGDATABASE="${PGDATABASE:-feijian}"

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/${PGDATABASE}-${STAMP}.dump"

echo "[$(date -Is)] dumping ${PGDATABASE} -> ${OUT}"
pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -Fc -f "$OUT" "$PGDATABASE"

# 保留窗口外清理
find "$BACKUP_DIR" -name "*.dump" -mtime +"$KEEP_DAYS" -delete
echo "[$(date -Is)] backup done; removed dumps older than ${KEEP_DAYS}d"
