# Replikacja MySQL — terminal3 → terminal1

Replikacja **asynchroniczna** — dane z produkcji kopiowane na bieżąco na standby.
Przy failoverze: `./scripts/failover-start.sh --use-replication` (bez restore z dumpa).

```
terminal3 (PRIMARY)                    terminal1 (REPLICA)
  MySQL binlog  ────── :3306 ────────►  MySQL (read_only po konfiguracji)
  aplikacja web                          tylko kontener db
```

Backupy (`backup-mes.sh`) **zostają** — druga linia obrony (do 1 h opóźnienia).

---

## Wymagania

1. PRIMARY na terminal3 z `docker-compose.primary.yml` (binlog)
2. Sieć między hostami (LAN / Tailscale), port **3306** na terminal3
3. Spójne hasła w `.env` na obu hostach
4. `MYSQLUSER=mes_user` (nie `root`) — wymóg obrazu Docker MySQL

---

## Pliki konfiguracyjne

| Plik | Opis |
|------|------|
| `docker/mysql/primary.cnf` | `server-id=1`, binlog |
| `docker/mysql/replica.cnf` | `server-id=2`, relay-log |
| `docker/mysql/promoted.cnf` | wyłącza `read_only` po failover |
| `docker-compose.primary.yml` | override na terminal3 |
| `docker-compose.standby.yml` | port 80 + replica.cnf na terminal1 |
| `docker-compose.failover.yml` | promoted.cnf po promocji repliki |

---

## Krok 1: `.env` (oba hosty)

```env
SECRET_KEY=...
MYSQLUSER=mes_user
MYSQL_ROOT_PASSWORD=...
MYSQL_PASSWORD_FOR_USER=...
MYSQL_REPLICATION_USER=repl
MYSQL_REPLICATION_PASSWORD=wygeneruj-silne-haslo
PRIMARY_HOST=terminal3
```

Na terminal1 zalecane IP zamiast hostname (kontener MySQL lepiej łączy się po IP):

```env
PRIMARY_HOST=100.69.117.56
```

Skrypt `setup-replica.sh` automatycznie rozwiązuje hostname do IP w `CHANGE MASTER TO`.

---

## Krok 2: PRIMARY (terminal3)

```bash
cd ~/mes-parafina-app
git pull
chmod +x scripts/*.sh
./scripts/mysql-replication-setup-primary.sh
```

Skrypt:
- włącza binlog (`docker-compose.primary.yml`),
- tworzy `repl@'%'` z **`mysql_native_password`** (wymagane bez SSL),
- tworzy `root@'%'` do zdalnego mysqldump.

Firewall:

```bash
sudo ufw allow from IP_TERMINAL1 to any port 3306 proto tcp
```

Auto-start:

```cron
@reboot sleep 30 && cd /home/terminal3/mes-parafina-app && COMPOSE_FILE=docker-compose.yml:docker-compose.primary.yml docker compose up -d
```

---

## Krok 3: REPLICA (terminal1, jednorazowo)

```bash
cd ~/mes-parafina-app
git pull
chmod +x scripts/*.sh

docker compose -f docker-compose.yml -f docker-compose.standby.yml down
docker volume rm mes-parafina-app_mysql_data 2>/dev/null || true

./scripts/mysql-replication-setup-replica.sh
```

Skrypt:
- czyści lokalny wolumen MySQL,
- pobiera dump z PRIMARY (`--source-data=2`, `--set-gtid-purged=OFF`),
- przywraca dane,
- `RESET SLAVE ALL` + `CHANGE MASTER TO` (IP, nie hostname),
- `START SLAVE` + `read_only=ON`.

---

## Krok 4: Utrzymanie (terminal1)

```bash
./scripts/mysql-replication-start-db.sh
```

Cron:

```cron
@reboot sleep 30 && /home/terminal1/mes-parafina-app/scripts/mysql-replication-start-db.sh >> /home/terminal1/mes-replica.log 2>&1
```

Status:

```bash
./scripts/mysql-replication-status.sh
```

Oczekiwane:

```
Slave_IO_Running: Yes
Slave_SQL_Running: Yes
Seconds_Behind_Master: 0
Last_IO_Error:          (puste)
```

Test połączenia z terminal1:

```bash
source .env
nc -zv terminal3 3306
docker run --rm --network host mysql:8.0 mysqladmin ping \
  -h terminal3 -uroot -p"${MYSQL_ROOT_PASSWORD}"
```

---

## Failover z repliką

```bash
./scripts/failover-start.sh --use-replication --sync-env
```

Ręcznie:

```bash
./scripts/mysql-replication-promote.sh
./scripts/failover-start.sh --no-restore --sync-env
```

---

## Failback

Po powrocie na terminal3 replikację trzeba **skonfigurować od nowa**:

1. `./scripts/failover-stop.sh` na terminal1
2. Dump z terminal1 → restore na terminal3 (jeśli były nowe dane)
3. PRIMARY na terminal3: `docker compose up -d`
4. `./scripts/mysql-replication-setup-replica.sh` na terminal1

---

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---------|-------------|
| `Slave_IO_Running: Connecting` | `PRIMARY_HOST` = IP; `./scripts/mysql-replication-fix-io.sh` |
| `Authentication requires secure connection` | terminal3: `./scripts/mysql-replication-fix-auth-primary.sh` |
| `CHANGE MASTER` / błąd MTA | Ponów `./scripts/mysql-replication-setup-replica.sh` |
| `MYSQL_USER=root` przy init | Ustaw `MYSQLUSER=mes_user` w `.env` |
| `Access denied` przy restore lokalnym | Skrypt używa `MYSQL_PWD` + `-h 127.0.0.1` |
| `Seconds_Behind_Master` duże | Odczekaj; sprawdź sieć i obciążenie |

---

## Skrypty

| Skrypt | Host |
|--------|------|
| `mysql-replication-setup-primary.sh` | terminal3 |
| `mysql-replication-fix-auth-primary.sh` | terminal3 |
| `mysql-replication-setup-replica.sh` | terminal1 |
| `mysql-replication-start-db.sh` | terminal1 (@reboot) |
| `mysql-replication-status.sh` | oba |
| `mysql-replication-promote.sh` | terminal1 |
| `mysql-replication-fix-io.sh` | terminal1 |
| `mysql-replication-restore-standby.sh` | terminal1 (po teście failover) |

Szczegóły failover: [docs/disaster-recovery.md](disaster-recovery.md)
