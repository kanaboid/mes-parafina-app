# Replikacja MySQL — terminal3 → terminal1

Replikacja **asynchroniczna** — dane z produkcji kopiowane na bieżąco do standby.
Przy failoverze można promować replikę zamiast czekać na ostatni dump (mniejsza utrata danych niż sam backup co godzinę).

```
terminal3 (PRIMARY)                    terminal1 (REPLICA)
  MySQL binlog  ────── sieć :3306 ────►  MySQL read_only
  aplikacja web                          tylko db (bez web)
```

Backupy (`backup-mes.sh`) **zostają** — to druga linia obrony.

---

## Wymagania

1. Działający PRIMARY na terminal3
2. SSH i sieć LAN między hostami
3. Port **3306** na terminal3 dostępny **tylko z IP terminal1**
4. Te same hasła w `.env` na obu hostach (root + replikacja)

---

## Krok 1: Hasła w `.env` (oba hosty)

Dodaj do `.env` na **terminal3** i **terminal1**:

```env
MYSQL_REPLICATION_USER=repl
MYSQL_REPLICATION_PASSWORD=wygeneruj-silne-haslo-tutaj
PRIMARY_HOST=terminal3
```

---

## Krok 2: PRIMARY na terminal3

```bash
cd ~/mes-parafina-app
git pull
chmod +x scripts/*.sh

./scripts/mysql-replication-setup-primary.sh
```

Firewall — tylko terminal1 (podstaw IP):

```bash
sudo ufw allow from IP_TERMINAL1 to any port 3306 proto tcp
sudo ufw status
```

### Auto-start z binlogiem (zaktualizuj cron @reboot na terminal3)

```cron
@reboot sleep 30 && cd /home/terminal3/mes-parafina-app && COMPOSE_FILE=docker-compose.yml:docker-compose.primary.yml docker compose up -d
```

---

## Krok 3: REPLICA na terminal1 (jednorazowa inicjalizacja)

```bash
cd ~/mes-parafina-app
git pull
chmod +x scripts/*.sh

./scripts/mysql-replication-setup-replica.sh
```

Skrypt:
- kasuje lokalny wolumen MySQL na terminal1,
- pobiera dump z terminal3 z pozycją binlog,
- uruchamia `START REPLICA`.

---

## Krok 4: Utrzymanie repliki (terminal1)

Tylko baza — **bez** aplikacji web:

```bash
./scripts/mysql-replication-start-db.sh
```

Cron `@reboot` na terminal1:

```cron
@reboot sleep 30 && /home/terminal1/mes-parafina-app/scripts/mysql-replication-start-db.sh >> /home/terminal1/mes-replica.log 2>&1
```

### Status (co kilka godzin lub z crona)

```bash
./scripts/mysql-replication-status.sh
```

Oczekiwane:

```
Slave_IO_Running: Yes
Slave_SQL_Running: Yes
Seconds_Behind_Master: 0   (lub mała liczba)
```

---

## Failover z repliką

Gdy terminal3 padł, a replika działa:

```bash
cd ~/mes-parafina-app
./scripts/failover-start.sh --use-replication --sync-env
```

To:
1. promuje replikę (`mysql-replication-promote.sh`),
2. uruchamia pełny stack na porcie 80,
3. **bez** restore z pliku `.sql.gz`.

Alternatywnie ręcznie:

```bash
./scripts/mysql-replication-promote.sh
./scripts/failover-start.sh --no-restore
```

Potem przekieruj użytkowników (`terminal3` → IP terminal1).

---

## Failback (powrót na terminal3)

Po naprawie terminal3 replikacja wymaga **ponownej konfiguracji** (terminal1 był chwilowo PRIMARY).

Uproszczony plan:

1. Zatrzymaj aplikację na terminal1: `./scripts/failover-stop.sh`
2. Zrób dump z terminal1 (jeśli były nowe dane): `backup-mes.sh` lub ręczny mysqldump
3. Na terminal3: uruchom stack, przywróć dump jeśli trzeba
4. Na terminal1: ponów `./scripts/mysql-replication-setup-replica.sh`
5. Przywróć DNS na terminal3

---

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---------|-------------|
| `Slave_IO_Running: No` | Firewall 3306, hasło `repl`, `PRIMARY_HOST` |
| `Seconds_Behind_Master` duże | Odczekaj; sprawdź obciążenie sieci/CPU |
| Brak `SHOW MASTER STATUS` na primary | Uruchom z `docker-compose.primary.yml` |
| Replikacja po teście restore | Ponów `mysql-replication-setup-replica.sh` |

---

## Skrypty

| Skrypt | Host |
|--------|------|
| `mysql-replication-setup-primary.sh` | terminal3 |
| `mysql-replication-setup-replica.sh` | terminal1 (raz) |
| `mysql-replication-start-db.sh` | terminal1 (codziennie/@reboot) |
| `mysql-replication-status.sh` | oba |
| `mysql-replication-promote.sh` | terminal1 (failover) |

Szczegóły failover: `docs/disaster-recovery.md`
