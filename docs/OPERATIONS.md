# Running JobCopilot in production

Day-to-day checks for the Docker Compose deployment (`docker-compose.production.yml`).
Commands run on the server, from the repository folder. `dc` below means:

```bash
alias dc='docker compose --env-file .env.production -f docker-compose.production.yml'
```

## 1. Error reports (Sentry, free plan)

1. Create a free account at sentry.io and a **Python / FastAPI** project.
2. Copy its DSN into `.env.production` as `SENTRY_DSN=...` and restart: `dc up -d`.
3. Check: `curl -s https://<your-domain>/health` shows `"sentry_enabled": true`.

What gets reported: API errors, background-job errors (hourly search, applying), and
errors in people's browsers (the web app sends them to `/api/client-errors`).
Reports don't include request bodies, cookies, IP addresses or query strings.

## 2. Uptime alerts (UptimeRobot, free plan)

Add an HTTP(s) monitor for `https://<your-domain>/health` every 5 minutes, with email
alerts. `/health` returns 503 when the database is down.

## 3. Database backups

The `db_backup` service dumps the database once a day into the `db_backups` volume and
keeps 14 days.

```bash
dc logs --tail 5 db_backup                    # expect "backup ok: /backups/jobcopilot-...sql.gz"
dc exec db_backup ls -lh /backups             # list backups
```

**Copy backups off the server.** A backup on the same machine is lost with the machine.
Simplest: once a week, from your own computer:

```bash
scp -i <key> ubuntu@<server-ip>:/var/lib/docker/volumes/jobcopilot_db_backups/_data/*.sql.gz ~/jobcopilot-backups/
```

(For automatic copies, Oracle Cloud's free Object Storage plus `rclone` works well.)

**Restore** (replaces the current data; stop the app first):

```bash
dc stop api celery_worker celery_beat
dc exec -T db_backup sh -c 'gunzip -c /backups/<file>.sql.gz | psql'
dc start api celery_worker celery_beat
```

Test a restore once before launch, on a copy, so you know it works.

## 4. Hourly job search

`celery_beat` queues a search at minute 7 of every hour; `celery_worker` runs it.

```bash
dc logs --since 2h celery_worker | grep "hourly discovery"
# hourly discovery: 2679 postings, 42 users, 17 new matches
```

If nothing appears, check that `celery_beat` is running: `dc ps celery_beat`.

## 5. After deploying an update

```bash
git pull && dc up -d --build
dc ps                                          # all services running / healthy
curl -s https://<your-domain>/health
```

People with the site open get the new version automatically the next time they open a page.
