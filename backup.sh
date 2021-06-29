#!/bin/sh
# Backup the geochron database to /var/local/geochron/backup<DATE>.gz
# To restore, use:
# gunzip -c /var/local/geochron/backup20211202.gz | docker-compose exec -T db psql -U geochron -f-
mkdir -p /var/local/geochron
cd `dirname $0`
docker-compose exec -T db pg_dump -c -U geochron | gzip -c > /var/local/geochron/backup`date +%Y%m%d`.gz
# delete backups more than a week old
find /var/local/geochron/ -mtime +7 -delete
