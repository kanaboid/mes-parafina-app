# Odtwarzanie awaryjne — MES Parafina

Procedura backupu, replikacji MySQL, failover i powrotu na produkcję.

## Hosty

| Host | Rola | Adres aplikacji |
|------|------|-----------------|
| **terminal3** | Produkcja (PRIMARY) | `http://terminal3/` (port z `docker-compose.yml`, np. 80 lub 8080) |
| **terminal1** | Standby (REPLICA + failover) | `http://terminal1/` (**port 80** — `docker-compose.standby.yml`) |
| **oczyszczalnia-aio** | Archiwum backupów | tylko SSH/rsync |

## Architektura

```
terminal3 (PRIMARY)                         terminal1 (REPLICA / standby)
  aplikacja web                               tylko MySQL (replikacja w tle)
  MySQL binlog ────── :3306 ──────────────►  MySQL read_only
       │
       ├── co 1 h: backup-mes.sh → ~/mes-backups/
       ├── rsync → terminal1:~/mes-backups/           (retencja 14 dni)
       └── rsync → oczyszczalnia-aio:~/mes-backups-archive/  (retencja 90 dni)
```

Szczegóły replikacji: **[docs/mysql-replication.md](mysql-replication.md)**  
Monitoring hostów: **[docs/monitoring.md](monitoring.md)**

---

## Skrypty (`scripts/`)

| Skrypt | Host | Opis |
|--------|------|------|
| `backup-mes.sh` | terminal3 (cron) | Dump MySQL + `.env` + rsync |
| `restore-mes.sh` | terminal1 | Przywrócenie bazy z `.sql.gz` |
| `failover-start.sh` | terminal1 | Start aplikacji po awarii |
| `failover-stop.sh` | terminal1 | Zatrzymanie stacku standby |
| `monitor-primary.sh` | terminal1 (cron) | Sprawdzenie `http://terminal3/` — opcjonalnie; zastąpione przez [Uptime Kuma](monitoring.md) |
| `monitoring-start.sh` | oczyszczalnia-aio / wszystkie | Uruchomienie Kuma lub Netdata |
| `monitoring-kuma-push.sh` | terminal3, terminal1 | Ping do monitora Push w Kuma |
| `mysql-replication-healthcheck.sh` | terminal1 (cron) | Replikacja OK + push do Kuma |
| `mysql-replication-setup-primary.sh` | terminal3 | Binlog + użytkownik `repl` |
| `mysql-replication-setup-replica.sh` | terminal1 | Jednorazowa inicjalizacja repliki |
| `mysql-replication-start-db.sh` | terminal1 (@reboot) | Uruchomienie samej bazy |
| `mysql-replication-status.sh` | oba | Status PRIMARY / REPLICA |
| `mysql-replication-promote.sh` | terminal1 | Promocja repliki przy failover |
| `mysql-replication-fix-auth-primary.sh` | terminal3 | Naprawa `mysql_native_password` dla `repl` |
| `mysql-replication-fix-io.sh` | terminal1 | Naprawa `MASTER_HOST` (IP) |
| `mysql-replication-restore-standby.sh` | terminal1 | Po teście failover — przywróć replikę |

## Pliki Compose

| Plik | Host | Opis |
|------|------|------|
| `docker-compose.yml` | oba | Bazowy stack |
| `docker-compose.primary.yml` | terminal3 | Binlog MySQL |
| `docker-compose.standby.yml` | terminal1 | Port 80 + config repliki |
| `docker-compose.failover.yml` | terminal1 | Wyłącza `read_only` po promocji |

---

## Przygotowanie standby (jednorazowo, terminal1)

```bash
git clone https://github.com/kanaboid/mes-parafina-app.git ~/mes-parafina-app
cd ~/mes-parafina-app
git switch terminale-gui

cp ~/mes-backups/config/env_latest.bak ~/mes-parafina-app/.env
chmod +x scripts/*.sh
docker compose build

# Standby: tylko replika MySQL (bez aplikacji web):
./scripts/mysql-replication-setup-replica.sh
./scripts/mysql-replication-start-db.sh

sudo ufw allow 80/tcp   # na wypadek failover
```

W `.env` na standby (LAN bez HTTPS):

```env
FLASK_ENV=development
ENVIRONMENT=development
MYSQLUSER=mes_user
PRIMARY_HOST=terminal3
MYSQL_REPLICATION_USER=repl
MYSQL_REPLICATION_PASSWORD=...
```

> `MYSQLUSER` nie może być `root` — obraz Docker MySQL tego nie akceptuje przy pierwszej inicjalizacji.

---

## Produkcja (terminal3)

### Cron — backup co godzinę

