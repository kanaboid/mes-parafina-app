# Odtwarzanie awaryjne — MES Parafina

Procedura backupu, failover i powrotu na produkcję.

## Hosty

| Host | Rola | Adres aplikacji |
|------|------|-----------------|
| **terminal3** | Produkcja (primary) | `http://terminal3/` (port z `docker-compose.yml`, np. 8080 lub 80) |
| **terminal1** | Standby (failover) | `http://terminal1/` (**port 80** — plik `docker-compose.standby.yml`) |
| **oczyszczalnia-aio** | Archiwum backupów | tylko SSH/rsync |

## Architektura backupu

```
terminal3 (produkcja)
    │
    ├── co 1 h: mysqldump + .env → ~/mes-backups/
    ├── rsync --delete → terminal1:~/mes-backups/     (retencja 14 dni)
    └── rsync → oczyszczalnia-aio:~/mes-backups-archive/mysql/  (retencja 90 dni)
```

Skrypty w katalogu `scripts/`:

| Skrypt | Gdzie uruchamiać | Opis |
|--------|------------------|------|
| `backup-mes.sh` | terminal3 (cron) | Backup bazy i konfiguracji |
| `restore-mes.sh` | terminal1 | Ręczne przywrócenie bazy |
| `failover-start.sh` | terminal1 | Start systemu po awarii |
| `failover-stop.sh` | terminal1 | Zatrzymanie standby |
| `monitor-primary.sh` | terminal1 (cron) | Sprawdzenie czy terminal3 żyje |
| `mysql-replication-*.sh` | terminal3 / terminal1 | Replikacja MySQL — patrz `docs/mysql-replication.md` |

---

## Replikacja MySQL (opcjonalnie)

Ciągła kopia bazy terminal3 → terminal1. Szczegóły: **[docs/mysql-replication.md](mysql-replication.md)**.

Skrót:

```bash
# terminal3
./scripts/mysql-replication-setup-primary.sh

# terminal1 (jednorazowo)
./scripts/mysql-replication-setup-replica.sh
./scripts/mysql-replication-start-db.sh   # @reboot

# failover z repliką
./scripts/failover-start.sh --use-replication --sync-env
```

---

## Przygotowanie standby (jednorazowo na terminal1)

```bash
git clone https://github.com/kanaboid/mes-parafina-app.git ~/mes-parafina-app
cd ~/mes-parafina-app
git switch terminale-gui

# Docker — patrz dokumentacja instalacji w README / wcześniejsze instrukcje

cp ~/mes-backups/config/env_latest.bak ~/mes-parafina-app/.env
chmod +x scripts/*.sh
docker compose build

# Standby uruchamia aplikację na porcie 80 (docker-compose.standby.yml).
# Skrypt failover-start.sh używa tego pliku automatycznie.

# Otwórz port 80 w firewallu (jeśli UFW włączony):
# sudo ufw allow 80/tcp

# Standby domyślnie WYŁĄCZONY:
docker compose down
```

W `.env` na standby ustaw (jeśli brak HTTPS w LAN):

```
FLASK_ENV=development
ENVIRONMENT=development
```

---

## Backup na produkcji (terminal3)

### Cron (co godzinę)

```cron
0 * * * * /home/terminal3/mes-parafina-app/scripts/backup-mes.sh >> /home/terminal3/mes-backup.log 2>&1
```

### Auto-start po restarcie maszyny (terminal3)

```cron
@reboot sleep 30 && cd /home/terminal3/mes-parafina-app && docker compose up -d
```

### Git na produkcji

```bash
git config core.fileMode false
git pull
```

### Logi backupu

```bash
tail -50 ~/mes-backup.log
```

---

## Test odtwarzania (co miesiąc, na terminal1)

```bash
cd ~/mes-parafina-app
./scripts/failover-start.sh --sync-env
# sprawdź http://terminal1/ w przeglądarce
./scripts/failover-stop.sh
```

---

