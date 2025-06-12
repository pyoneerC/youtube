#!/bin/bash
BACKUP_DIR="backups/$(date +%Y-%m-%d)"
mkdir -p "$BACKUP_DIR"

# Backup de la base de datos (si existe)
pg_dump $DATABASE_URL > "$BACKUP_DIR/database.sql"

# Backup de archivos de configuración
cp .env "$BACKUP_DIR/"
cp requirements.txt "$BACKUP_DIR/"

# Comprimir backup
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"
rm -rf "$BACKUP_DIR"