```cron
0 * * * * /home/terminal3/mes-parafina-app/scripts/backup-mes.sh >> /home/terminal3/mes-backup.log 2>&1
```

Opcjonalne zmienne: `KEEP_DAYS=14`, `ARCHIVE_KEEP_DAYS=90`

### Auto-start po restarcie

```cron
@reboot sleep 30 && cd /home/terminal3/mes-parafina-app && COMPOSE_FILE=docker-compose.yml:docker-compose.primary.yml docker compose up -d
```

### Git na produkcji

```bash
git config core.fileMode false
git pull
chmod +x scripts/*.sh
```

### Logi backupu

```bash
tail -50 ~/mes-backup.log
```

---

## Utrzymanie repliki (terminal1)

### Cron `@reboot`

```cron
@reboot sleep 30 && /home/terminal1/mes-parafina-app/scripts/mysql-replication-start-db.sh >> /home/terminal1/mes-replica.log 2>&1
```

### Status (co tydzień)

```bash
./scripts/mysql-replication-status.sh
```

Oczekiwane: `Slave_IO_Running: Yes`, `Slave_SQL_Running: Yes`, `Seconds_Behind_Master: 0`

---

## Test miesięczny (terminal1)

**Replikacja działa — nie uruchamiaj pełnego stacku na co dzień.**

```bash
# tylko sprawdź replikę:
./scripts/mysql-replication-status.sh

# opcjonalnie test failover (krótko):
./scripts/failover-start.sh --use-replication --sync-env
# sprawdź http://terminal1/
./scripts/mysql-replication-restore-standby.sh   # przywróć replikę po teście
```

---

## Failover — gdy terminal3 nie działa

### 1. Potwierdź awarię

```bash
curl -I http://terminal3/
ssh terminal3
./scripts/mysql-replication-status.sh   # replika powinna być aktualna
```

### 2. Uruchom na terminal1

**Zalecane (replikacja działa — dane sprzed sekund):**

```bash
cd ~/mes-parafina-app
git pull
./scripts/failover-start.sh --use-replication --sync-env
```

**Awaryjnie (restore z backupu, gdy replikacja nie działa):**

```bash
./scripts/failover-start.sh --sync-env
# lub konkretny dump:
DUMP_FILE=~/mes-backups/mysql/latest.sql.gz ./scripts/failover-start.sh --sync-env
```

**Bez restore (baza już gotowa):**

```bash
./scripts/failover-start.sh --no-restore
```

### 3. Sprawdź

```bash
docker compose -f docker-compose.yml -f docker-compose.standby.yml -f docker-compose.failover.yml ps
docker compose logs -f web
curl -I http://terminal1/
```

### 4. Przekieruj użytkowników

- DNS/router: nazwa `terminal3` → IP **terminal1**, lub
- `/etc/hosts` na klientach, lub
- komunikat: „wchodźcie na `http://terminal1/`”

### 5. Po przełączeniu

- Backup na terminal3 nie działa — po naprawie wznów cron.
- Nowe dane tylko na terminal1 — przed failback zrób dump.

---

## Failback — powrót na terminal3

1. Na terminal1: `./scripts/failover-stop.sh`
2. Dump z terminal1 (jeśli były nowe dane) → restore na terminal3
3. Na terminal3: `COMPOSE_FILE=docker-compose.yml:docker-compose.primary.yml docker compose up -d`
4. Na terminal1: `./scripts/mysql-replication-setup-replica.sh` (odtwórz replikę)
5. Przywróć DNS: `terminal3` → IP terminal3
6. Wznów backup: `./scripts/backup-mes.sh`

---

## Monitoring (terminal1, opcjonalnie)

```cron
*/5 * * * * /home/terminal1/mes-parafina-app/scripts/monitor-primary.sh >> /home/terminal1/mes-monitor.log 2>&1
```

---

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---------|-------------|
| JS się nie ładują (HTTP) | `FLASK_ENV=development`, `ENVIRONMENT=development` w `.env` |
| `git pull` blokuje się | `git config core.fileMode false` |
| Replika `Connecting` / błąd SSL | terminal3: `mysql-replication-fix-auth-primary.sh`; terminal1: `mysql-replication-fix-io.sh` |
| Replika w stanie błędu SQL | Ponów `mysql-replication-setup-replica.sh` |
| Restore nie działa | `MYSQL_PWD` — użyj `restore-mes.sh` z repo |
| Symlink `latest.sql.gz` zły | Ponów backup na terminal3 |

---

## Kontakty (uzupełnij ręcznie)

- IP terminal3 (Tailscale): `100.69.117.56`
- IP terminal1 (Tailscale): `100.69.117.5` / `100.124.169.118`
- IP oczyszczalnia-aio: `________________`
- Osoba przy awarii: `________________`
