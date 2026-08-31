#!/usr/bin/env bash
# Konsistentes Backup der SQLite-Datenbank (nutzt die Online-Backup-API).
# Aufruf per systemd-Timer (weg-backup.timer) oder cron.
set -euo pipefail

APP_DIR="${WEG_APP_DIR:-/opt/weg-abrechnung}"
DB_FILE="${WEG_DB_FILE:-$APP_DIR/data/weg.db}"
BACKUP_DIR="${WEG_BACKUP_DIR:-$APP_DIR/backups}"
KEEP_DAYS="${WEG_BACKUP_KEEP_DAYS:-30}"

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
TARGET="$BACKUP_DIR/weg-$STAMP.db"

# .backup ist auch bei laufender Anwendung konsistent (kein Kopieren der Datei!)
sqlite3 "$DB_FILE" ".backup '$TARGET'"
gzip -f "$TARGET"

# alte Backups aufräumen
find "$BACKUP_DIR" -name 'weg-*.db.gz' -type f -mtime "+$KEEP_DAYS" -delete

echo "Backup: $TARGET.gz"
