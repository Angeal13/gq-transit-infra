#!/bin/bash
# backup_database.sh — backs up all province databases
# Run: sudo bash backup_database.sh
# Cron (daily 3am): 0 3 * * * /opt/bioko_server/scripts/backup_database.sh

set -e
BACKUP_DIR="/opt/bioko_backups/$(date +%Y-%m-%d)"
mkdir -p "$BACKUP_DIR"
source /opt/bioko_server/.env

REGIONS="bioko litoral centrosur welenzas kientem interprovince"
for region in $REGIONS; do
  DB="bus_tracking_gq_${region}"
  FILE="$BACKUP_DIR/${DB}.sql.gz"
  if mysql -u "$DB_USER" -p"$DB_PASSWORD" -e "USE \`$DB\`" 2>/dev/null; then
    mysqldump -u "$DB_USER" -p"$DB_PASSWORD" "$DB" | gzip > "$FILE"
    echo "Backed up: $DB → $FILE"
  fi
done

# Keep only last 30 days of backups
find /opt/bioko_backups -maxdepth 1 -type d -mtime +30 -exec rm -rf {} \; 2>/dev/null || true
echo "Backup complete: $BACKUP_DIR"