## Failover — gdy terminal3 nie działa

### 1. Potwierdź awarię

```bash
# z terminal1 lub innego PC w sieci
curl -I http://terminal3/
ssh terminal3    # jeśli nie odpowiada — failover
```

### 2. Uruchom system na terminal1

**Pełny failover (restore z ostatniego backupu):**

```bash
cd ~/mes-parafina-app
git pull
./scripts/failover-start.sh --sync-env
```

**Bez restore (baza już była odtworzona wcześniej):**

```bash
./scripts/failover-start.sh --no-restore
```

**Konkretny plik backupu:**

```bash
DUMP_FILE=~/mes-backups/mysql/mes_parafina_db_20260616_180001.sql.gz \
  ./scripts/failover-start.sh --sync-env
```

### 3. Sprawdź działanie

```bash
docker compose ps
docker compose logs -f web
curl -I http://terminal1/
```

Otwórz w przeglądarce: `http://terminal1/` (port **80**).

Skrypty failover używają `docker-compose.standby.yml`, który mapuje `80:5000`.

### 4. Przekieruj użytkowników

**Opcja A — zmiana DNS / routera (zalecane):**

Przypisz nazwę `terminal3` do IP maszyny **terminal1**.

**Opcja B — plik hosts na każdym kliencie:**

```
192.168.x.x   terminal3
```

(gdzie `192.168.x.x` to IP **terminal1**)

**Opcja C — komunikat:**

„Wchodźcie na `http://terminal1/`”.

### 5. Po przełączeniu

- Backup z terminal3 **nie działa** — po naprawie terminal3 uruchom go ponownie.
- Nowe dane powstają tylko na terminal1 — przed failback zrób dump z terminal1.

---

## Failback — powrót na terminal3

Gdy terminal3 wróci do działania:

### 1. Zatrzymaj standby

```bash
# na terminal1
cd ~/mes-parafina-app
./scripts/failover-stop.sh
```

### 2. Jeśli na terminal1 powstały nowe dane produkcyjne

Zrób dump na terminal1 i przywróć na terminal3:

```bash
# terminal1 — tymczasowo uruchom tylko db jeśli stack down
cd ~/mes-parafina-app
docker compose up -d db
# ręczny dump (lub uruchom backup-mes.sh jeśli dostosujesz do standby)

# terminal3 — po uruchomieniu stacku
./scripts/restore-mes.sh /ścieżka/do/dumpa.sql.gz
```

### 3. Uruchom produkcję na terminal3

```bash
cd ~/mes-parafina-app
docker compose up -d
docker compose exec web alembic upgrade head
```

### 4. Przywróć DNS / hosts

`terminal3` → z powrotem IP **terminal3**.

### 5. Wznów backup

Sprawdź cron i ręcznie:

```bash
./scripts/backup-mes.sh
```

---

## Monitoring (opcjonalnie, terminal1)

```cron
*/5 * * * * /home/terminal1/mes-parafina-app/scripts/monitor-primary.sh >> /home/terminal1/mes-monitor.log 2>&1
```

Log awarii:

```bash
tail -20 ~/mes-monitor.log
```

---

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---------|-------------|
| JS się nie ładują | `FLASK_ENV=development`, `ENVIRONMENT=development` w `.env` |
| `git pull` blokuje się | `git config core.fileMode false` lub `git checkout -- scripts/` |
| Brak odpowiedzi HTTP | `docker compose logs web`, sprawdź port w `docker-compose.yml` |
| Restore się nie udaje | `docker compose up -d db`, poczekaj 30 s, ponów restore |
| Symlink `latest.sql.gz` zły na terminal1 | Uruchom backup ponownie na terminal3 (względny symlink) |

---

## Kontakty i notatki

Uzupełnij ręcznie:

- IP terminal3: `________________`
- IP terminal1: `________________`
- IP oczyszczalnia-aio: `________________`
- Osoba do powiadomienia przy awarii: `________________`
