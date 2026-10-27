# Scheduled database backups

`scripts/backup_db.py` (with `backend/app/backup.py`) creates consistent zip
snapshots of `analytics.db`, `admin.db`, and `users.db` using the sqlite3 backup
API, then prunes old archives. This document covers running it on a schedule and
drilling a restore; it does not add new backup code.

## Configuration

| Variable | Default | Meaning |
|----------|---------|---------|
| `CACHE_DIR` | `/app/data` in Docker, `./data` locally | Directory holding the SQLite databases. |
| `BACKUP_DIR` | `$CACHE_DIR/backups` | Where archives are written. Point this at a different volume/disk in production. |
| `BACKUP_KEEP` | `7` | Number of most recent archives to retain; older ones are pruned after each run. |

Run from the repository root so the script can import `backend/app`:

```bash
CACHE_DIR=./data BACKUP_DIR=./data/backups BACKUP_KEEP=7 python3 scripts/backup_db.py backup
python3 scripts/backup_db.py list
```

Archives are named `backup-<UTC timestamp>.zip` (e.g. `backup-20260101T030000Z.zip`).

## Cron

Daily at 03:15, logging to syslog:

```cron
# m h dom mon dow  command
15 3 * * *  cd /srv/OperationChildShield && CACHE_DIR=/srv/data BACKUP_DIR=/srv/backups BACKUP_KEEP=14 /usr/bin/python3 scripts/backup_db.py backup >> /var/log/ocs-backup.log 2>&1
```

Use `crontab -e` for the service user that owns `CACHE_DIR`; the process needs
read access to the databases and write access to `BACKUP_DIR`. Set `MAILTO=` in
the crontab so failures reach a monitored inbox, or rely on the exit code from
your monitoring agent.

## systemd timer (preferred on hardened hosts)

`/etc/systemd/system/ocs-backup.service`:

```ini
[Unit]
Description=Operation Child Shield database backup
After=network.target

[Service]
Type=oneshot
User=ocs
WorkingDirectory=/srv/OperationChildShield
Environment=CACHE_DIR=/srv/data
Environment=BACKUP_DIR=/srv/backups
Environment=BACKUP_KEEP=14
ExecStart=/usr/bin/python3 scripts/backup_db.py backup
# Keep the failure visible to `systemctl status`.
StandardOutput=journal
StandardError=journal
```

`/etc/systemd/system/ocs-backup.timer`:

```ini
[Unit]
Description=Daily Operation Child Shield backup

[Timer]
OnCalendar=*-*-* 03:15:00
RandomizedDelaySec=15m
Persistent=true

[Install]
WantedBy=timers.target
```

Enable with:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ocs-backup.timer
systemctl list-timers ocs-backup.timer
journalctl -u ocs-backup.service -n 50
```

`Persistent=true` runs a missed backup after downtime; `RandomizedDelaySec`
avoids every host hitting disk at the same second.

## Restore drill checklist

Run this quarterly, and after any schema change, against a **copy** of the data
directory first.

1. Confirm the newest archive exists and is recent:
   `python3 scripts/backup_db.py list` — the top entry should be < 24h old.
2. Stop the API/worker containers so nothing writes during the restore:
   `docker compose stop backend` (or `systemctl stop ocs-backend`).
3. Copy the current `CACHE_DIR` aside (e.g. `data.pre-restore-$(date +%F)`) so a
   bad restore is reversible.
4. Restore the archive:
   `python3 scripts/backup_db.py restore data/backups/backup-<timestamp>.zip`.
5. Verify file ownership and permissions: databases should be `0600` and owned
   by the service user.
6. Start the API and check `GET /api/health` returns `200`.
7. Verify content, not just liveness:
   - an admin can log in at `/admin/login`;
   - `/api/metrics` returns the expected bill records;
   - row counts look sane (`select count(*) from users;` for `users.db`).
8. Record the drill date, archive used, and time to recovery. Note any archive
   that failed to restore and investigate before the next cycle.
9. Copy at least one archive off-host (object storage or another machine);
   backups that only exist on the server are not backups.

## Failure handling

- A non-zero exit means at least one database could not be snapshotted; check
  the log line it prints and confirm the file is present and readable.
- A restore refuses archives containing members that are not one of the known
  database names, so a wrong or tampered zip cannot overwrite other files.
- Keep `BACKUP_KEEP` large enough to cover the interval between off-host copies.
